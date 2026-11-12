"""Specialist tools. Scoped user data, safe file paths, explicit command approvals."""
import asyncio
import hashlib
import json
import os
import shlex
import subprocess
import uuid
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile
import httpx
from .execution import AGENTS
from . import jobstore as db,repository as repo,object_store,rag

ROOT=Path(os.getenv('SYSTEM_ROOT') or db.BACKEND.parent).expanduser().resolve()
MAX_FILE=20*1024*1024
COMMON={'get_current_time','memory_search','save_memory','get_profile','update_profile','list_tasks','create_task','complete_task','list_files','read_file','write_file'}
GRANTS={a:COMMON|set(spec.tools) for a,spec in AGENTS.items()}
for a in ('nova','michel','zeus','oracle'):GRANTS[a]|={'list_dir','read_system_file','request_command'}
for a in ('friday','drake','gaya','elena'):GRANTS[a]|={'get_weather','get_news'}
for a in ('pepper','kratos','athena'):GRANTS[a]|={'journal_add','journal_recent','habit_add','habit_log','habit_status','workout_log','workout_recent'}
for a in ('gecko','stark'):GRANTS[a]|={'get_crypto_price','watchlist_add','watchlist_list'}


def schema(name,description,properties=None,required=None):
    return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties or {},'required':required or []}}}
S=lambda description:{'type':'string','description':description}
SCHEMAS={s['function']['name']:s for s in [
 schema('get_current_time','Get the actual UTC date and time.'),
 schema('memory_search','Search this user memory.',{'query':S('Search terms')},['query']),
 schema('save_memory','Save an important user fact.',{'content':S('Fact to remember')},['content']),
 schema('get_profile','Read the current user profile.'),
 schema('update_profile','Save a user profile fact.',{'key':S('Fact name'),'value':S('Fact value')},['key','value']),
 schema('list_tasks','Read this user task list.'),
 schema('create_task','Create a to-do/reminder; this records work, it does not execute an AI workflow.',{'title':S('Title'),'due_at':S('Optional ISO 8601 time including timezone'),'notes':S('Notes')},['title']),
 schema('complete_task','Mark a user to-do complete.',{'task_id':S('Task ID')},['task_id']),
 schema('list_files','List the current user uploaded/generated files.'),
 schema('read_file','Read a user file as text, PDF or DOCX.',{'filename':S('Filename')},['filename']),
 schema('write_file','Create an output file in the current user private file storage.',{'filename':S('Filename'),'content':S('Text content')},['filename','content']),
 schema('list_dir','List paths inside the configured system root; credentials are hidden.',{'path':S('Relative directory')}),
 schema('read_system_file','Read code inside the configured root; secret files are forbidden.',{'path':S('Relative file path')},['path']),
 schema('request_command','Request explicit user approval for a supported project command. Does not run until approved.',{'command':S('Command: pwd, ls, git status/diff/log, or npm run build/test/lint')},['command']),
 schema('web_search','Find actual public search results; returns source URLs.',{'query':S('Search query')},['query']),
 schema('get_news','Read a public RSS news feed; returns actual headlines and URLs.'),
 schema('get_weather','Read forecast from Open-Meteo.',{'location':S('City')},['location']),
 schema('get_crypto_price','Read CoinGecko market price.',{'coin':S('CoinGecko coin ID, e.g. bitcoin')},['coin']),
 schema('journal_add','Save a journal entry.',{'entry':S('User entry'),'mood':S('Optional mood')},['entry']),
 schema('journal_recent','Read recent journal entries.'),
 schema('habit_add','Track a habit.',{'name':S('Habit name')},['name']),
 schema('habit_log','Log completion of a tracked habit.',{'name':S('Habit name')},['name']),
 schema('habit_status','Read recorded habit completion history.'),
 schema('workout_log','Record a workout.',{'activity':S('Activity'),'detail':S('Sets/reps/duration')},['activity']),
 schema('workout_recent','Read recorded workouts.'),
 schema('watchlist_add','Track an asset.',{'symbol':S('Symbol')},['symbol']),
 schema('watchlist_list','Read this user watchlist.'),
]}


SYSTEM_TOOLS={'list_dir','read_system_file','request_command'}

def privileged(user):
    return user in ('owner','local-owner') or bool(os.getenv('SYSTEM_ACCESS_USER_ID')) and user==os.getenv('SYSTEM_ACCESS_USER_ID')

def schemas_for(agent,user=None):
    return [SCHEMAS[n] for n in sorted(GRANTS.get(agent,set())) if n in SCHEMAS and (user is None or n not in SYSTEM_TOOLS or privileged(user))]


def safe_name(filename):
    if not filename or filename in ('.','..','.locks') or '/' in filename or '\\' in filename or '\x00' in filename or len(filename)>120:raise ValueError('Use a filename without directories, up to 120 characters.')
    return filename


def read_text(path):
    if path.stat().st_size>MAX_FILE:raise ValueError('File exceeds the 20 MB limit')
    return extract_text(path.name,path.read_bytes())


def extract_text(filename,data):
    from io import BytesIO
    suffix=Path(filename).suffix.lower()
    if suffix=='.pdf':
        from pypdf import PdfReader
        return '\n'.join((p.extract_text() or '') for p in PdfReader(BytesIO(data)).pages)[:80000]
    if suffix=='.docx':
        with ZipFile(BytesIO(data)) as archive:
            item=archive.getinfo('word/document.xml')
            if item.file_size>MAX_FILE:raise ValueError('DOCX extraction exceeds the limit')
            tree=ElementTree.fromstring(archive.read(item))
            return ' '.join(n.text or '' for n in tree.iter() if n.tag.endswith('}t'))[:80000]
    if suffix in {'.txt','.md','.csv','.json','.yaml','.yml','.toml','.py','.js','.jsx','.ts','.tsx','.css','.html','.sql','.sh','.rs','.go','.java','.xml','.log','.ini'}:
        return data.decode(errors='replace')[:80000]
    raise ValueError('This format is stored but cannot be indexed. Use text, code, PDF or DOCX.')


def file_id(filename):return 'file-'+hashlib.sha256(safe_name(filename).encode()).hexdigest()

def save_file(user,filename,data):
    safe_name(filename)
    if len(data)>MAX_FILE:raise ValueError('Files must be 20 MB or smaller')
    ident=file_id(filename);generation=str(uuid.uuid4())
    object_key=f'users/{db.user_key(user)}/{ident}/{generation}/{filename}'
    object_store.put(object_key,data)
    warning=None;chunks=0;readable=False
    try:
        text=extract_text(filename,data);readable=True
        chunks=rag.replace(user,ident,generation,filename,text)
    except Exception as exc:warning=str(exc) if isinstance(exc,ValueError) else f'File could not be indexed ({type(exc).__name__}); re-upload to retry'
    # Immutable object and chunks are prepared before publishing one coherent pointer.
    # Concurrent replacement can only select a complete generation, never mixed data.
    payload={'filename':filename,'object_key':object_key,'generation':generation,'size_bytes':len(data),'indexed':bool(chunks),'chunks_indexed':chunks,'readable':readable,'warning':warning}
    # Retain prepared data on an uncertain Firestore acknowledgement, since the
    # pointer may already have committed and must remain downloadable.
    row,previous=repo.put(user,'file',payload,ident,with_previous=True)
    if previous:cleanup_file(user,previous)
    return row


def file_bytes(user,filename):
    row=repo.get(user,file_id(filename),'file')
    if not row:raise FileNotFoundError('File not found')
    return object_store.get(row['object_key'])


def read_file(user,filename):return extract_text(filename,file_bytes(user,filename))


def delete_file(user,filename):
    # Atomically detach exactly the generation being removed. A concurrent upload
    # publishes its own generation and cannot have its new object removed here.
    row=repo.take(user,file_id(filename),'file')
    if not row:return {'ok':False}
    warning=cleanup_file(user,row)
    return {'ok':True,**({'warning':warning} if warning else {})}

def cleanup_file(user,row):
    try:
        object_store.delete(row['object_key'])
        rag.delete(user,row['id'],row['generation'])
        return None
    except Exception as error:
        # Durable cleanup records also cover partial deletion after a service outage.
        ident=db.user_key(user+':'+row['id']+':'+row['generation'])
        db.put('migrations',ident,{'id':ident,'kind':'file_cleanup','user_id':user,'file':row,'created_at':db.now()})
        return f'File removed from active access; storage cleanup pending ({type(error).__name__})'


def system_path(raw):
    path=(ROOT/raw).resolve()
    if not path.is_relative_to(ROOT):raise ValueError('Path escapes SYSTEM_ROOT')
    for part in path.relative_to(ROOT).parts:
        lower=part.lower()
        if lower.startswith('.env') or lower in {'.aws','.ssh','.git','.codex','.agents','data','venv','.venv','node_modules'} or any(s in lower for s in ('private_key','service-account','serviceaccount','firebase-adminsdk')) or lower.endswith(('.pem','.key','.p12')):raise ValueError('Credential and private-data paths are off limits')
    return path


def validate_command(command):
    argv=shlex.split(command)
    valid=argv==['pwd'] or argv==['ls'] or argv in (['git','status'],['git','status','--short'],['git','diff','--stat'],['git','log','--oneline'],['npm','run','build'],['npm','run','test'],['npm','test'],['npm','run','lint'])
    if not valid or any(x in command for x in (';','|','&','>','<','`','\n','$')):raise ValueError('Only supported project commands are available: pwd, ls, git status/diff/log, npm run build/test/lint. No shell syntax.')
    return argv


async def dispatch(user,agent,name,args):
    if name not in GRANTS.get(agent,set()) or name not in SCHEMAS:return {'ok':False,'error':'Tool is not granted to this agent'}
    if name in SYSTEM_TOOLS and not privileged(user):return {'ok':False,'error':'System tools are reserved for the workspace owner. Configure SYSTEM_ACCESS_USER_ID for the owner Firebase UID.'}
    if not isinstance(args,dict):return {'ok':False,'error':'Tool arguments must be an object'}
    try:
        if name=='get_current_time':return {'ok':True,'utc':db.now()}
        if name=='memory_search':return {'ok':True,'results':repo.recall(user,args.get('query',''))}
        if name=='save_memory':return {'ok':True,'memory':repo.put(user,'memory',{'content':str(args['content'])[:8000],'kind':'fact','agent_id':agent})}
        if name=='get_profile':return {'ok':True,'facts':{r['key']:r['value'] for r in repo.list_for(user,'profile')}}
        if name=='update_profile':
            prior=next((r for r in repo.list_for(user,'profile') if r['key']==args['key']),None)
            return {'ok':True,'fact':repo.put(user,'profile',args,prior['id'] if prior else None)}
        if name=='list_tasks':return {'ok':True,'tasks':repo.list_for(user,'task')}
        if name=='create_task':
            if not str(args.get('title','')).strip():raise ValueError('Task title cannot be blank')
            due=args.get('due_at')
            if due:
                parsed=datetime.fromisoformat(due.replace('Z','+00:00'))
                if not parsed.tzinfo:raise ValueError('Reminder times need a timezone')
                due=parsed.astimezone(timezone.utc).isoformat()
            return {'ok':True,'task':repo.put(user,'task',{'title':str(args['title'])[:300],'notes':args.get('notes'),'due_at':due,'status':'open','notified':False})}
        if name=='complete_task':
            row=repo.get(user,args['task_id'],'task')
            if not row:raise ValueError('Task not found')
            return {'ok':True,'task':repo.put(user,'task',{**row,'status':'done'},row['id'])}
        if name=='list_files':return {'ok':True,'files':repo.list_for(user,'file')}
        if name=='read_file':return {'ok':True,'content':await asyncio.to_thread(read_file,user,args['filename'])}
        if name=='write_file':return {'ok':True,'file':await asyncio.to_thread(save_file,user,args['filename'],str(args['content']).encode())}
        if name=='list_dir':
            path=system_path(args.get('path',''));out=[]
            for child in path.iterdir():
                try:system_path(str(child.relative_to(ROOT)))
                except ValueError:continue
                out.append({'name':child.name,'directory':child.is_dir()})
            return {'ok':True,'entries':out[:200]}
        if name=='read_system_file':return {'ok':True,'content':await asyncio.to_thread(read_text,system_path(args['path']))}
        if name=='request_command':
            command=args['command'];validate_command(command)
            from .execution import context
            ctx=context.get() or {}
            ident=db.next_id('action')
            def request(tx):
                if ctx.get('workflow_id'):
                    run=tx.get('workflows',ctx['workflow_id'])
                    if not run or run['user_id']!=user or run['status']=='cancelled':raise ValueError('Workflow cancelled; no new approval will be created')
                prior=tx.rows('actions',user_id=user,step_id=ctx.get('step_id'),workflow_id=ctx.get('workflow_id'),summary=command,status='pending')
                if prior:return prior[0]['id']
                tx.put('actions',ident,{'id':ident,'user_id':user,'agent_id':agent,'workflow_id':ctx.get('workflow_id'),'step_id':ctx.get('step_id'),'kind':'command','summary':command,'payload':{'command':command,'cwd':str(ROOT)},'created_at':db.now(),'status':'pending','result':None,'resolved_at':None})
                return ident
            actual=db.atomic(['workflows','actions'],request)
            return {'ok':False,'status':'awaiting approval','action_id':actual,'note':'This command has NOT run. Review it in Alerts. Do not request it again.'}
        simple={'journal_add':('journal','entry'),'habit_add':('habit','name'),'habit_log':('habit_log','name'),'workout_log':('workout','activity'),'watchlist_add':('watchlist','symbol')}
        if name in simple:
            kind,key=simple[name]
            if not str(args.get(key,'')).strip():raise ValueError(f'{key} is required')
            return {'ok':True,'record':repo.put(user,kind,args)}
        reads={'journal_recent':'journal','habit_status':'habit_log','workout_recent':'workout','watchlist_list':'watchlist'}
        if name in reads:return {'ok':True,'records':repo.list_for(user,reads[name]),'note':'Only recorded history is shown; no inferred streaks.'}
        async with httpx.AsyncClient(timeout=15,follow_redirects=True) as client:
            if name=='web_search':
                query=args['query'];key=os.getenv('TAVILY_API_KEY','')
                if key and not key.startswith('your'):
                    r=await client.post('https://api.tavily.com/search',json={'api_key':key,'query':query,'max_results':5});r.raise_for_status();return {'ok':True,'results':r.json().get('results',[])}
                r=await client.get('https://www.google.com/search',params={'q':query,'num':5});r.raise_for_status()
                from html.parser import HTMLParser
                from urllib.parse import parse_qs,urlparse
                class Links(HTMLParser):
                    def __init__(self):super().__init__();self.links=[]
                    def handle_starttag(self,tag,attrs):
                        href=dict(attrs).get('href','')
                        if tag=='a' and href.startswith('/url?q='):
                            url=parse_qs(urlparse(href).query).get('q',[''])[0]
                            if url.startswith('http'):self.links.append(url)
                parser=Links();parser.feed(r.text)
                if not parser.links:raise ValueError('Search provider returned no usable sources. Configure TAVILY_API_KEY for reliable search.')
                return {'ok':True,'urls':list(dict.fromkeys(parser.links))[:8]}
            if name=='get_news':
                r=await client.get('https://feeds.bbci.co.uk/news/rss.xml');r.raise_for_status();tree=ElementTree.fromstring(r.content)
                return {'ok':True,'headlines':[{'title':i.findtext('title'),'url':i.findtext('link')} for i in tree.findall('.//item')[:10]]}
            if name=='get_weather':
                r=await client.get('https://geocoding-api.open-meteo.com/v1/search',params={'name':args['location'],'count':1});r.raise_for_status();places=r.json().get('results',[])
                if not places:raise ValueError('Location not found')
                p=places[0];r=await client.get('https://api.open-meteo.com/v1/forecast',params={'latitude':p['latitude'],'longitude':p['longitude'],'current':'temperature_2m,precipitation,wind_speed_10m'});r.raise_for_status();return {'ok':True,'location':p['name'],'forecast':r.json()}
            if name=='get_crypto_price':
                r=await client.get('https://api.coingecko.com/api/v3/simple/price',params={'ids':args['coin'],'vs_currencies':'usd,inr','include_24hr_change':'true'});r.raise_for_status();return {'ok':True,'prices':r.json()}
        return {'ok':False,'error':'Integration is not available'}
    except Exception as exc:return {'ok':False,'error':str(exc) if isinstance(exc,(ValueError,KeyError)) else f'Tool failed ({type(exc).__name__}); integration may be unavailable'}


async def approve(user,action_id):
    if not privileged(user):return {'ok':False,'error':'Only the workspace owner may run system commands'}
    def claim(tx):
        row=tx.get('actions',action_id)
        if not row or row['user_id']!=user or row['status']!='pending':return None
        if row['workflow_id']:
            run=tx.get('workflows',row['workflow_id'])
            if not run or run['status']=='cancelled':return None
        row.update(status='executing',executing_at=db.now(),worker_token=db.fence.get());return dict(row)
    row=db.atomic(['actions','workflows'],claim)
    if not row:return {'ok':False,'error':'Action unavailable or already resolved'}
    try:
        argv=validate_command(row['payload']['command'])
        db.assert_lease()
        command_root=ROOT/'frontend' if argv[0]=='npm' and not (ROOT/'package.json').is_file() and (ROOT/'frontend/package.json').is_file() else ROOT
        def run():return subprocess.run(argv,cwd=command_root,capture_output=True,text=True,timeout=60,env={'PATH':os.getenv('PATH',''),'LANG':'en_US.UTF-8','HOME':str(ROOT)})
        result=await asyncio.to_thread(run)
        outcome={'ok':result.returncode==0,'exit_code':result.returncode,'output':(result.stdout+result.stderr)[-16000:]}
    except asyncio.CancelledError:
        db.update('actions',action_id,{'status':'interrupted','resolved_at':db.now()},status='executing');raise
    except Exception as exc:outcome={'ok':False,'error':f'Command failed ({type(exc).__name__})'}
    db.update('actions',action_id,{'status':'done' if outcome['ok'] else 'failed','result':outcome,'resolved_at':db.now()},status='executing')
    db.event(user,'approval_resolved',workflow_id=row['workflow_id'],step_id=row['step_id'],agent_id=row['agent_id'],action_id=action_id,result=outcome)
    return outcome
