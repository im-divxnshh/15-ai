# Environment audit

All values remain private. Presence and code references do not establish live connectivity.

The current audit covers 24 backend fields and five public frontend fields. Storage fields are referenced by the Redis, Firebase, Neon and R2 adapters. SQLite fallback is disabled.

| File | Field | Value | Integration |
|---|---|---|---|
| backend/.env | GROQ_API_KEY | Present | referenced |
| backend/.env | GROQ_MODEL | Present | referenced |
| backend/.env | NOVA_LLM_MODEL | Present | referenced |
| backend/.env | FIREBASE_PROJECT_ID | Present | referenced |
| backend/.env | FIREBASE_CREDENTIALS | Present | referenced |
| backend/.env | SYSTEM_ACCESS_USER_ID | Present | referenced |
| backend/.env | STORAGE_BACKEND | Present | referenced |
| backend/.env | UPSTASH_REDIS_REST_URL | Present | referenced |
| backend/.env | UPSTASH_REDIS_REST_TOKEN | Present | referenced |
| backend/.env | NEON_URL | Present | referenced |
| backend/.env | FILE_STORAGE_BACKEND | Present | referenced |
| backend/.env | R2_ACCOUNT_ID | Present | referenced |
| backend/.env | R2_ACCESS_KEY_ID | Present | referenced |
| backend/.env | R2_SECRET_ACCESS_KEY | Present | referenced |
| backend/.env | R2_BUCKET | Present | referenced |
| backend/.env | NOTIFY_EMAIL | Present | referenced |
| backend/.env | SMTP_HOST | Present | referenced |
| backend/.env | SMTP_PORT | Present | referenced |
| backend/.env | SMTP_USER | Present | referenced |
| backend/.env | SMTP_PASSWORD | Present | referenced |
| backend/.env | SMTP_FROM | Present | referenced |
| backend/.env | TELEGRAM_BOT_TOKEN | Present | referenced |
| backend/.env | TELEGRAM_CHAT_ID | Present | referenced |
| backend/.env | CORS_ORIGINS | Present | referenced |
| frontend/.env.local | NEXT_PUBLIC_BACKEND_URL | Present | referenced |
| frontend/.env.local | NEXT_PUBLIC_FIREBASE_API_KEY | Present | referenced |
| frontend/.env.local | NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN | Present | referenced |
| frontend/.env.local | NEXT_PUBLIC_FIREBASE_PROJECT_ID | Present | referenced |
| frontend/.env.local | NEXT_PUBLIC_FIREBASE_APP_ID | Present | referenced |

## Connection evidence

Latest live report at 2026-11-12T19:38:18.377342+00:00. Passed: groq, upstash, neon, r2. Failed: firebase, email. Telegram remains deferred. Code/configuration changes require a fresh connection check; actual storage writes and notification delivery are separate checks.

Run `backend/venv/bin/python scripts/check_connections.py` from your own terminal to check the current values. It uses read-only service probes and SMTP authentication; it sends no email or Telegram message. Delivery needs a later actual message test.

## Office UI

Open [the standalone office preview](../frontend/public/office-preview.html) to inspect all 15 cabins, themes and capabilities without a backend or production build. The frontend homepage and `/office` show the public office; `/workspace` provides authenticated controls. Select Friday and click Preview assignment to see the labelled walking demo. The public preview is a labelled demo. Authenticated office movement consumes actual backend events when connected.

The standalone preview can be served outside the managed workspace with:

```bash
python3 -m http.server 3001 --bind 127.0.0.1 --directory frontend/public
```

Then open `http://localhost:3001/office-preview.html`. Standalone desktop/mobile browser checks passed in the terminal verification run; see docs/VERIFICATION.md for workspace/browser limitations.

Run `node scripts/render-office-preview.cjs` to refresh the HTML from the actual React office components. The production build is gated until required live connection checks pass.
