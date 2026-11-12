# Verification evidence

## Current UI checks

- TypeScript `--noEmit` passed on the new cabin office and public/authenticated routes.
- Three office tests passed: all fourteen specialist routes enter the CEO cabin and return without crossing other cabins; walking completion/cancellation/reduced motion; only new agent-start events produce assignment movements, including separate tasks for the same agent.
- Two existing frontend transport tests passed: SSE authentication/reconnect/cursor handling and visible validation/offline/authentication errors.
- The standalone office renderer passed: 15 cabins and no fabricated working status. The generated HTML includes persistent themes, cabin detail dialogs, map/list controls and a labelled walking demo.
- `frontend/tests/office-browser.mjs` attempted Chrome with a file URL and debugging pipe. Chrome closed at `Target.setDiscoverTargets` before any page checks. **Desktop/mobile visual checks and actual browser interactions remain unverified.** No screenshot or browser pass is claimed. The failed report is artifacts/office/report.json.

## Configuration and storage

All 29 active env fields are populated. Local format validation passed; five frontend fields are referenced. Nine backend storage fields still await the Upstash/Neon/R2 runtime migration. Live Groq, Upstash, Firebase, Neon, R2, SMTP and Telegram probes failed at network/connection access in this workspace; DNS resolution also failed. This does not prove that credentials are valid or invalid. No AI completion or notification was sent.

SQLite fallback and worker startup are disabled while storage migration is pending. Four focused API configuration tests passed and establish that the public roster/health do not touch SQLite and private operations require identity before returning storage-unavailable errors. The full runtime suite needs adaptation to the new storage architecture.

## Historical evidence

31 backend tests and a Next.js production build passed for the previous SQLite application. **These do not verify the requested Redis/Firebase/Neon/R2 architecture or the latest office UI.** Historical provider/notification simulations were local tests, not live service verification. Production builds remain gated pending current successful connection checks. Docker is unavailable and container deployment is unverified.

## Repeat current UI checks

```bash
cd frontend
node node_modules/typescript/bin/tsc --noEmit
npm run test:office
npm run test:transport
node ../scripts/render-office-preview.cjs
npm run test:office:browser
```

Set CHROME_BIN to a Chrome/Chromium executable if needed. The standalone browser runner requires no backend and sends no work. It checks 15 cabins, desktop/mobile overflow, both themes, detail dialogs, hand-off stages, cancellation and reduced motion. Successful runs save actual screenshots and a report in artifacts/office.

The older full-application browser harness remains for later migration work; it cannot verify the new persistence architecture yet. PLAN.md counts unverified work as remaining.
