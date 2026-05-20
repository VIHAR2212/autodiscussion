# 🚗 AutoDiscussion — AI Car Channel Pipeline

> *Every car has a story.*

Full AI pipeline to generate YouTube videos + Shorts for the AutoDiscussion channel.
Haunted stories. Brand legends. True crime. Comparisons. New launches.

---

## 📁 Project Structure

```
autodiscussion/
├── backend/
│   ├── main.py          → FastAPI server (job queue, download endpoints)
│   ├── pipeline.py      → Full video pipeline (script → voice → photos → MP4)
│   ├── requirements.txt → Python dependencies
│   └── .env.example     → API keys template
├── frontend/
│   └── index.html       → AutoReel website (script generator UI)
├── assets/
│   └── bg_music.mp3     → Drop royalty-free music here (pixabay.com/music)
└── README.md
```

---

## 🎯 Channel Content Pillars

| Pillar | Style | Example |
|--------|-------|---------|
| 👻 Haunted | Horror narration | "The Ghost Truck of NH44" |
| 🏆 Brand Legends | Rise/fall stories | "How Lamborghini Was Born From Revenge" |
| 💀 True Crime | Dark drama | "The Getaway Car That Was Never Found" |
| ⚔️ Comparisons | Informative | "Tata Punch vs Fronx — Who Actually Wins" |
| 🚀 New Launches | News style | "Everything About Tata Sierra 2026" |

---

## ⚡ Free Tool Stack (₹0 Forever)

| Tool | Purpose |
|------|---------|
| Groq (llama-3.3-70b) | Script generation |
| Edge TTS (Microsoft) | AI Voiceover |
| Pexels API | HD Car Photos |
| FFmpeg | Video assembly + Ken Burns |
| FastAPI | Backend server |
| Render.com | Free hosting |

---

## 🚀 Setup (After Exams!)

### 1. Install FFmpeg
```bash
# Ubuntu / Render
sudo apt install ffmpeg

# Mac
brew install ffmpeg

# Windows
winget install FFmpeg
```

### 2. Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. Add API Keys
```bash
cp .env.example .env
# Edit .env:
# GROQ_API_KEY → https://console.groq.com (free)
# PEXELS_API_KEY → https://www.pexels.com/api (free)
```

### 4. Add background music
```
Download any cinematic/dark royalty-free MP3 from pixabay.com/music
Save as: assets/bg_music.mp3
```

### 5. Run the server
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 6. Open the website
```
Open frontend/index.html in browser
Point API calls to http://localhost:8000
```

---

## 📡 API Reference

### Generate Video
```http
POST /generate
Content-Type: application/json

{
  "topic": "The Ghost Truck of NH44",
  "content_type": "haunted",
  "market": "india",
  "notes": "Make it scary, Indian highways",
  "format": "both"
}

Response: { "job_id": "abc123" }
```

### Check Progress
```http
GET /status/{job_id}

Response:
{ "status": "running", "progress": 65, "message": "Assembling video..." }
{ "status": "done", "progress": 100, "title": "...", "long_path": "...", "short_path": "..." }
```

### Download Video
```http
GET /download/{job_id}/long    → 1920x1080 YouTube MP4
GET /download/{job_id}/short   → 1080x1920 Shorts/Reels MP4
```

---

## 🎬 Content Types
- `comparison` → Car A vs Car B
- `news` → Industry news
- `launch` → New car launch
- `features` → Feature deep dive
- `ranking` → Tier list
- `story` → Brand history
- `haunted` → Horror/ghost stories 👻
- `truecrime` → Dark true crime stories

---

## 🌐 Deploy to Render (Free)
1. Push to GitHub
2. New Web Service → connect repo
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add env vars in Render dashboard

---

## 📱 Output Formats
- **Long video** → 1920x1080 (16:9), 8-12 min, YouTube
- **Short/Reel** → 1080x1920 (9:16), 60-90 sec, Shorts + Reels

---

*Good luck on end sems Vihar! 🎓 Come back and we launch AutoDiscussion! 🚗👻*
