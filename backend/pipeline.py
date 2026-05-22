from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import re
import json
import httpx
import subprocess
import shutil
from pathlib import Path

# ─── CONFIG ────────────────────────────────────────────────────────────────────
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
OUTPUT_DIR     = Path("outputs")
MUSIC_FILE     = Path("assets/bg_music.mp3")
OUTPUT_DIR.mkdir(exist_ok=True)

FFMPEG  = "C:\\ffmpeg\\bin\\ffmpeg.exe"
FFPROBE = "C:\\ffmpeg\\bin\\ffprobe.exe"

MARKET_LABELS = {
    "india":  "Indian (₹ prices, Indian brands like Tata, Maruti, Hyundai India)",
    "global": "global",
    "us":     "American (USD prices, US market)",
    "uk":     "British (GBP prices, UK market)",
}

# ─── STEP 1: SCRIPT GENERATION ─────────────────────────────────────────────────
async def generate_script(topic: str, content_type: str, market: str, notes: str) -> dict:
    market_label = MARKET_LABELS.get(market, "global")

    system_prompt = f"""You are a viral YouTube script writer for a faceless car channel.
You write in a witty, entertaining style — like a knowledgeable friend who roasts cars for fun.
Think: Top Gear meets stand-up comedy. Add funny observations naturally throughout every script.

ROAST style:
- "The AC works great... said no one in summer ever"
- "BMW owners have two hobbies — driving and visiting the service center"
- "The resale value drops faster than your confidence after buying it"
- "This car has the turning radius of a small country"
- "It's reliable. Mostly. When it wants to be."
- "Built like a tank — unfortunately the tank in question is a toy one"

RELATABLE style (adapt to market):
- "The mileage is better than my life decisions"
- "Ground clearance so low it scrapes speed bumps — and speed bumps out here are basically mountain ranges"
- "Comparing these two is like choosing between two bad options — one is just slightly less bad"
- "The boot space is generous. Unless you actually want to put things in it."

HOOK openers style:
- "You've been spending thousands on the wrong car and nobody told you"
- "This car will either save your life or embarrass you — let's find out which"
- "If cars could talk, this one would have a lot of complaints"
- "Most people buy this car. Most people are wrong."
- "The car companies don't want you to know this comparison exists"

COMPARISON roast style:
- "One is built like a tank. The other is built like the budget for a tank."
- "This car is perfect — if you enjoy explaining to people why you bought it"
- "Both cars are great. One of them just happens to be greater."
- "Choosing between these two is the most important decision you'll make this year. Possibly ever."

WORLDWIDE brands humor:
- "Toyota reliability is a religion at this point — people pray to it"
- "Mercedes: for when you want everyone to know you have money and bad taste in parking spots"
- "A Lamborghini on a speed bump is not a car — it's a prayer"
- "Tesla owners will tell you about their Tesla within 30 seconds. Every time."
- "Buying a Ferrari and living in a city with traffic is the world's most expensive joke"

Write in this EXACT format and return ONLY valid JSON, nothing else:

{{
  "title": "YouTube video title (clickbait, under 60 chars)",
  "description": "YouTube description (150 words, include keywords)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "hook": "First 15 seconds — dramatic + funny opening line",
  "scenes": [
    {{
      "id": 1,
      "narration": "Narration for this scene. Keep it punchy, 2-3 sentences max. Add one witty observation per scene.",
      "photo_keyword": "MUST match exactly what is being talked about in narration. See rules below.",
      "duration": 8,
      "transition": "one of: slow_zoom_in | zoom_out | pan_left | pan_right | fast_zoom | slow_zoom_out_in",
      "mood": "one of: dramatic | action | story | compare | verdict | funny"
    }}
  ],
  "short_hook": "Best 90-second standalone cut for Shorts/Reels — witty and punchy"
}}

Rules:
- content_type: {content_type}
- market: {market_label}
- Long video: 18-22 scenes for 8-10 minute video (more scenes = longer video)
- Each scene narration = 2-3 sentences ONLY (shorter = better sync with photos)
- No long paragraphs — short punchy sentences
- At least 1 funny/witty line per 3 scenes
- {f'Extra notes: {notes}' if notes else ''}

CRITICAL photo_keyword rules — the photo must match EXACTLY what is spoken in that scene:
- Talking about BMW M4 exterior → "BMW M4 front exterior red"
- Talking about Toyota Supra → "Toyota Supra MK4 side profile"
- Talking about engine → "BMW inline 6 engine bay"
- Talking about exhaust/silencer → "sports car exhaust pipe close up"
- Talking about interior → "BMW M4 interior dashboard cockpit"
- Talking about seats → "sports car leather seats interior"
- Talking about wheels/rims → "BMW M4 alloy wheels close up"
- Talking about brakes → "sports car brake caliper disc"
- Talking about headlights → "BMW M4 LED headlights front"
- Talking about price/value → "luxury car dealership showroom"
- Talking about racing/track → "sports car race track drift"
- Talking about reliability → "car engine maintenance repair"
- Talking about safety → "car crash test safety airbag"
- Talking about speed → "sports car highway speed motion blur"
- Talking about comparison/verdict → "two sports cars side by side"
- NEVER use generic "car" — always be specific to the exact topic and brand being discussed

TRANSITION rules — pick based on what is happening in the scene:
- slow_zoom_in: calm storytelling, background info, introductions
- zoom_out: dramatic reveals, shocking facts, "but wait..." moments  
- pan_left: comparisons going from car A to car B
- pan_right: comparisons going from car B to car A, timelines moving forward
- fast_zoom: action, speed, performance, exciting moments
- slow_zoom_out_in: verdict, conclusion, emotional moments

MOOD rules:
- dramatic: shocking facts, origins, history
- action: speed, performance, racing, horsepower
- story: background, history, brand story
- compare: head to head comparison scenes
- verdict: final thoughts, which is better
- funny: roast lines, jokes, funny observations"""

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
                "temperature": 0.9,
                "max_tokens": 4000,
            }
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]

    clean = re.sub(r"```json|```", "", raw).strip()
    return json.loads(clean)

# ─── STEP 2: TEXT TO SPEECH ─────────────────────────────────────────────────────
async def text_to_speech(text: str, output_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(
        text,
        voice="en-US-GuyNeural",
        rate="+15%",
        volume="+0%"
    )
    await communicate.save(output_path)

async def generate_voiceovers(scenes: list, short_hook: str, job_dir: Path) -> dict:
    audio_dir = job_dir / "audio"
    audio_dir.mkdir(exist_ok=True)

    scene_audios = []
    for scene in scenes:
        out_path = str(audio_dir / f"scene_{scene['id']:02d}.mp3")
        # rate="+15%" removes unnatural pauses, keeps energy up
        import edge_tts
        communicate = edge_tts.Communicate(
            scene["narration"],
            voice="en-US-GuyNeural",
            rate="+15%",
            volume="+0%"
        )
        await communicate.save(out_path)
        scene_audios.append(out_path)

    short_audio = str(audio_dir / "short.mp3")
    import edge_tts
    communicate = edge_tts.Communicate(
        short_hook,
        voice="en-US-GuyNeural",
        rate="+15%",
        volume="+0%"
    )
    await communicate.save(short_audio)

    return {"scene_audios": scene_audios, "short_audio": short_audio}

# ─── STEP 3: PHOTO FETCHING ─────────────────────────────────────────────────────
async def fetch_photo(keyword: str, photo_dir: Path, idx: int, used_ids: set) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        # Try specific keyword first with more results to avoid duplicates
        response = await client.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": keyword, "per_page": 10, "orientation": "landscape"}
        )
        response.raise_for_status()
        photos = response.json().get("photos", [])

        # Filter out already used photos
        photos = [p for p in photos if p["id"] not in used_ids]

        if not photos:
            # Fallback with broader search
            response = await client.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": "car automotive road", "per_page": 15, "orientation": "landscape", "page": idx % 3 + 1}
            )
            photos = response.json().get("photos", [])
            photos = [p for p in photos if p["id"] not in used_ids]

        if not photos:
            return None

        # Pick first unused photo
        photo = photos[0]
        used_ids.add(photo["id"])
        photo_url = photo["src"]["large2x"]
        photo_path = str(photo_dir / f"photo_{idx:02d}.jpg")

        img_response = await client.get(photo_url)
        with open(photo_path, "wb") as f:
            f.write(img_response.content)

        return photo_path

async def fetch_all_photos(scenes: list, job_dir: Path) -> list:
    photo_dir = job_dir / "photos"
    photo_dir.mkdir(exist_ok=True)
    used_ids = set()  # track used photo IDs to prevent duplicates

    photo_paths = []
    for scene in scenes:
        path = await fetch_photo(scene["photo_keyword"], photo_dir, scene["id"], used_ids)
        photo_paths.append(path)

    return photo_paths

# ─── STEP 4: AUDIO DURATION ─────────────────────────────────────────────────────
def get_audio_duration(audio_path: str) -> float:
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except:
        return 8.0

# ─── TRANSITION FILTERS ─────────────────────────────────────────────────────────
def get_transition_filter(transition: str, duration: float) -> str:
    frames = int(duration * 25)
    t = transition or "slow_zoom_in"

    if t == "slow_zoom_in":
        # Gentle slow zoom in — storytelling
        return (f"zoompan=z='min(zoom+0.0004,1.2)':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25")

    elif t == "zoom_out":
        # Start zoomed in, pull back — dramatic reveal
        return (f"zoompan=z='if(eq(on\,1)\,1.3\,max(zoom-0.0008\,1.0))':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25")

    elif t == "pan_left":
        # Pan from right to left — comparison A to B
        return (f"zoompan=z='1.15':d={frames}:"
                f"x='iw-(iw/zoom/2)-(iw-(iw/zoom))*on/{frames}':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25")

    elif t == "pan_right":
        # Pan from left to right — timeline forward
        return (f"zoompan=z='1.15':d={frames}:"
                f"x='(iw-(iw/zoom))*on/{frames}':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25")

    elif t == "fast_zoom":
        # Fast aggressive zoom — action/speed/performance
        return (f"zoompan=z='min(zoom+0.002,1.4)':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25")

    elif t == "slow_zoom_out_in":
        # Zoom out then back in — verdict/emotional
        half = frames // 2
        return (f"zoompan=z='if(lt(on\,{half})\,max(1.3-on*0.001\,1.05)\,min(1.05+on*0.0004\,1.2))':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25")

    else:
        return (f"zoompan=z='min(zoom+0.0004,1.2)':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25")


# ─── FULL SENTENCE CAPTION GENERATOR ────────────────────────────────────────────
def split_into_lines(text: str, max_chars: int = 45) -> list:
    """Split narration into readable subtitle lines"""
    words = text.split()
    lines = []
    current = []
    for word in words:
        current.append(word)
        if len(" ".join(current)) >= max_chars:
            lines.append(" ".join(current))
            current = []
    if current:
        lines.append(" ".join(current))
    return lines

def build_caption_filter(narration: str, duration: float) -> str:
    """Show subtitle lines timed evenly across the scene duration"""
    lines = split_into_lines(narration, max_chars=40)
    if not lines:
        return ""

    time_per_line = duration / len(lines)
    drawtext_parts = []

    for i, line in enumerate(lines):
        start = i * time_per_line
        end = start + time_per_line

        # Escape special chars
        safe = (line.replace("\", "\\")
                    .replace("'", "")
                    .replace(":", "\:")
                    .replace("%", "\%"))

        drawtext_parts.append(
            f"drawtext=text='{safe}'"
            f":fontsize=54"
            f":fontcolor=white"
            f":bordercolor=black"
            f":borderw=4"
            f":font='Arial Bold'"
            f":x=(w-text_w)/2"
            f":y=h-140"
            f":enable='between(t,{start:.2f},{end:.2f})'"
        )

    return ",".join(drawtext_parts)


# ─── STEP 5: VIDEO ASSEMBLY ─────────────────────────────────────────────────────
def build_long_video(scenes: list, photo_paths: list, scene_audios: list, job_dir: Path) -> str:
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

        transition = scene.get("transition", "slow_zoom_in")
        narration = scene.get("narration", "")

        zoom_filter = get_transition_filter(transition, duration)
        caption_filter = build_caption_filter(narration, duration)

        # Combine zoom + captions
        if caption_filter:
            vf = f"{zoom_filter},{caption_filter}"
        else:
            vf = zoom_filter

        result = subprocess.run([
            FFMPEG, "-y",
            "-loop", "1", "-i", photo,
            "-i", audio,
            "-vf", vf,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            "-avoid_negative_ts", "make_zero",
            clip_out
        ], capture_output=True)

        if os.path.exists(clip_out):
            clip_paths.append(clip_out)

    if not clip_paths:
        raise Exception("No clips were generated")

    concat_file = str(job_dir / "concat.txt")
    with open(concat_file, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    merged = str(job_dir / "merged.mp4")
    subprocess.run([
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        merged
    ], capture_output=True)

    long_out = str(OUTPUT_DIR / f"{job_dir.name}_long.mp4")
    if MUSIC_FILE.exists():
        subprocess.run([
            FFMPEG, "-y",
            "-i", merged,
            "-i", str(MUSIC_FILE),
            "-filter_complex",
            "[1:a]volume=0.07[music];[0:a][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac",
            long_out
        ], capture_output=True)
    else:
        shutil.copy(merged, long_out)

    return long_out

def build_short_video(short_audio: str, photo_paths: list, job_dir: Path) -> str:
    duration = min(get_audio_duration(short_audio), 90)
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

        zoom_filter = (
            f"zoompan=z='min(zoom+0.001,1.4)':d={frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s=1080x1920:fps=25,"
            f"crop=1080:1920"
        )

        subprocess.run([
            FFMPEG, "-y",
            "-loop", "1", "-i", photo,
            "-vf", zoom_filter,
            "-c:v", "libx264",
            "-t", str(per_photo),
            "-pix_fmt", "yuv420p",
            clip_out
        ], capture_output=True)

        if os.path.exists(clip_out):
            clip_paths.append(clip_out)

    concat_file = str(job_dir / "short_concat.txt")
    with open(concat_file, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    merged_video = str(job_dir / "short_merged.mp4")
    subprocess.run([
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        merged_video
    ], capture_output=True)

    short_out = str(OUTPUT_DIR / f"{job_dir.name}_short.mp4")
    subprocess.run([
        FFMPEG, "-y",
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
        shutil.rmtree(job_dir, ignore_errors=True)
