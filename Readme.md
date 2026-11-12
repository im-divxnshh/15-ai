# NOVA OS / 15-AI

NOVA coordinates fourteen specialist agents. The workspace provides chats, editable mission plans, queued execution, files, memory, tasks, routines, approvals and Telegram delivery.

The active services are Groq, Firebase Auth/Firestore, Upstash Redis, Neon PostgreSQL and Cloudflare R2. Configure private credentials in `backend/.env` and public Firebase/backend settings in `frontend/.env.local`.

Use Python 3.12+ and Node 22+. Install dependencies if needed:

```bash
backend/venv/bin/python -m pip install -r backend/requirements.txt
npm install --prefix frontend
```

Start the backend from the project root:

```bash
backend/venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

In another terminal:

```bash
cd frontend
npm run dev
```

Open [the workspace](http://localhost:3000/workspace), [the public office](http://localhost:3000/office), or [API docs](http://127.0.0.1:8000/docs).

[Startup, missions, Telegram and production commands](docs/RUNNING.md) explain daily operation. [API documentation](docs/API.md) and [the OpenAPI contract](docs/openapi.json) describe the backend.

For a production frontend, run `npm run build` and `npm run start` in `frontend`. Dockerfiles and `compose.yaml` are included. The backend must run continuously for queued work and Telegram commands.
