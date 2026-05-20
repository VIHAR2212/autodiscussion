from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uuid
import os
from pipeline import run_pipeline

app = FastAPI(title="AutoDiscussion Pipeline API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store
jobs = {}

@app.get("/")
def root():
    return {"status": "AutoDiscussion API running"}

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
        jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": "Video ready!",
            **result
        })
    except Exception as e:
        jobs[job_id].update({"status": "error", "message": str(e)})