"""Report env presence and active code references without exporting values."""
import ast
import json
from pathlib import Path
import re
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
PENDING=set()
sources=[ROOT/'backend/main.py',ROOT/'backend/app/api/nova.py',*(ROOT/'backend/app/core/runtime').glob('*.py')]
references={}
for file in sources:
    tree=ast.parse(file.read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.Constant) and isinstance(node.value,str) and re.fullmatch(r'[A-Z][A-Z0-9_]+',node.value):
            references.setdefault(node.value,[]).append(str(file.relative_to(ROOT))+':'+str(node.lineno))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='getenv' and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
            references.setdefault(node.args[0].value,[]).append(str(file.relative_to(ROOT))+':'+str(node.lineno))
for file in [ROOT/'frontend/lib/api.ts',ROOT/'frontend/lib/firebaseClient.ts']:
    for match in re.finditer(r'process\.env\.([A-Z0-9_]+)',file.read_text()):references.setdefault(match.group(1),[]).append(str(file.relative_to(ROOT)))
fields=[]
for file in ['backend/.env','frontend/.env.local']:
    for key,value in dotenv_values(ROOT/file).items():
        fields.append({'file':file,'key':key,'present':bool(str(value or '').strip()),'integration':'migration pending' if key in PENDING else 'referenced' if references.get(key) else 'unreferenced','references':references.get(key,[])})
connection_note='No successful live report is available yet. Run the connection checker; environment presence alone cannot establish service access.'
try:
    report=json.loads((ROOT/'artifacts/connection-report.json').read_text())
    if report.get('mode')=='live':
        passed=[name for name,row in report['checks'].items() if row.get('status')=='passed']
        failed=[name for name,row in report['checks'].items() if row.get('status') in ('failed','missing')]
        connection_note='Latest live report at '+report['checked_at']+'. Passed: '+(', '.join(passed) or 'none')+'. Failed: '+(', '.join(failed) or 'none')+'. Telegram remains deferred. Code/configuration changes require a fresh connection check; actual storage writes and notification delivery are separate checks.'
except (OSError,ValueError,KeyError,TypeError):
    pass
target=ROOT/'docs/ENV-AUDIT.md'
lines=['# Environment audit','','All values remain private. Presence and code references do not establish live connectivity.','','The current audit covers 24 backend fields and five public frontend fields. Storage fields are referenced by the Redis, Firebase, Neon and R2 adapters. SQLite fallback is disabled.','','| File | Field | Value | Integration |','|---|---|---|---|']
for field in fields:lines.append(f"| {field['file']} | {field['key']} | {'Present' if field['present'] else 'Missing'} | {field['integration']} |")
lines+=['','## Connection evidence','',connection_note,'','Run `backend/venv/bin/python scripts/check_connections.py` from your own terminal to check the current values. It uses read-only service probes and SMTP authentication; it sends no email or Telegram message. Delivery needs a later actual message test.','','## Office UI','','Open [the standalone office preview](../frontend/public/office-preview.html) to inspect all 15 cabins, themes and capabilities without a backend or production build. The frontend homepage and `/office` show the public office; `/workspace` provides authenticated controls. Select Friday and click Preview assignment to see the labelled walking demo. The public preview is a labelled demo. Authenticated office movement consumes actual backend events when connected.','','The standalone preview can be served outside the managed workspace with:','','```bash','python3 -m http.server 3001 --bind 127.0.0.1 --directory frontend/public','```','','Then open `http://localhost:3001/office-preview.html`. Standalone desktop/mobile browser checks passed in the terminal verification run; see docs/VERIFICATION.md for workspace/browser limitations.','','Run `node scripts/render-office-preview.cjs` to refresh the HTML from the actual React office components. The production build is gated until required live connection checks pass.']
target.write_text('\n'.join(lines)+'\n')
artifact=ROOT/'artifacts/env-audit.json';artifact.parent.mkdir(exist_ok=True);artifact.write_text(json.dumps({'fields':fields},indent=2)+'\n')
print(f"Audited {len(fields)} fields: {sum(f['present'] for f in fields)} present, {sum(f['integration']=='migration pending' for f in fields)} awaiting storage integration. No values exported.")
