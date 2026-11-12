# Environment audit

All values remain private. Presence and code references do not establish live connectivity.

The current audit covers 24 backend fields and five public frontend fields. Nine storage fields await runtime integration. SQLite fallback is disabled.

| File | Field | Value | Integration |
|---|---|---|---|
| backend/.env | GROQ_API_KEY | Present | referenced |
| backend/.env | GROQ_MODEL | Present | referenced |
| backend/.env | NOVA_LLM_MODEL | Present | referenced |
| backend/.env | FIREBASE_PROJECT_ID | Present | referenced |
| backend/.env | FIREBASE_CREDENTIALS | Present | referenced |
| backend/.env | SYSTEM_ACCESS_USER_ID | Present | referenced |
| backend/.env | STORAGE_BACKEND | Present | migration pending |
| backend/.env | UPSTASH_REDIS_REST_URL | Present | migration pending |
| backend/.env | UPSTASH_REDIS_REST_TOKEN | Present | migration pending |
| backend/.env | NEON_URL | Present | migration pending |
| backend/.env | FILE_STORAGE_BACKEND | Present | migration pending |
| backend/.env | R2_ACCOUNT_ID | Present | migration pending |
| backend/.env | R2_ACCESS_KEY_ID | Present | migration pending |
| backend/.env | R2_SECRET_ACCESS_KEY | Present | migration pending |
| backend/.env | R2_BUCKET | Present | migration pending |
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

The last live checks encountered connection/network errors for Groq, Upstash, Firebase, Neon, R2, SMTP and Telegram. Public DNS resolution also failed in this managed workspace. Credentials were not verified or rejected by the services.

Run `backend/venv/bin/python scripts/check_connections.py` from your own terminal to check the current values. It uses read-only service probes and SMTP authentication; it sends no email or Telegram message. Delivery needs a later actual message test.

## Office UI

Open [the standalone office preview](../frontend/public/office-preview.html) to inspect all 15 cabins, themes and capabilities without a backend or production build. The frontend homepage and `/office` show the public office; `/workspace` provides authenticated controls. Select Friday and click Preview assignment to see the labelled walking demo. Actual execution activity is explicitly unavailable.

The standalone preview can be served outside the managed workspace with:

```bash
python3 -m http.server 3001 --bind 127.0.0.1 --directory frontend/public
```

Then open `http://localhost:3001/office-preview.html`. Automatic browser launch and local hosting were unavailable in the managed workspace.

Run `node scripts/render-office-preview.cjs` to refresh the HTML from the actual React office components. The production build is gated until required live connection checks pass.
