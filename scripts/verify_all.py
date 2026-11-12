#!/usr/bin/env python3
"""Verify NOVA and record actual evidence in PLAN.md; never sends notifications."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from datetime import datetime,timezone
from urllib.request import urlopen
from progress import generate,update

ROOT=Path(__file__).resolve().parents[1]
PYTHON=ROOT/'backend/venv/bin/python'
OUT=ROOT/'artifacts/verification'
OUT.mkdir(parents=True,exist_ok=True)
RESULTS={}
SELECTED=set()

def selected(ident):return not SELECTED or ident in SELECTED

def record(ident,title,code,scope,task=None):
    row={'title':title,'at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'exit_code':code,'scope':scope}
    RESULTS[ident]=row
    report_path=OUT/'report.json'
    prior=json.loads(report_path.read_text()) if report_path.exists() else {}
    prior.update(RESULTS);report_path.write_text(json.dumps(prior,indent=2)+'\n')
    with (ROOT/'.progress.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=ROOT/'project-progress.json';data=json.loads(path.read_text())
        data['local_checks']=[c for c in data.get('local_checks',[]) if c['title']!=title]+[row]
        data['updated_at']=row['at'];path.write_text(json.dumps(data,indent=2)+'\n')
    if task:update(task,'complete' if code==0 else 'blocked',scope,{'at':row['at'],'exit_code':code})
    else:generate()
    print(f"{title}: {'PASS' if code==0 else 'FAIL/BLOCKED'} — {scope}",flush=True)
    return code==0

def run(ident,title,args,scope,task=None,cwd=ROOT,env=None,timeout=300):
    print(f'Checking {title}...',flush=True)
    log=OUT/(ident+'.log')
    try:
        with log.open('w') as output:
            code=subprocess.run([str(a) for a in args],cwd=cwd,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=timeout).returncode
    except subprocess.TimeoutExpired:code=124
    except OSError:code=127
    return record(ident,title,code,scope,task)

def stop(process):
    if process.poll() is None:
        os.killpg(process.pid,signal.SIGTERM)
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()

def server(args,log,env=None,cwd=ROOT):
    handle=log.open('w')
    process=subprocess.Popen([str(a) for a in args],cwd=cwd,env=env,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
    handle.close();return process

def ready(url,process,timeout=90):
    end=time.monotonic()+timeout
    while time.monotonic()<end and process.poll() is None:
        try:
            with urlopen(url,timeout=2) as response:
                if response.status==200:return True
        except Exception:pass
        time.sleep(.5)
    return False

def simulation():
    log=OUT/'simulation.ndjson';env=os.environ.copy();env['NOVA_SIMULATION_URL']='http://127.0.0.1:14010'
    process=None
    try:
        process=server(['postman','simulation','run','postman/simulations/nova-runtime.sim.yaml','--port','14010','--no-history','--output','ndjson'],log)
        deadline=time.monotonic()+40
        while process.poll() is None and time.monotonic()<deadline:
            if 'listening' in log.read_text():break
            time.sleep(.5)
        if 'listening' not in log.read_text():return record('simulation','Postman provider HTTP simulation',1,'Simulation did not start; see artifacts/verification/simulation.ndjson.')
        return run('simulation','Postman provider HTTP simulation',[PYTHON,'backend/tests/check_simulation.py'],'Actual tool creation and provider 503 propagation against a local Groq HTTP stand-in; disposable storage SDKs, no live notifications.',env=env)
    except OSError:return record('simulation','Postman provider HTTP simulation',127,'Postman CLI/server unavailable.')
    finally:
        if process:stop(process)

def browser(production):
    env=os.environ.copy();env.update(NOVA_BROWSER_URL='http://127.0.0.1:13000',NOVA_BROWSER_BACKEND_URL='http://127.0.0.1:18000',NOVA_TEST_PORT='18000',CORS_ORIGINS='http://127.0.0.1:13000',NOVA_CHROME_NO_SANDBOX='1',NEXT_TELEMETRY_DISABLED='1')
    processes=[]
    try:
        backend=server([PYTHON,'backend/tests/browser_server.py'],OUT/'browser-backend.log',env);processes.append(backend)
        if not ready(env['NOVA_BROWSER_BACKEND_URL']+'/api/health',backend):return record('browser','Workspace browser verification',1,'Disposable backend did not start; no live account was used.',task='browser-tests')
        command=['node','node_modules/next/dist/bin/next','start' if production else 'dev','--hostname','127.0.0.1','--port','13000']
        frontend=server(command,OUT/'browser-frontend.log',env,ROOT/'frontend');processes.append(frontend)
        if not ready(env['NOVA_BROWSER_URL']+'/workspace',frontend):return record('browser','Workspace browser verification',1,'Frontend did not start; see browser-frontend.log.',task='browser-tests')
        scope=('Production' if production else 'Development')+' frontend; desktop/mobile themes, chat/workflow/task/file/approval/delivery/offline controls against a disposable backend. Google sign-in and real notifications are excluded.'
        return run('browser','Workspace browser verification',['node','tests/browser.mjs'],scope,task='browser-tests' if production else None,cwd=ROOT/'frontend',env=env,timeout=300)
    except OSError:return record('browser','Workspace browser verification',127,'Browser/server executable unavailable.',task='browser-tests')
    finally:
        for process in reversed(processes):stop(process)

def main():
    global SELECTED
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',help='Comma-separated check IDs; omitted runs every check')
    parser.add_argument('--local',action='store_true',help='No dependency downloads or live calls; excludes production build')
    args=parser.parse_args();SELECTED=set(filter(None,(args.only or '').split(',')))
    if selected('dependencies') and not args.local:
        if not (importlib.util.find_spec('fakeredis') and importlib.util.find_spec('lupa')):
            run('dependencies','Redis test dependencies',[PYTHON,'-m','pip','install','fakeredis[lua]>=2.32,<3'],'fakeredis/lupa installed for actual Redis Lua verification.')
        else:record('dependencies','Redis test dependencies',0,'fakeredis and lupa already available.')
    if selected('env'):run('env','Environment reference audit',[PYTHON,'scripts/audit_env.py'],'All required environment fields audited without exporting values.')
    if selected('backend'):
        env=os.environ.copy();env.pop('NOVA_STATE_TESTS',None)
        if args.local and not importlib.util.find_spec('fakeredis'):env['NOVA_STATE_TESTS']='1'
        run('backend','Backend runtime and storage adapter checks',[PYTHON,'-m','unittest','discover','-s','backend/tests','-v'],'Full backend suite including actual Redis Lua, ownership, queue/recovery, provider and storage failure checks.' if env.get('NOVA_STATE_TESTS')!='1' else 'Local state/SDK/HTTP fixture checks; actual Redis Lua explicitly excluded.',task='backend-tests' if env.get('NOVA_STATE_TESTS')!='1' else None,env=env)
    for ident,title,command,scope in [
        ('office','Office movement tests',['node','--test','tests/office.test.cjs'],'All fourteen routes, movement phases, cancellation, reduced motion and actual event mapping.'),
        ('transport','Frontend transport tests',['node','--test','tests/transport.test.cjs'],'Authenticated reconnect cursors and visible validation/offline errors.'),
        ('typescript','Frontend TypeScript',['node','node_modules/typescript/bin/tsc','--noEmit'],'Type-check the current frontend; separate from production build.'),
        ('render','Standalone office rendering',['node','../scripts/render-office-preview.cjs'],'Generate the standalone preview from the actual components.')]:
        if selected(ident):run(ident,title,command,scope,cwd=ROOT/'frontend')
    if selected('simulation'):simulation()
    if selected('connections') and not args.local:
        run('connections','Required live service connections',[PYTHON,'scripts/check_connections.py'],'Six live access probes; no email/Telegram message; Telegram remains deferred.',timeout=150)
        path=ROOT/'artifacts/connection-report.json'
        if path.exists():
            for service,check in json.loads(path.read_text()).get('checks',{}).items():
                if check.get('status') in ('failed','missing'):
                    print(f"{service}: {check.get('detail','Connection check failed')}",flush=True)
    connection_path=ROOT/'artifacts/connection-report.json'
    connections=json.loads(connection_path.read_text()) if connection_path.exists() else {}
    current=subprocess.run([str(PYTHON),'scripts/check_connections.py','--require-verified'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    from check_connections import fingerprint,values,CHECK_VERSION
    try:age=(datetime.now(timezone.utc)-datetime.fromisoformat(connections['checked_at'])).total_seconds()
    except (KeyError,ValueError):age=-1
    fresh=connections.get('version')==CHECK_VERSION and connections.get('fingerprint')==fingerprint(values()) and 0<=age<86400
    storage_ready=fresh and all(connections.get('checks',{}).get(s,{}).get('status')=='passed' for s in ('upstash','firebase','neon','r2')) and connections.get('mode')=='live'
    if selected('storage') and not args.local:
        if storage_ready:run('storage','Live managed-storage integration',[PYTHON,'backend/scripts/verify_storage.py'],'Isolated live Redis lease/transactions/events, Firestore history, private R2 put/get and Neon retrieval; fixture cleanup included.',timeout=180)
        else:record('storage','Live managed-storage integration',1,'Blocked by failed storage connection probes; no live fixture writes attempted.')
    if selected('provider') and not args.local:
        if fresh and connections.get('checks',{}).get('groq',{}).get('status')=='passed':run('provider','Live Groq completion',[PYTHON,'backend/scripts/verify_provider.py'],'One bounded Groq completion for the selected NOVA model; no user history or notifications.',timeout=150)
        else:record('provider','Live Groq completion',1,'Blocked by failed Groq connection probe; no AI completion attempted.')
    production=False
    if selected('build') and not args.local:
        if current:production=run('build','Frontend production build',['npm','run','build'],'Production build passed after the current six-service connection gate.',task='frontend-build',cwd=ROOT/'frontend',timeout=600)
        else:record('build','Frontend production build',1,'Blocked by the required live connection gate; production build not attempted.',task='frontend-build')
    if selected('office-browser'):run('office-browser','Standalone office browser verification',['node','tests/office-browser.mjs'],'Desktop/mobile, both themes, 15 cabins, details, walking demo, cancellation and reduced motion.',cwd=ROOT/'frontend',timeout=120)
    if selected('browser'):browser(production)
    if selected('container'):
        available=bool(__import__('shutil').which('docker'))
        if available:run('container','Container configuration',['docker','compose','config','--quiet'],'Compose configuration parsed; actual container deployment remains separate.')
        else:record('container','Container configuration',1,'Docker unavailable; container validation/deployment not attempted.')
    generate();return 0 if all(r['exit_code']==0 for r in RESULTS.values()) else 1

if __name__=='__main__':sys.exit(main())
