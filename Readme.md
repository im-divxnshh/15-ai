# 15-AI / NOVA OS

NOVA is the CEO and orchestrator of a 15-robot office. The public homepage shows a connected 2D floor with fifteen private cabins, furnished desks, shared walkways, clickable agent details, and persistent dark/light themes. Voice work is deferred.

## See the office now

Open **frontend/public/office-preview.html** in your browser. It is standalone and needs no backend, credentials, build, or external assets. Choose Friday and click **Preview assignment**: the robot walks to NOVA, collects the brief, and returns to its cabin. A four-stage assignment flow follows the animation. Stop/replay controls are included. This is a labelled animation demo; it sends no AI tasks or notifications.

The floor plan scrolls to keep cabin text readable on smaller screens. Switch to **Cabin list** for a compact mobile view. Click any cabin for its role and configured capabilities.

If your browser needs an HTTP origin, run this from your own terminal:

```bash
python3 -m http.server 3001 --bind 127.0.0.1 --directory frontend/public
```

Then open http://localhost:3001/office-preview.html. Refresh the standalone file after UI changes with `node scripts/render-office-preview.cjs`.

## Current state

**3/27 work items complete; 24 remaining.** [PLAN.md](PLAN.md) generates counts from project-progress.json. UI code is implemented; real browser visual verification remains pending because Chrome exits before page checks in this managed workspace.

The previous application used SQLite. The requested Upstash/Firebase/Neon/R2 migration is **pending**, and SQLite fallback is disabled. The backend does not start the worker or accept private data operations until storage is implemented. Existing queue, workflow, outbox and tool modules need integration and retesting. Earlier test/build passes do not verify this new architecture.

Intended stack: Next.js 16 / React 19 / TypeScript, FastAPI / Python, Groq only for AI, Firebase for authentication and user data, Upstash Redis for durable execution/state/cache, Neon PostgreSQL/pgvector for chunk-based RAG, Cloudflare R2 for files, and SMTP/Telegram for notifications.

## Configuration and connection checks

All 24 backend and five frontend fields have values; private values were preserved. [ENV-AUDIT.md](docs/ENV-AUDIT.md) lists actual code references and remaining storage integration. No private keys belong in the frontend. Firebase Admin credentials use inline JSON in backend/.env, with no credential-file path.

```bash
backend/venv/bin/python scripts/audit_env.py
backend/venv/bin/python scripts/check_connections.py --offline
backend/venv/bin/python scripts/check_connections.py
```

Offline validation cannot unlock builds. Live probes check Groq models, Firebase Admin/Auth, Upstash PING, Neon SELECT 1, R2 bucket access, SMTP TLS authentication and Telegram bot/chat lookup. They send no AI completion, email or Telegram message. Previous live probes failed at network/DNS access; credentials have not been verified or rejected. Actual notification delivery remains unverified.

Production `npm run build` requires a current passing live connection report. Do not copy examples over filled env files. Restart the backend after private env changes; restart/rebuild the frontend after public env changes.

## Application routes and local startup

The frontend homepage `/` and `/office` show the public office. `/workspace` provides the Firebase-authenticated dashboard, agent chats and workflow controls. Public cabin previews expose no private history. When storage is available, office assignment movement consumes actual agent-start events, skips the initial historical snapshot, and stops on connection loss. Animation stages visualize the hand-off and do not represent execution progress.

Use Python 3.12+, Node 22+, and npm. Dependencies are already present in this workspace; for a new checkout:

```bash
python3 -m venv backend/venv
backend/venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
```

For frontend development from your own terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:3000. The office is visible without sign-in. The authenticated workspace requires your Firebase configuration and a connected backend.

```bash
backend/venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

Health and docs are available at `/api/health` and `/docs`. The API can expose the public roster and configuration while private operations return 503 for pending storage. This command currently does **not** enable continuous execution. Compose/Docker files are reference configurations awaiting migration and container verification; Docker is unavailable here.

## Verification

```bash
cd frontend
npm run test:office
npm run test:transport
node node_modules/typescript/bin/tsc --noEmit
node ../scripts/render-office-preview.cjs
npm run test:office:browser
```

The three office tests verify all specialist paths reach the CEO and return without crossing other cabins, the animation/cancellation/reduced-motion lifecycle, and event-based movement without duplicate routing animations. Two transport tests cover SSE reconnect cursors/authentication and visible offline/validation errors. TypeScript and standalone rendering passed. The browser runner targets only the standalone file, checks desktop/mobile themes and interactions, and saves screenshots only after actual successful page checks. Chrome closed before these checks; no screenshots or visual pass are claimed.

See [verification evidence](docs/VERIFICATION.md). The full backend/runtime suite must be adapted after storage migration. Run `python3 scripts/progress.py watch` to regenerate PLAN.md whenever the tracker changes. The active API contract is [docs/openapi.json](docs/openapi.json); implemented handlers remain storage-gated.
