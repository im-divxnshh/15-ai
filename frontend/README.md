# NOVA frontend

Run `npm install`, then `npm run dev` from this directory. The workspace is at http://localhost:3000/workspace; the public office is at http://localhost:3000/office.

Configure the backend URL and public Firebase values in `.env.local`. The backend must run separately on port 8000.

Use `npm run build` and `npm run start` for production. See [startup and Telegram instructions](../docs/RUNNING.md).

The standalone office demo is [public/office-preview.html](public/office-preview.html). Refresh it from the repository root with `node scripts/render-office-preview.cjs`.
