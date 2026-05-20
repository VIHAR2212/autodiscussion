from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uuid
import os
import httpx
from pipeline import run_pipeline

app = FastAPI(title="AutoDiscussion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

jobs = {}

@app.get("/")
def root():
    return {"status": "AutoDiscussion API running"}

# ── SCRIPT ENDPOINT (called by frontend) ──────────────────────────────────────
@app.post("/script")
async def generate_script(request: dict):
    topic        = request.get("topic", "")
    content_type = request.get("content_type", "comparison")
    market       = request.get("market", "india")
    notes        = request.get("notes", "")

    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")

    market_labels = {
        "india": "Indian",
        "global": "global",
        "us": "American",
        "uk": "British"
    }

    system_prompt = f"""You are a viral YouTube script writer for a faceless car channel. Write engaging scripts in this exact format:

HOOK (15 seconds): A dramatic, curiosity-inducing opening line.
INTRO: Brief setup of what the video covers.
SECTION 1-4: Each section has a bold header + 2-3 paragraphs of narration. For comparisons use "Round 1", "Round 2" etc. For rankings use numbered tiers.
CTA: End with "Which would you choose? Comment below. Subscribe for more car content."

Rules:
- Write as pure narration (no camera directions)
- Each paragraph = one photo scene
- Short punchy sentences. No filler.
- Target {market_labels.get(market, 'global')} car market
- Content type: {content_type}
- Total length: ~600-800 words

After the script, add a line: "PHOTOS NEEDED: [comma-separated list of 8-10 photo search keywords for Pexels]"
"""

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "max_tokens": 1000,
                "temperature": 0.8,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f'Write a YouTube script about: "{topic}". {("Additional notes: " + notes) if notes else ""}'}
                ]
            }
        )
        response.raise_for_status()
        data = response.json()

    script_text = data["choices"][0]["message"]["content"]
    words = len(script_text.split())
    minutes = round(words / 130)
    photos = min(script_text.count('\n\n') + 6, 12)

    return {
        "script": script_text,
        "words": words,
        "duration": f"{minutes}M",
        "photos": photos
    }

# ── VIDEO PIPELINE ENDPOINTS ───────────────────────────────────────────────────
@app.post("/generate")
async def generate_video(request: dict, background_tasks: BackgroundTasks):
    topic        = request.get("topic", "")
    content_type = request.get("content_type", "comparison")
    market       = request.get("market", "india")
    notes        = request.get("notes", "")
    format_type  = request.get("format", "both")

    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "progress": 0, "message": "Starting..."}
    background_tasks.add_task(run_job, job_id, topic, content_type, market, notes, format_type)
    return {"job_id": job_id}

@app.get("/status/{job_id}")
def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/download/{job_id}/{file_type}")
def download_video(job_id: str, file_type: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Video not ready yet")
    path = job.get(f"{file_type}_path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="video/mp4", filename=f"autodiscussion_{file_type}_{job_id[:8]}.mp4")

async def run_job(job_id, topic, content_type, market, notes, format_type):
    try:
        def update(progress, message):
            jobs[job_id].update({"progress": progress, "message": message, "status": "running"})
        result = await run_pipeline(topic, content_type, market, notes, format_type, update)
        jobs[job_id].update({"status": "done", "progress": 100, "message": "Video ready!", **result})
    except Exception as e:
        jobs[job_id].update({"status": "error", "message": str(e)})
