# Verification evidence

## Repeatable verification

`backend/venv/bin/python scripts/verify_all.py` runs the complete verification sequence and records each result in `artifacts/verification/report.json`, `project-progress.json` and generated `PLAN.md`. It installs missing Redis test dependencies, uses an isolated live storage fixture and one bounded Groq completion, runs the saved local Postman simulation and browser checks, and attempts the production build only after the live connection gate passes. It sends no real notifications.

`--local --only env,backend,office,transport,typescript,render` repeats the checks available inside the sandbox. The local rerun and subsequent terminal verification completed on 2026-11-12. Current connection/browser fixes still need a focused rerun. Browser API requests are redirected to the disposable backend, including when testing a build configured for the production backend URL.

## Current results

The terminal run on 2026-11-12 passed all 51 backend tests, including actual Redis Lua. After the SMTP certificate-trust and browser fixture CORS fixes, the complete backend suite passed **54 tests with no skips**. The three added regressions check verified TLS roots, CORS/fixture identity with allowed and denied origins, and useful Firebase diagnostics without credential leakage.

Five frontend movement/transport tests, TypeScript, rendering and the standalone office browser passed. The latter checks desktop/mobile, dark/light persistence, 15 cabins, details, hand-off phases, cancellation and reduced motion. Screenshots and the report are in `artifacts/office/`.

The Postman simulation passed. Its NDJSON log independently records two HTTP 200 requests for tool/continuation and three HTTP 503 requests. The real caller checker observed tool creation, a failed task and a skipped dependent. A separate live Groq completion for the selected NOVA model passed.

Four of six live access probes passed: **Groq, Upstash, Neon and R2**. Firebase failed while refreshing the service-account token (`RefreshError`); local PEM parsing/project checks pass, but they cannot establish that Google accepts the key. The checker now classifies known refresh failures without logging credential material.

SMTP failed with `SSLCertVerificationError`. This Python has no default CA file. The checker and runtime now supplement system roots with certifi; hostname/certificate verification stays enabled and 121 trusted CA roots were loaded. Actual SMTP authentication still needs the focused rerun. No real email or Telegram message was sent; Telegram remains deferred.

## Workspace browser failure and fix

The full workspace browser failed on its first health fetch. The disposable backend's outer middleware returned a new response before CORS ran. The fix decorates the existing health response and preserves CORS headers. Allowed-origin and denied-origin regression requests now pass. The actual Chrome workspace rerun is pending; the standalone browser pass does not establish workspace controls.

```bash
backend/venv/bin/python scripts/verify_all.py --only connections,browser
```

The runner now prints failed-service reasons directly. Logs and reports remain in `artifacts/verification/` and `artifacts/browser/`. The browser redirects application API traffic to the disposable backend and uses ephemeral data.

## Remaining verification

Live managed-storage writes remain blocked by Firebase. The production build remains blocked by the required connection gate. Container checks are unavailable because Docker is not installed; native startup does not require Docker. Google sign-in, real notification delivery and live restart/failover remain unverified.

## Repeat checks

```bash
NOVA_STATE_TESTS=1 backend/venv/bin/python -m unittest discover -s backend/tests -v
backend/venv/bin/python scripts/audit_env.py
cd frontend
npm run test:office
npm run test:transport
node node_modules/typescript/bin/tsc --noEmit
npm run test:office:browser
```

Historical SQLite evidence does not establish managed-storage compatibility. Current Lua tests use fakeredis/lupa; Firestore/Neon/R2 integration tests use fixtures until live writes pass. See [PLAN.md](../PLAN.md) for implementation and acceptance states.
