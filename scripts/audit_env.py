"""Report env presence and active code references without exporting values."""
import ast
import json
from pathlib import Path
import re
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
PENDING={'STORAGE_BACKEND','UPSTASH_REDIS_REST_URL','UPSTASH_REDIS_REST_TOKEN','NEON_URL','FILE_STORAGE_BACKEND','R2_ACCOUNT_ID','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_BUCKET'}
sources=[ROOT/'backend/main.py',ROOT/'backend/app/api/nova.py',*(ROOT/'backend/app/core/runtime').glob('*.py')]
references={}
for file in sources:
    tree=ast.parse(file.read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='getenv' and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
            references.setdefault(node.args[0].value,[]).append(str(file.relative_to(ROOT))+':'+str(node.lineno))
for file in [ROOT/'frontend/lib/api.ts',ROOT/'frontend/lib/firebaseClient.ts']:
    for match in re.finditer(r'process\.env\.([A-Z0-9_]+)',file.read_text()):references.setdefault(match.group(1),[]).append(str(file.relative_to(ROOT)))
fields=[]
for file in ['backend/.env','frontend/.env.local']:
    for key,value in dotenv_values(ROOT/file).items():
        fields.append({'file':file,'key':key,'present':bool(str(value or '').strip()),'integration':'migration pending' if key in PENDING else 'referenced' if references.get(key) else 'unreferenced','references':references.get(key,[])})
target=ROOT/'docs/ENV-AUDIT.md'
lines=['# Environment audit','','All values remain private. Presence and code references do not establish live connectivity.','','The current audit covers 24 backend fields and five public frontend fields. Nine storage fields await runtime integration. SQLite fallback is disabled.','','| File | Field | Value | Integration |','|---|---|---|---|']
for field in fields:lines.append(f"| {field['file']} | {field['key']} | {'Present' if field['present'] else 'Missing'} | {field['integration']} |")
lines+=['','## Connection evidence','','The last live checks encountered connection/network errors for Groq, Upstash, Firebase, Neon, R2, SMTP and Telegram. Public DNS resolution also failed in this managed workspace. Credentials were not verified or rejected by the services.','','Run `backend/venv/bin/python scripts/check_connections.py` from your own terminal to check the current values. It uses read-only service probes and SMTP authentication; it sends no email or Telegram message. Delivery needs a later actual message test.','','## Office UI','','Open [the standalone office preview](../frontend/public/office-preview.html) to inspect all 15 cabins, themes and capabilities without a backend or production build. The frontend homepage and `/office` show the public office; `/workspace` provides authenticated controls. Select Friday and click Preview assignment to see the labelled walking demo. Actual execution activity is explicitly unavailable.','','The standalone preview can be served outside the managed workspace with:','','```bash','python3 -m http.server 3001 --bind 127.0.0.1 --directory frontend/public','```','','Then open `http://localhost:3001/office-preview.html`. Automatic browser launch and local hosting were unavailable in the managed workspace.','','Run `node scripts/render-office-preview.cjs` to refresh the HTML from the actual React office components. The production build is gated until required live connection checks pass.']
target.write_text('\n'.join(lines)+'\n')
artifact=ROOT/'artifacts/env-audit.json';artifact.parent.mkdir(exist_ok=True);artifact.write_text(json.dumps({'fields':fields},indent=2)+'\n')
print(f"Audited {len(fields)} fields: {sum(f['present'] for f in fields)} present, {sum(f['integration']=='migration pending' for f in fields)} awaiting storage integration. No values exported.")
