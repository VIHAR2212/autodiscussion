import asyncio
import os
import re
import json
import httpx
import subprocess
import tempfile
import shutil
from pathlib import Path

# ─── CONFIG ────────────────────────────────────────────────────────────────────
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")       # paste your Groq key here
PEXELS_API_KEY  = os.getenv("PEXELS_API_KEY", "")     # paste your Pexels key here
OUTPUT_DIR      = Path("outputs")
MUSIC_FILE      = Path("assets/bg_music.mp3")          # drop any royalty-free mp3 here
OUTPUT_DIR.mkdir(exist_ok=True)

MARKET_LABELS = {
    "india":  "Indian (₹ prices, Indian brands like Tata, Maruti, Hyundai India)",
    "global": "global",
    "us":     "American (USD prices, US market)",
    "uk":     "British (GBP prices, UK market)",
}

# ─── STEP 1: SCRIPT GENERATION (Groq) ──────────────────────────────────────────
async def generate_script(topic: str, content_type: str, market: str, notes: str) -> dict:
    market_label = MARKET_LABELS.get(market, "global")

    system_prompt = f"""You are a viral YouTube script writer for a faceless car channel.
Write in this exact format and return ONLY valid JSON, nothing else:

{{
  "title": "YouTube video title (clickbait, under 60 chars)",
  "description": "YouTube description (150 words, include keywords)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "hook": "First 15 seconds — dramatic opening line that hooks viewers",
  "scenes": [
    {{
      "id": 1,
      "narration": "Narration text for this scene (2-4 sentences)",
      "photo_keyword": "specific search term for Pexels e.g. 'Tata Punch SUV red front view'",
      "duration": 8
    }}
  ],
  "short_hook": "Best 90-second cut — rewrite the hook + top 2 scenes into one punchy narration for Shorts/Reels"
}}

Rules:
- content_type: {content_type}
- market: {market_label}
- Long video: 15-20 scenes, total ~8-10 minutes
- Each scene narration = 2-4 sentences max
- photo_keyword must be very specific for car image search
- short_hook must be standalone 90 seconds (no reference to long video)
- {f'Extra notes: {notes}' if notes else ''}"""

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Write a YouTube script about: {topic}"}
                ],
                "temperature": 0.8,
                "max_tokens": 4000,
            }
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]

    # Strip markdown fences if present
    clean = re.sub(r"```json|```", "", raw).strip()
    return json.loads(clean)

# ─── STEP 2: TEXT TO SPEECH (Edge TTS — 100% Free) ─────────────────────────────
async def text_to_speech(text: str, output_path: str, voice: str = "en-US-GuyNeural"):
    """Uses edge-tts (Microsoft Edge TTS) — completely free, no API key needed"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

async def generate_voiceovers(scenes: list, short_hook: str, job_dir: Path) -> dict:
    """Generate MP3 for each scene + one for short"""
    audio_dir = job_dir / "audio"
    audio_dir.mkdir(exist_ok=True)

    scene_audios = []
    for scene in scenes:
        out_path = str(audio_dir / f"scene_{scene['id']:02d}.mp3")
        await text_to_speech(scene["narration"], out_path)
        scene_audios.append(out_path)

    # Short version audio
    short_audio = str(audio_dir / "short.mp3")
    await text_to_speech(short_hook, short_audio)

    return {"scene_audios": scene_audios, "short_audio": short_audio}

# ─── STEP 3: PHOTO FETCHING (Pexels API — Free) ────────────────────────────────
async def fetch_photo(keyword: str, photo_dir: Path, idx: int) -> str:
    """Fetch best matching car photo from Pexels"""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": keyword, "per_page": 3, "orientation": "landscape"}
        )
        response.raise_for_status()
        photos = response.json().get("photos", [])

        if not photos:
            # Fallback: search just "car" if specific search fails
            response = await client.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": "car automotive", "per_page": 3, "orientation": "landscape"}
            )
            photos = response.json().get("photos", [])

        if not photos:
            return None

        # Pick highest quality photo
        photo_url = photos[0]["src"]["large2x"]
        photo_path = str(photo_dir / f"photo_{idx:02d}.jpg")

        img_response = await client.get(photo_url)
        with open(photo_path, "wb") as f:
            f.write(img_response.content)

        return photo_path

async def fetch_all_photos(scenes: list, job_dir: Path) -> list:
    photo_dir = job_dir / "photos"
    photo_dir.mkdir(exist_ok=True)

    tasks = [fetch_photo(scene["photo_keyword"], photo_dir, scene["id"]) for scene in scenes]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    photo_paths = []
    for i, r in enumerate(results):
        if isinstance(r, Exception) or r is None:
            photo_paths.append(None)
        else:
            photo_paths.append(r)

    return photo_paths

# ─── STEP 4: GET AUDIO DURATION ────────────────────────────────────────────────
def get_audio_duration(audio_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except:
        return 8.0  # fallback duration

# ─── STEP 5: VIDEO ASSEMBLY (FFmpeg) ───────────────────────────────────────────
def build_long_video(scenes: list, photo_paths: list, scene_audios: list, job_dir: Path) -> str:
    """Assemble long video: Ken Burns photos + voiceover + subtitles + bg music"""
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(exist_ok=True)
    clip_paths = []

    for i, (scene, photo, audio) in enumerate(zip(scenes, photo_paths, scene_audios)):
        if photo is None or not os.path.exists(photo):
            continue
        if not os.path.exists(audio):
            continue

        duration = get_audio_duration(audio)
        clip_out = str(clips_dir / f"clip_{i:02d}.mp4")

        # Ken Burns effect: slow zoom in on photo, synced to audio duration
        zoom_filter = (
            f"zoompan=z='min(zoom+0.0008,1.3)':d={int(duration*25)}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s=1920x1080:fps=25"
        )

        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1", "-i", photo,
            "-i", audio,
            "-vf", zoom_filter,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            clip_out
        ], capture_output=True)

        if os.path.exists(clip_out):
            clip_paths.append(clip_out)

    if not clip_paths:
        raise Exception("No clips were generated")

    # Concat list
    concat_file = str(job_dir / "concat.txt")
    with open(concat_file, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    # Merge all clips
    merged = str(job_dir / "merged.mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        merged
    ], capture_output=True)

    # Add background music if available
    long_out = str(OUTPUT_DIR / f"{job_dir.name}_long.mp4")
    if MUSIC_FILE.exists():
        subprocess.run([
            "ffmpeg", "-y",
            "-i", merged,
            "-i", str(MUSIC_FILE),
            "-filter_complex",
            "[1:a]volume=0.08[music];[0:a][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac",
            long_out
        ], capture_output=True)
    else:
        shutil.copy(merged, long_out)

    return long_out

def build_short_video(short_audio: str, photo_paths: list, job_dir: Path) -> str:
    """Build vertical 9:16 short/reel — first 3 photos, 90 sec max"""
    duration = get_audio_duration(short_audio)
    duration = min(duration, 90)

    # Use first 3 valid photos
    valid_photos = [p for p in photo_paths if p and os.path.exists(p)][:3]
    if not valid_photos:
        raise Exception("No photos for short video")

    per_photo = duration / len(valid_photos)
    clips_dir = job_dir / "short_clips"
    clips_dir.mkdir(exist_ok=True)
    clip_paths = []

    for i, photo in enumerate(valid_photos):
        clip_out = str(clips_dir / f"short_clip_{i}.mp4")
        frames = int(per_photo * 25)

        # Vertical crop (9:16) + Ken Burns
        zoom_filter = (
            f"zoompan=z='min(zoom+0.001,1.4)':d={frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s=1080x1920:fps=25,"
            f"crop=1080:1920"
        )

        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1", "-i", photo,
            "-vf", zoom_filter,
            "-c:v", "libx264",
            "-t", str(per_photo),
            "-pix_fmt", "yuv420p",
            clip_out
        ], capture_output=True)

        if os.path.exists(clip_out):
            clip_paths.append(clip_out)

    # Concat short clips
    concat_file = str(job_dir / "short_concat.txt")
    with open(concat_file, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    merged_video = str(job_dir / "short_merged.mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        merged_video
    ], capture_output=True)

    # Combine with audio
    short_out = str(OUTPUT_DIR / f"{job_dir.name}_short.mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", merged_video,
        "-i", short_audio,
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        short_out
    ], capture_output=True)

    return short_out

# ─── MAIN PIPELINE ──────────────────────────────────────────────────────────────
async def run_pipeline(topic, content_type, market, notes, format_type, update_fn):
    job_id = os.urandom(4).hex()
    job_dir = Path(f"jobs/{job_id}")
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        update_fn(10, "✍️ Generating script with Groq...")
        script_data = await generate_script(topic, content_type, market, notes)

        update_fn(25, "🎙️ Generating voiceovers with Edge TTS...")
        audio_data = await generate_voiceovers(
            script_data["scenes"],
            script_data["short_hook"],
            job_dir
        )

        update_fn(45, "🖼️ Fetching car photos from Pexels...")
        photo_paths = await fetch_all_photos(script_data["scenes"], job_dir)

        result = {
            "script": script_data,
            "title": script_data.get("title"),
            "description": script_data.get("description"),
            "tags": script_data.get("tags"),
        }

        if format_type in ("long", "both"):
            update_fn(65, "🎬 Assembling long video (FFmpeg)...")
            long_path = build_long_video(
                script_data["scenes"],
                photo_paths,
                audio_data["scene_audios"],
                job_dir
            )
            result["long_path"] = long_path

        if format_type in ("short", "both"):
            update_fn(85, "📱 Assembling Short/Reel (9:16)...")
            short_path = build_short_video(
                audio_data["short_audio"],
                photo_paths,
                job_dir
            )
            result["short_path"] = short_path

        update_fn(100, "✅ Done!")
        return result

    finally:
        # Cleanup temp job dir (keep outputs)
        shutil.rmtree(job_dir, ignore_errors=True)
