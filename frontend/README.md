# NOVA OS frontend

Next.js 16, React 19, TypeScript and Firebase authentication. The homepage and `/office` show the public 2D cabin office; `/workspace` hosts authenticated work controls.

Open [office-preview.html](public/office-preview.html) directly in a browser to see the CEO cabin, fourteen specialists, agent details, themes, and the labelled assignment walking demo. It requires no backend or build. Select Friday and click **Preview assignment**.

```bash
npm ci
npm run dev
npm run test:office
npm run test:transport
npm run test:office:browser
```

The browser check targets the standalone file and writes actual screenshots under ../artifacts/office when Chrome can run. Its latest launch failed before page checks. Live assignment event wiring remains unverified until the requested backend storage migration is complete.

`npm run build` stays gated until all required live connection checks pass. Private credentials belong only in backend/.env; frontend/.env.local contains five public fields. See [the project README](../Readme.md), [env audit](../docs/ENV-AUDIT.md), and [PLAN.md](../PLAN.md).
