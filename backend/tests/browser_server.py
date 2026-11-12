"""Temporary UI verification backend. No live model or delivery calls.

Run from the repository root: backend/venv/bin/python backend/tests/browser_server.py
Stop the normal backend first; this harness uses port 8000 and disposable data.
"""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import httpx
import uvicorn
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from main import app
from app.api.nova import health
from app.core.runtime import jobstore as db,workflows,provider,tools
from fastapi.responses import JSONResponse

temporary=tempfile.TemporaryDirectory(prefix='nova-ui-')
root=Path(temporary.name);db.PATH=root/'office.sqlite3';tools.FILES=root/'files';tools.ROOT=root
os.environ.update(APP_TOKEN='nova-browser-test',ALLOW_LOCAL_NO_AUTH='false',FIREBASE_CREDENTIALS='',GROQ_API_KEY='simulation-only',SMTP_HOST='',SMTP_USER='',SMTP_PASSWORD='',TELEGRAM_BOT_TOKEN='',SYSTEM_ACCESS_USER_ID='')
actual_client=httpx.AsyncClient

async def simulate(request):
    payload=json.loads(request.content);messages=payload['messages'];system=messages[0]['content'];text=messages[-1]['content'] or ''
    if system.startswith('Route'):
        content=json.dumps({'agents':['friday'],'reason':'Simulation fixture routing'})
    elif system.startswith('Create an editable plan'):
        content=json.dumps({'title':'Editable verification plan','tasks':[{'title':'Inspect','instruction':'Inspect supplied information','agent_id':'drake','dependencies':[]},{'title':'Recommend','instruction':'Summarize the earlier result','agent_id':'stark','dependencies':[0]}]})
    elif 'FAIL_PROVIDER' in text:
        return httpx.Response(503,json={'error':{'message':'Injected verification failure'}})
    else:
        if 'slow' in text.lower():await asyncio.sleep(8)
        content='Simulated verification reply: '+text[:300]
    return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':content}}]})

@app.middleware('http')
async def verification_header(request,call_next):
    if request.url.path=='/api/health':return JSONResponse({**health(),'verification':'simulated-disposable-harness'})
    return await call_next(request)

@asynccontextmanager
async def lifespan(_):
    db.init()
    await tools.dispatch('owner','michel','request_command',{'command':'pwd'})
    with patch.object(httpx,'AsyncClient',lambda **kw:actual_client(**kw,transport=httpx.MockTransport(simulate))):
        workflows.start()
        try:yield
        finally:await workflows.stop()

app.router.lifespan_context=lifespan
if __name__=='__main__':
    try:uvicorn.run(app,host='127.0.0.1',port=8000,log_level='warning')
    finally:temporary.cleanup()
