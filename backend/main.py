from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import uuid
import httpx
import tempfile

_key = os.getenv("GROQ_API_KEY", "NOT FOUND")
print(f"GROQ KEY CHECK: {_key[:10] if _key != 'NOT FOUND' else 'NOT FOUND'}")

app = FastAPI(title="AutoDiscussion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Store generated audio files temporarily
audio_store = {}

NICHE_CONTEXT = {
    "automobiles": "cars, automotive industry, racing, car brands and technology",
    "business": "startups, corporations, entrepreneurs, business strategies and failures",
    "finance": "crypto, stocks, investing, financial scandals and success stories",
    "technology": "tech companies, innovations, AI, gadgets and digital revolution",
    "history": "historical events, empires, wars, forgotten stories and mysteries",
    "science": "scientific discoveries, space, nature, experiments and breakthroughs",
    "sports": "athletes, teams, tournaments, rivalries and sporting legends",
    "truecrime": "crimes, heists, frauds, investigations and justice",
    "entertainment": "movies, music, celebrities, pop culture and industry secrets",
    "health": "fitness, medicine, mental health, nutrition and wellness",
    "politics": "political events, leaders, elections and geopolitical stories",
    "nature": "wildlife, environment, natural disasters and conservation",
}

HUMOR_EXAMPLES = """
You write in a witty, entertaining style — like a knowledgeable friend who tells stories with humor.
Think: MrBeast storytelling meets stand-up comedy meets documentary narration.

ROAST style:
- "They had one job. They managed to mess that up too."
- "The plan was brilliant. The execution, not so much."
- "Nobody saw it coming. Except everyone who was paying attention."
- "It worked perfectly — until it absolutely didn't."

RELATABLE style:
- "This is the kind of story your history teacher was too scared to tell you"
- "Imagine losing a billion dollars and calling it a learning experience"
- "The difference between genius and stupidity is that genius has limits"
- "Sometimes the most obvious answer is the one everyone ignores"

HOOK openers:
- "Nobody talks about this, and that's exactly the problem"
- "This story will change how you see everything"
- "Most people believe the official version. They shouldn't."
- "This happened 10 years ago. The world still hasn't recovered."
- "You think you know this story. You don't."

DRAMATIC reveals:
- "And that's when everything went wrong"
- "What happened next, nobody predicted"
- "The truth was hiding in plain sight the entire time"
- "One decision changed everything"
"""

@app.get("/")
def root():
    return {"status": "AutoDiscussion API running"}

# ── MAIN GENERATE ENDPOINT ─────────────────────────────────────────────────────
@app.post("/generate")
async def generate(request: dict):
    topic        = request.get("topic", "")
    content_type = request.get("content_type", "story")
    notes        = request.get("notes", "")

    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")

    niche = request.get("niche", "automobiles")
    niche_context = NICHE_CONTEXT.get(niche, "general topics")

    system_prompt = f"""You are a viral YouTube script writer for faceless channels covering any topic.
{HUMOR_EXAMPLES}

Return ONLY valid JSON, nothing else:

{{
  "title": "YouTube video title (clickbait, under 60 chars)",
  "description": "YouTube description (150 words, SEO optimized)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
  "hook": "First 15 seconds — dramatic + funny opening line that hooks viewers instantly",
  "hook_alternatives": ["alternative hook 1", "alternative hook 2", "alternative hook 3"],
  "script": "Full narration script (600-800 words). Pure narration, no camera directions. Add witty lines naturally.",
  "scenes": [
    {{
      "id": 1,
      "narration": "Narration for this scene (2-3 sentences max)",
      "photo_keyword": "Specific Pexels search term matching exactly what is discussed",
      "pause_after": false
    }}
  ],
  "short_hook": "90-second standalone version for Shorts/Reels — punchy and witty"
}}

Rules:
- content_type: {content_type}
- niche/topic area: {niche_context}
- 15-18 scenes for 8-10 minute video
- pause_after: true only for dramatic moments, shocking reveals
- photo_keyword must match EXACTLY what is being discussed (engine scene → engine photo, wheel scene → wheel photo)
- At least 1 funny/witty line per 3 scenes
- {f'Extra notes: {notes}' if notes else ''}"""

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
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

    import re, json
    clean = re.sub(r"```json|```", "", raw).strip()
    data = json.loads(clean)

    words = len(data.get("script", "").split())
    minutes = round(words / 130)

    return {
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "tags": data.get("tags", []),
        "hook": data.get("hook", ""),
        "hook_alternatives": data.get("hook_alternatives", []),
        "script": data.get("script", ""),
        "scenes": data.get("scenes", []),
        "short_hook": data.get("short_hook", ""),
        "words": words,
        "duration": f"{minutes} min",
        "scenes_count": len(data.get("scenes", [])),
    }

# ── AUDIO GENERATION ENDPOINT ──────────────────────────────────────────────────
@app.post("/audio")
async def generate_audio(request: dict):
    script = request.get("script", "")
    if not script:
        raise HTTPException(status_code=400, detail="Script is required")

    audio_id = str(uuid.uuid4())[:8]
    audio_path = f"/tmp/audio_{audio_id}.mp3"

    import edge_tts
    communicate = edge_tts.Communicate(
        script,
        voice="en-US-GuyNeural",
        rate="+15%",
        volume="+0%"
    )
    await communicate.save(audio_path)

    audio_store[audio_id] = audio_path
    return {"audio_id": audio_id}

# ── AUDIO DOWNLOAD ENDPOINT ────────────────────────────────────────────────────
@app.get("/audio/{audio_id}")
def download_audio(audio_id: str):
    path = audio_store.get(audio_id)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=f"autodiscussion_{audio_id}.mp3"
    )
