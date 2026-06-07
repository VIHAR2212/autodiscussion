from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os, uuid, httpx, re, json, tempfile

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
audio_store = {}

# ── Niche context ──────────────────────────────────────────────────────────────
NICHE_CONTEXT = {
    "automobiles":   "cars, automotive industry, racing, car brands and technology",
    "business":      "startups, corporations, entrepreneurs, business strategies and failures",
    "finance":       "crypto, stocks, investing, financial scandals and success stories",
    "technology":    "tech companies, innovations, AI, gadgets and digital revolution",
    "history":       "historical events, empires, wars, forgotten stories and mysteries",
    "science":       "scientific discoveries, space, nature, experiments and breakthroughs",
    "sports":        "athletes, teams, tournaments, rivalries and sporting legends",
    "truecrime":     "crimes, heists, frauds, investigations and justice",
    "entertainment": "movies, music, celebrities, pop culture and industry secrets",
    "health":        "fitness, medicine, mental health, nutrition and wellness",
    "politics":      "political events, leaders, elections and geopolitical stories",
    "nature":        "wildlife, environment, natural disasters and conservation",
}

# ── BGM library ────────────────────────────────────────────────────────────────
BGM_LIBRARY = {
    "automobiles":   {"name": "Cinematic Drive",    "mood": "Epic, power, speed",              "pixabay_query": "cinematic epic orchestral drive",            "bpm": "120-140", "vibe": "🏎️ Full throttle energy"},
    "business":      {"name": "Corporate Tension",  "mood": "Suspense, drama, boardroom",       "pixabay_query": "corporate suspense background music",        "bpm": "90-110",  "vibe": "💼 Suits and stakes"},
    "finance":       {"name": "Market Pulse",       "mood": "Tense, analytical, rhythmic",      "pixabay_query": "electronic tension financial news background","bpm": "100-120", "vibe": "📈 Numbers under pressure"},
    "technology":    {"name": "Digital Pulse",      "mood": "Futuristic, curious, innovative",  "pixabay_query": "futuristic tech electronic ambient",          "bpm": "110-130", "vibe": "🤖 Silicon dreams"},
    "history":       {"name": "Epic Chronicles",    "mood": "Dramatic, grand, cinematic",       "pixabay_query": "epic cinematic orchestral history documentary","bpm": "80-100",  "vibe": "⚔️ Empires and echoes"},
    "truecrime":     {"name": "Dark Undertones",    "mood": "Eerie, suspenseful, thriller",     "pixabay_query": "dark suspense thriller investigation",        "bpm": "70-90",   "vibe": "🔍 Something's off..."},
    "sports":        {"name": "Champion's Rise",    "mood": "Hype, energy, triumphant",         "pixabay_query": "epic sports hype motivational background",    "bpm": "130-150", "vibe": "🏆 Game on"},
    "science":       {"name": "Discovery Wave",     "mood": "Wonder, curiosity, exploration",   "pixabay_query": "ambient discovery science documentary",       "bpm": "85-105",  "vibe": "🔬 Mind expanding"},
    "entertainment": {"name": "Showtime",           "mood": "Fun, bright, energetic",           "pixabay_query": "upbeat pop background entertainment",        "bpm": "115-135", "vibe": "🎬 Lights, camera, action"},
    "health":        {"name": "Calm Focus",         "mood": "Serene, motivational, clear",      "pixabay_query": "calm motivational background wellness",       "bpm": "75-95",   "vibe": "❤️ Mind and body"},
    "politics":      {"name": "Power Play",         "mood": "Tension, stakes, gravitas",        "pixabay_query": "dramatic news background cinematic tension",  "bpm": "80-100",  "vibe": "🌍 The world watching"},
    "nature":        {"name": "Earth Pulse",        "mood": "Vast, peaceful, awe-inspiring",    "pixabay_query": "nature ambient orchestral documentary",       "bpm": "70-90",   "vibe": "🌿 Breath of the wild"},
}

def get_bgm(niche: str) -> dict:
    return BGM_LIBRARY.get(niche, BGM_LIBRARY["business"])

HUMOR_EXAMPLES = """
Style: 70% sharp information, 30% wit and personality. Never boring. Think MrBeast storytelling meets stand-up comedy meets documentary narration.

ROAST lines: "They had one job. They managed to mess that up too." | "The plan was brilliant. The execution, not so much."
RELATABLE: "This is the story your teacher was too scared to tell you" | "Imagine losing a billion dollars and calling it a learning experience"
DRAMATIC: "And that's when everything went wrong" | "One decision changed everything"
"""

SENTENCE_TYPE_GUIDE = """
Every sentence in the `sentences` array must have one of these types:
- "narration" → factual, informational core content
- "dramatic"  → high-stakes reveal, shocking fact, tension moment  
- "funny"     → wit, irony, sarcasm, relatable joke (never cringe)
- "pause"     → use text "..." for breathing room after dramatic/funny lines
Pattern: every 3-4 narration sentences → 1 funny or dramatic → optional pause
"""

# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "AutoDiscussion API v2.0 running", "endpoints": ["/generate", "/audio", "/audio/{id}"]}

# ── Generate ──────────────────────────────────────────────────────────────────
@app.post("/generate")
async def generate(request: dict):
    topic        = request.get("topic", "").strip()
    content_type = request.get("content_type", "story")
    notes        = request.get("notes", "")
    niche        = request.get("niche", "automobiles")

    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")

    niche_context = NICHE_CONTEXT.get(niche, "general topics")

    system_prompt = f"""You are a viral YouTube script writer for faceless channels.
{HUMOR_EXAMPLES}
{SENTENCE_TYPE_GUIDE}

Return ONLY valid JSON, nothing else. No markdown fences.

{{
  "title": "YouTube video title (clickbait, under 60 chars)",
  "description": "YouTube description (150 words, SEO optimized, includes CTA)",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
  "hook": "First 15 seconds — dramatic + funny opening line that hooks viewers instantly",
  "hook_alternatives": ["alternative hook 1", "alternative hook 2", "alternative hook 3"],
  "short_hook": "15-word max punchy hook for Shorts/Reels",
  "sentences": [
    {{"text": "Nobody saw this coming.", "type": "dramatic"}},
    {{"text": "Well, except the accountants.", "type": "funny"}},
    {{"text": "...", "type": "pause"}},
    {{"text": "In 2008 the company had $4 billion in assets.", "type": "narration"}}
  ],
  "photo_keywords": ["keyword1","keyword2","keyword3","keyword4","keyword5","keyword6","keyword7","keyword8","keyword9","keyword10"],
  "scenes": [
    {{
      "id": 1,
      "narration": "Narration for this scene (2-3 sentences max)",
      "photo_keyword": "Specific Pexels search term matching exactly what is discussed",
      "pause_after": false
    }}
  ]
}}

Rules:
- content_type: {content_type}
- niche: {niche_context}
- sentences: 20-35 items; follow narration→dramatic/funny→pause rhythm
- scenes: 15-18 for 8-10 minute video
- photo_keywords: 8-12 specific Pexels search terms (top-level, from scenes)
- pause_after: true only for dramatic moments
- At least 1 funny/witty line per 3 scenes
{f'- Extra notes: {notes}' if notes else ''}"""

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": f"Write a YouTube script about: {topic}"}
                ],
                "temperature": 0.9,
                "max_tokens": 4000,
            }
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]

    # Parse — strip fences if model adds them
    clean = re.sub(r"```json|```", "", raw).strip()
    # Find outermost JSON object
    match = re.search(r'\{[\s\S]*\}', clean)
    if not match:
        raise HTTPException(status_code=500, detail="Model returned invalid JSON")
    data = json.loads(match.group())

    # Validate + fix sentences
    valid_types = {"narration", "dramatic", "funny", "pause"}
    sentences = []
    for s in data.get("sentences", []):
        if isinstance(s, dict) and "text" in s:
            t = s.get("type", "narration")
            sentences.append({"text": s["text"], "type": t if t in valid_types else "narration"})

    # Build full script from sentences (skip pauses)
    full_script = " ".join(s["text"] for s in sentences if s["type"] != "pause")

    scenes = data.get("scenes", [])

    return {
        # Core output
        "title":             data.get("title", ""),
        "description":       data.get("description", ""),
        "tags":              data.get("tags", []),
        "hook":              data.get("hook", ""),
        "hook_alternatives": data.get("hook_alternatives", []),
        "short_hook":        data.get("short_hook", ""),
        # NEW: tagged sentence array
        "sentences":         sentences,
        # Derived full script (for audio / display)
        "script":            full_script,
        # Media
        "photo_keywords":    data.get("photo_keywords", [s.get("photo_keyword","") for s in scenes]),
        "scenes":            scenes,
        "bgm_suggestion":    get_bgm(niche),
        # Stats
        "words":             len(full_script.split()),
        "duration":          f"{round(len(full_script.split()) / 130)} min",
        "scenes_count":      len(scenes),
        "sentence_count":    len(sentences),
    }

# ── Audio generate ────────────────────────────────────────────────────────────
@app.post("/audio")
async def generate_audio(request: dict):
    script = request.get("script", "") or request.get("text", "")
    if not script:
        raise HTTPException(status_code=400, detail="script is required")

    audio_id   = str(uuid.uuid4())[:8]
    audio_path = f"/tmp/audio_{audio_id}.mp3"

    import edge_tts
    communicate = edge_tts.Communicate(
        script,
        voice=request.get("voice", "en-US-GuyNeural"),
        rate="+15%",
    )
    await communicate.save(audio_path)
    audio_store[audio_id] = audio_path
    return {"audio_id": audio_id}

# ── Audio download ─────────────────────────────────────────────────────────────
@app.get("/audio/{audio_id}")
def download_audio(audio_id: str):
    path = audio_store.get(audio_id)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path, media_type="audio/mpeg", filename=f"autodiscussion_{audio_id}.mp3")
