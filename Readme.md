# 15-AI — JARVIS Office 🧠

**"Build for comfort"** — a personal AI office of **15 agents** with one mission: handle your every work.

Talk to it in **Hindi, English, or natural Hinglish** — it replies the way an Indian friend actually talks.

![layers](https://img.shields.io/badge/stack-100%25%20FREE-success)

## What is this?

An isometric **2D cyberpunk office** where 15 AI workers (JARVIS + 14 agents) sit at their desks and work for you in real time. You chat (text or voice), JARVIS's brain classifies → plans → risk-checks → executes via agents/tools → answers with memory of everything.

| Layer | Agents |
|---|---|
| 🧠 Supreme Control | **JARVIS** (orchestrates all) |
| Intelligence | Friday · Drake · Stark · Athena |
| Execution | Michel (CTO) · Oracle · Zeus |
| Human Optimization | Kratos · Pepper · Gaya |
| Communication | Veronica · Echo |
| Lifestyle | Gecko · Elena |

## Tech stack (all free tier)

| Component | Service |
|---|---|
| Frontend | Next.js 16 + Tailwind 4 + Socket.IO client |
| Backend | Python FastAPI + Socket.IO |
| **LLM Brain** | **GLM** (OpenAI-compatible — bring your key) |
| Primary DB | Firebase Firestore *(falls back to local JSON if unset)* |
| Vector DB | Neon Postgres + pgvector *(falls back to in-memory if unset)* |
| Embeddings | Free local embedder *(GLM embeddings optional)* |
| File storage | Cloudflare R2 *(falls back to local disk if unset)* |
| Web search | GLM brain (same key — no extra API) |
| STT (voice → text) | Groq Whisper free tier |
| TTS (text → voice) | Browser Web Speech API (hi-IN / en-IN) |

> **Zero-config runs too**: with only `GLM_API_KEY` set, everything works locally with fallback stores.

## Quick start

```bash
# 1. Backend
cd backend
python3 -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit .env — set GLM_API_KEY + GLM_BASE_URL
uvicorn main:app --reload   # http://localhost:8000 (docs at /docs)

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

Open **http://localhost:3000** — the office loads, JARVIS sits in the glowing command pod, 14 workers at their desks.

## Setup: the one required key

```env
GLM_API_KEY=your-key-here
GLM_BASE_URL=https://api.z.ai/api/paas/v4   # or your custom endpoint
GLM_MODEL=glm-4.6
```

## Optional free services (all have free tiers)

### Firebase (Firestore) — persistent conversations/tasks across restarts
1. console.firebase.google.com → create project (Spark/free plan)
2. Project settings → Service accounts → generate private key JSON
3. Put it in `.env` as ONE line:
```bash
# macOS: python3 -c "import json;print(json.dumps(json.load(open('service-account.json'))))"
FIREBASE_CREDENTIALS={"type": "service_account", ...}
FIREBASE_PROJECT_ID=your-project-id
```

### Neon (vector memory — "remember everything" semantic search)
1. neon.tech → free account → create database
2. Copy the connection string:
```env
NEON_URL=postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
```
(pgvector extension + `memories` table are created automatically on first use.)

### Cloudflare R2 (file storage)
1. dash.cloudflare.com → R2 → create bucket + API token
```env
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET=15-ai
```

### Groq (voice STT — free)
```env
GROQ_API_KEY=gsk_...
```

## How to use

- **Chat**: type in the right panel — Hinglish/Hindi/English, whatever. JARVIS replies with voice (🔊 toggle).
- **Voice**: 🎤 button, bol daalo — Whisper transcribes (Hindi + English mix).
- **Direct agent chat**: click any worker's desk → chat goes straight to that agent (Drake for research, Kratos for gym motivation, Pepper for journaling...).
- **Files**: 📎 upload a PDF/notes/code — it gets indexed into memory; then ask questions about it.
- **Reminders/tasks**: "remind me kal 9 baje meeting hai" → task created, visible at `GET /api/tasks`.
- **Live office**: workers glow + show ⚡ status bubbles when working; Mission Control feed (left) shows every event.

## Architecture (maps to the JARVIS Master Roadmap — all 15 milestones ✅)

```
User → Chat/Voice
        ↓
   ┌─ BRAIN (M01) ─────────────────────────────┐
   │ Classifier → Planner → Risk Engine         │
   │ → Reasoner → Tools → Response Builder      │
   └────────────┬───────────────────────────────┘
                ↓
   MEMORY (M02): Neon pgvector + Firestore + fallbacks
                ↓
   RUNTIME (M03/07/08): Orchestrator → Dispatcher →
   Priority Task Queue → Task Executor
                ↓
   15 AGENTS (M15) + TOOLS (M09): web_search, memory,
   create_task, save_memory  → Event Bus → Socket.IO
                ↓
   2D OFFICE UI: live desks, status bubbles, feed
```

## API quick reference

| Endpoint | What |
|---|---|
| `POST /api/chat` | chat with JARVIS or a specific agent |
| `GET /api/agents` | office roster + live status |
| `GET/POST/PATCH /api/tasks` | your task list |
| `GET /api/memory/search?q=` | search long-term memory |
| `POST /api/files/upload` | upload + index a file |
| `POST /api/voice/stt` | voice → text (Groq Whisper) |
| `GET/POST /api/workflows` | automations (manual/phrase/schedule triggers) |
| `GET /api/analytics` | office stats |
| `GET /api/system/health` | which services are live |

## Notes

- `USER_NAME=Boss` in `.env` — agents call you by this.
- Set `APP_TOKEN` in backend env to require `Authorization: <token>` on APIs.
- Data without Firebase lives in `backend/data/*.json` — delete to reset.
