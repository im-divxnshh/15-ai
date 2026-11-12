# NOVA OS API

**Current readiness:** Upstash/Firebase/Neon/R2 persistence migration is pending. Private data endpoints require authentication and then return HTTP 503 while storage is unavailable; the background worker does not run. The workflow/data/delivery descriptions below document the retained handlers and their intended behavior, not a verified deployed runtime. SQLite fallback is disabled. Public `GET /api/office/roster` returns only the fifteen agent descriptors with unavailable activity; health endpoints are also public. `/api/session` verifies identity without opening storage.

The active contract is [openapi.json](openapi.json), generated from `backend/main.py`. Interactive docs are at `http://localhost:8000/docs`. Regenerate with `backend/venv/bin/python backend/scripts/export_openapi.py`.

All `/api` data endpoints require `Authorization: Bearer <Firebase ID token or APP_TOKEN>`. Health is public. APP_TOKEN identifies the private `owner`; Firebase uses the verified UID, including revocation checks. Only that user's data is returned. Local unauthenticated mode must be explicitly enabled and is for development.

## Workflows

`POST /api/workflows/plan` takes `instruction` and `mode` (`sequential` or `parallel`). NOVA prepares a validated, editable plan using Groq; this does not run the plan. Missing/rejected provider configuration produces an error.

`POST /api/workflows` queues work immediately and returns persisted state:

```json
{
  "title": "Research then recommend",
  "mode": "parallel",
  "concurrency": 2,
  "client_key": "unique-submission-id",
  "tasks": [
    {"title": "Research", "instruction": "Research options and cite sources", "agent_id": "drake", "dependencies": []},
    {"title": "Compare", "instruction": "Compare the research results", "agent_id": "stark", "dependencies": [0]}
  ]
}
```

`agent_id: null` invokes NOVA routing. Dependencies are zero-based indexes of earlier tasks. There are 1–30 tasks, per-workflow concurrency 1–4 and at most eight concurrent workflow tasks globally. Batches for a user run in FIFO order; different users can run concurrently. Sequential mode adds a dependency on the preceding task, passes its results forward, and stops dependent work after failure. Use parallel mode with concurrency 1 for independent ordered work that should continue after another task fails.

Repeated `client_key` for the same user returns the existing workflow. Reuse the key after an uncertain submission response. Queue creation is transactional. Model requests may retry transient HTTP errors three times; whole tasks are retried only by the user.

| Endpoint | Purpose |
|---|---|
| `GET /api/workflows` | Queue/history with real step results |
| `GET /api/workflows/{id}?after=0` | Full workflow and persisted events after a cursor |
| `POST /api/workflows/{id}/pause` | Finish active calls, prevent further starts in that workflow |
| `POST /api/workflows/{id}/resume` | Resume paused work after active tasks finish |
| `POST /api/workflows/{id}/cancel` | Cancel pending work and active async calls; deny pending approvals |
| `POST /api/workflows/{id}/retry` | Explicitly retry failed, skipped and interrupted steps; preserve completed results |
| `GET /api/workflows/{id}/stream?after=123` | Authenticated SSE replay/live stream |

Workflow states: `queued`, `running`, `paused`, `completed`, `failed`, `cancelled`, `interrupted`. Additional step states: `waiting_approval`, `skipped`. Browser closure does not stop queued work. On restart, in-flight steps are interrupted and require explicit review/retry. A server cannot undo a tool action already accepted or a command already running.

The SSE stream sends persisted IDs and JSON event data, plus a `ready` event and heartbeat comments. Reconnect with the last processed `after` cursor to recover missed events. Use authenticated fetch streaming; never put access tokens in URLs. Event types include routing, collaboration, tool start/completion/failure, approvals, step outcomes, and workflow controls. `/api/events` lists account activity.

## Agents, data and approvals

| Endpoints | Purpose |
|---|---|
| `/api/session`, `/api/agents`, `/api/analytics` | Identity, all 15 agents, actual activity/metrics |
| `POST /api/chat`, `GET/DELETE /api/history` | Direct or routed replies and scoped history |
| `GET/POST /api/memory`, `GET /api/memory/search?q=...`, `DELETE /api/memory/{id}` | Persistent keyword recall |
| `GET/POST /api/profile`, `DELETE /api/profile/{key}` | Profile facts |
| `GET/POST /api/tasks`, `POST /api/tasks/{id}/complete`, `DELETE /api/tasks/{id}` | To-dos/reminders; `GET ?status=all` includes completed work |
| `GET/POST /api/routines`, `POST /api/routines/{id}/toggle`, `POST /api/routines/run/{id}`, `DELETE /api/routines/{id}` | Durable standing instructions |
| `GET /api/notifications`, `POST /api/notifications/read` | Work alerts and read state |
| `GET /api/actions`, `POST /api/actions/{id}/approve`, `POST /api/actions/{id}/deny` | Held command approvals and recorded outcomes |

Supported specialist tools are listed in `/api/agents`; ungranted tools are rejected. System tools are owner-only (`APP_TOKEN` owner or `SYSTEM_ACCESS_USER_ID` Firebase UID). Paths outside SYSTEM_ROOT and credential/private-data paths are rejected. Commands have a narrow allowlist, require explicit approval, claim actions atomically, omit backend secrets from subprocess environments, and record outcomes once. They run with the backend's OS permissions; SYSTEM_ROOT is a path boundary, not an OS sandbox.

Files: `GET /api/files` lists metadata; `PUT /api/files/{filename}` uploads raw bytes (20 MB maximum, `application/octet-stream`); `GET` downloads and `DELETE` removes the file and its indexed chunks. Text/code/PDF/DOCX are indexed. Other formats remain downloadable with warnings. Files use a private per-user directory. Re-upload replaces stale chunks. Memory is keyword recall, with no vector-search claim.

## Delivery

`GET/PUT /api/delivery/settings` saves email/chat destinations, channel switches and categories (`updates`, `results`, `failures`, `replies`, `reminders`, `summaries`). New accounts start with both outgoing channels disabled. `POST /api/delivery/test` queues actual transport tests for enabled channels. `GET /api/delivery` shows message body, destination, state, attempts and errors. `POST /api/delivery/{id}/retry` explicitly retries eligible messages using the current destination.

Delivery states: `pending`, `sending`, `sent`, `blocked`, `retrying`, `failed`, `interrupted`, `disabled`. Known transient rejections/connection failures have bounded retries. Lost acknowledgements and partial Telegram messages require explicit review; they are not silently replayed. Destination changes block old messages until explicit retry. Restart during sending marks the outcome interrupted. Verification is tied to sender configuration and destination. "Sent" means SMTP/Telegram acceptance, not guaranteed inbox arrival.

SMTP passwords and Telegram tokens are read only from backend environment variables. The token is omitted from transport logs. Bots only deliver to configured chats; calendar, inbox, broker, social publication and music account integrations are not implemented. The agents can draft and reason about these topics using supplied information.

## Errors

`401`: missing/invalid identity; `404`: unavailable or other-user resource; `409`: invalid control transition; `413`: file too large; `422`: invalid data/dependency/filename; `502`: provider planning failure; `503`: unavailable authentication configuration. Chat returns an explicit `error` alongside any usable partial reply. Steps persist failures; the app never supplies fabricated successful answers or progress.
