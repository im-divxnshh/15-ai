# Run NOVA

Use Python 3.12+ and Node 22+. Backend configuration is in `backend/.env`; public frontend configuration is in `frontend/.env.local`.

Start the backend from the project root:

```bash
backend/venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

Start the frontend in a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:3000/workspace and continue with Google. Backend health is http://127.0.0.1:8000/api/health; interactive API documentation is http://127.0.0.1:8000/docs. The public office preview is http://localhost:3000/office.

`NEXT_PUBLIC_BACKEND_URL` must point to the backend, and `CORS_ORIGINS` must include the frontend origin. Restart the relevant server after changing an environment file.

## Missions and results

In Missions, Batch creates one task per line. NOVA plan generates an editable breakdown from a larger brief. Include the actual product, audience, constraints and source information in that brief. Each agent receives the original brief, its individual instruction and completed dependency results.

Sequential mode passes the preceding result forward. Parallel mode runs independent tasks together, subject to dependencies and the selected concurrency. Queue the plan and expand each task's Instruction & result to read its response. A completed response can still ask for missing information; the status does not independently assess output quality.

If Groq returns HTTP 429, check the model's quota in Groq Console and wait for it to reset before choosing Retry unsuccessful tasks. Completed tasks are preserved. Use sequential mode or concurrency 1 to reduce bursts.

## Telegram

The backend must keep running for Telegram commands and notifications. With the backend stopped, bind the bot to the Firebase UID used by your Google login:

```bash
backend/venv/bin/python backend/scripts/setup_telegram.py --enable --user YOUR_FIREBASE_UID
```

Find your UID in Firebase Console under Authentication → Users. If you configure an optional private `APP_TOKEN` login, the setup script's default `owner` binding corresponds to that login.

After starting the backend, open your configured bot and send `/start`, `/status`, then `/task Write a three-point daily plan`. `/tasks` lists workflows; `/run WORKFLOW_ID` shows results. First activation skips old pending messages, so send new commands after startup. Only the configured private chat can control the bound account.

Delivery settings control automatic notifications. Telegram must be enabled with the configured chat ID. The bot continues working after the browser closes.

## Configuration helpers

From the project root:

```bash
backend/venv/bin/python scripts/check_connections.py --offline
backend/venv/bin/python scripts/check_connections.py --include-telegram
backend/venv/bin/python backend/scripts/import_firebase_key.py PATH_TO_SERVICE_ACCOUNT_JSON
```

The offline command checks values without contacting services. The live command checks service access without AI completions, email or Telegram messages; it prints results without creating reports. Importing a Firebase key preserves other environment values.

## Production

```bash
cd frontend
npm run build
npm run start
```

Alternatively, `scripts/start-production.sh` runs the standalone frontend output after a build. Dockerfiles and `compose.yaml` support container deployment. A successful frontend build does not establish that the configured external services are available.

Stop each server with Ctrl+C.
