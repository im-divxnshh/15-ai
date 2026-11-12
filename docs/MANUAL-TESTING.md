# Run NOVA and test it manually

Use two terminals from the project root. Virtualenv activation is optional because these commands select the backend interpreter explicitly.

Terminal 1 — backend:

```bash
cd /Users/divxnshh/Desktop/Projects/15-ai
backend/venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

Terminal 2 — frontend:

```bash
cd /Users/divxnshh/Desktop/Projects/15-ai/frontend
npm run dev
```

Open http://localhost:3000/workspace. Backend health is http://127.0.0.1:8000/api/health and API documentation is http://127.0.0.1:8000/docs. Use the private `APP_TOKEN` from `backend/.env` in the workspace's access-token field; that connects the `owner` account used by the default Telegram setup. Google sign-in creates a separate Firebase-UID account; use that UID with `setup_telegram.py --user` if you want the bot to share its work instead.

The current Firebase key was rejected by Google. Chats, memory and other Firebase-backed operations require a valid current `FIREBASE_CREDENTIALS` value before they can succeed. SMTP failure does not prevent development startup or Telegram delivery. Keep `NEXT_PUBLIC_BACKEND_URL` in `frontend/.env.local` pointed at `http://127.0.0.1:8000`, and ensure backend `CORS_ORIGINS` includes `http://localhost:3000`. Restart the relevant server after an env change.

## Telegram setup

The repository already has token/chat fields in the private backend environment. Validate and enable them while the backend is stopped:

```bash
cd /Users/divxnshh/Desktop/Projects/15-ai
backend/venv/bin/python backend/scripts/setup_telegram.py --enable
```

This checks the live bot/private chat, refuses an existing webhook, registers a private command menu, enables all notification categories for `owner`, and saves `TELEGRAM_CONTROL_ENABLED=true` and `TELEGRAM_CONTROL_USER_ID=owner`. It preserves other env values. Then start the backend and send `/start` to the bot. First activation skips old pending messages; send new commands after startup. Only the elected backend worker polls Telegram, so keep the backend running. No public webhook or tunnel is needed.

If the bot credentials need replacing:

1. Open https://t.me/BotFather, send `/newbot`, and choose a username ending in `bot`.
2. Save the issued token as `TELEGRAM_BOT_TOKEN` in `backend/.env`. Never paste it into chat or commit it.
3. Open your bot, tap **Start**, and send a message.
4. With the backend stopped, run `backend/venv/bin/python backend/scripts/telegram_chat_id.py`. Save your positive private chat ID as `TELEGRAM_CHAT_ID` in `backend/.env`.
5. Run the setup command above, then start the backend.

For a Firebase-login workspace instead of APP_TOKEN, run `setup_telegram.py --enable --user YOUR_FIREBASE_UID`. `/api/session` returns your authenticated account ID. A bot is bound to one selected account; it cannot read other users' data.

## Telegram commands to try

| Send to your bot | Expected behavior |
|---|---|
| `/start` or `/help` | Command guide |
| `/status` | Current running, queued, paused or interrupted workflows |
| `/tasks` | Recent workflows with full IDs and completion counts |
| `/task Write a five-point study plan for tomorrow` | One queued NOVA task, followed by results or a truthful failure |
| `Draft a polite email asking for a project update` | Plain text queues a task; drafting does not send email |
| `/run WORKFLOW_ID` | Actual step states, recorded results and errors |
| `/audit` | Last 20 recorded account events |
| `/pause WORKFLOW_ID` | Finish active calls and hold later steps |
| `/resume WORKFLOW_ID` | Resume a paused workflow |
| `/cancel WORKFLOW_ID` | Cancel eligible pending/active work |
| `/retry WORKFLOW_ID` | Explicitly retry unsuccessful steps after reviewing side effects |

While you work in the frontend, Telegram also receives queue/control updates, replies, results, failures, reminders and workflow summaries. Activity audits arrive in batches about every 15 seconds with event IDs, timestamps, agent and task/tool labels. `/run` retrieves detailed results. Audits summarize recorded events; they do not include raw tool payloads or unrelated server logs. Telegram commands continue after you close the browser, while the backend remains running.

In **Delivery**, Telegram must stay enabled with the same configured chat ID. Category switches control automatic notifications; bot command replies remain available independently of category switches. Disabling Telegram or changing the destination also stops incoming commands for that binding. Inspect **Delivery history** for `sent`, `retrying`, `failed` or `interrupted`; `sent` records provider acceptance. Repeated Telegram update IDs do not create duplicate work. A command interrupted between its claim and acknowledgement is not silently rerun; inspect `/tasks` before sending a new command.

## Frontend test tasks

| Area | What to do | What to check |
|---|---|---|
| Office | Click NOVA and a specialist; switch themes and resize the window | 15 cabins, matching capabilities, persistent theme, readable mobile layout |
| Chat | Ask `Explain Python lists in three bullet points` | Reply, recorded agent/activity, history and Telegram reply notification |
| Missions | Queue `List three website ideas`, then `Choose one using the previous result` in sequential mode | Ordered steps and the second step receives the first result |
| Parallel work | Queue `Draft a study checklist` and `Draft a workout checklist` in parallel mode | Independent work starts within the configured concurrency limit |
| Controls | Queue several tasks, pause while running, resume, then cancel another batch | Visible real states; no later completion overwrites cancellation |
| Memory | Save `My preferred project color is copper`, revisit Memory, then ask about the saved preference | Persisted entry and recall; current browser automation stopped at this check |
| Files | Upload a small text file containing `Project Orion deadline is Friday`; ask about its deadline, then delete it | File list, indexed retrieval with source and removal from access |
| Tasks | Create a to-do and mark it done | Status persists on reload; this list is separate from queued AI workflows |
| Routines | Create a routine at the minimum allowed interval, choose Queue now, then disable it | One recorded run, queued result, disabled routine stops scheduling |
| Approvals | Ask for an allowed system command such as `pwd`, then approve in the workspace | Approval is required; recorded result appears once |
| Telegram | Keep the backend running, close the browser, submit `/task Draft three meeting agenda items` | Task appears on `/tasks`, outcome arrives, reopening workspace shows the same run |
| Offline | Disconnect internet briefly, then reconnect | Visible reconnect/error state and recovery without duplicate results |

Use tasks based on supplied information. Calendar, inbox reading, social publishing, trading and music account integrations are unavailable. Voice remains deferred. To stop each server, press Ctrl+C in its terminal.
