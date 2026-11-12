# 15-AI / NOVA OS

NOVA leads a fifteen-robot office with fourteen specialists. The public homepage has connected private cabins, clickable capabilities, a walking assignment demo and persistent dark/light themes. `/workspace` provides authenticated chats, workflows, files, tasks, routines, approvals and delivery preferences. Voice features remain deferred.

The Redis/Firebase/Neon/R2 migration is implemented. **54 backend tests pass**, including actual Redis Lua and TLS/CORS regressions; five frontend tests, TypeScript and standalone desktop/mobile browser checks pass. Live Groq, Upstash, Neon and R2 access and a Groq completion passed. Firebase token refresh and SMTP certificate verification failed in the live run; CA-trust/CORS fixes await a focused rerun. The production build remains gated. [PLAN.md](PLAN.md) and [VERIFICATION.md](docs/VERIFICATION.md) record the actual evidence.

The active runtime uses Groq for AI, Firebase Auth/Firestore for identity and user documents, Upstash Redis for execution/state/events/outbox, Neon PostgreSQL/pgvector for document chunks, and private Cloudflare R2 objects for files. File vectors use local token hashes for lexical retrieval. No SQLite fallback is mounted.

## Preview and development

Open [office-preview.html](frontend/public/office-preview.html) directly. This standalone office needs no backend or credentials. Select a specialist and choose **Preview assignment** for a labelled animation demo. Run `node scripts/render-office-preview.cjs` to refresh it after UI changes.

Use Python 3.12+, Node 22+ and npm. Preserve the populated `backend/.env` and `frontend/.env.local`; backend credentials stay private, and Firebase Admin accepts inline JSON.

```bash
backend/venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/venv/bin/python scripts/audit_env.py
backend/venv/bin/python scripts/check_connections.py
```

Connection probes authenticate and read service configuration without sending AI completions, email or Telegram messages. Telegram is deferred unless `--include-telegram` is explicitly supplied. Production builds require a current passing report for all six required services.

```bash
backend/venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
cd frontend
npm run dev
```

Visit http://localhost:3000 for the office and `/workspace` for private controls. Redis elects the continuous worker; a replica without the lease stays in standby. Jobs continue after the browser closes. A restart or lost lease interrupts uncertain work for explicit review/retry. New accounts start with outgoing notification channels disabled.

## Verification and production

Run `backend/venv/bin/python scripts/verify_all.py` for the complete sequence and automatic PLAN.md updates. Use `--only backend,browser` to repeat selected checks, or `--local --only env,backend,office,transport,typescript,render` for sandbox-compatible checks. Live connections still gate the production build.

```bash
backend/venv/bin/python -m unittest discover -s backend/tests -v
backend/venv/bin/python backend/scripts/verify_storage.py
cd frontend
npm run test:office
npm run test:transport
node node_modules/typescript/bin/tsc --noEmit
npm run test:office:browser
npm run build
```

Run `verify_storage.py` after connection checks pass. It writes, reads and cleans up an isolated live Redis/Firestore/R2/Neon fixture, without AI calls or notifications. The default backend suite runs Redis Lua through fakeredis/lupa. `NOVA_STATE_TESTS=1` explicitly runs only disposable state logic and SDK/HTTP fixtures; it excludes the Redis Lua checks and cannot establish live readiness.

The production build is gated by `scripts/check_connections.py --require-verified`. After it passes, use `scripts/start-production.sh` or the provided Docker/Compose configuration. The backend must run continuously; durable data lives in managed services. Container deployment is unverified in this workspace.

A local Postman Groq simulation is saved in `postman/simulations/nova-runtime.sim.yaml`. Run it on port 4010 and set `NOVA_SIMULATION_URL=http://127.0.0.1:4010` for `backend/tests/check_simulation.py`. See the adjacent context file for assumptions and unresolved evidence. No simulation has been published or deployed.

The API contract is [openapi.json](docs/openapi.json), with [API documentation](docs/API.md) and interactive `/docs`. Run `python3 scripts/progress.py watch` to keep the plan synchronized with the tracker.
