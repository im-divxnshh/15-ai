"""Authenticated application contract for NOVA's durable runtime."""
import asyncio
import hmac
import json
import os
from datetime import datetime,timedelta,timezone
from typing import Literal
from fastapi import APIRouter,Depends,Header,HTTPException,Query,Request
from fastapi.routing import APIRoute
from fastapi.responses import Response,StreamingResponse
from pydantic import BaseModel,Field
from app.core.runtime import jobstore as db,workflows,execution,provider,repository as repo,delivery,tools,telegram
from app.core.registry.agents import AGENTS

def current_user(authorization:str|None=Header(None)):
    token=authorization.removeprefix('Bearer ').strip() if authorization and authorization.startswith('Bearer ') else ''
    app_token=os.getenv('APP_TOKEN','')
    if app_token and token and hmac.compare_digest(token,app_token):return 'owner'
    if token:
        try:
            from firebase_admin import auth
            from app.core.runtime.firebase_store import admin_app
            return auth.verify_id_token(token,app=admin_app(),check_revoked=True)['uid']
        except HTTPException:raise
        except db.StorageUnavailable:raise HTTPException(503,'Firebase authentication configuration is unavailable') from None
        except (ImportError,ValueError,json.JSONDecodeError):raise HTTPException(503,'Firebase authentication configuration is unavailable. Check inline credentials in backend/.env.') from None
        except Exception:raise HTTPException(401,'Invalid or expired access token') from None
    if os.getenv('ALLOW_LOCAL_NO_AUTH','false').lower()=='true':return 'local-owner'
    raise HTTPException(401,'Sign in with Firebase or connect using your backend APP_TOKEN.')


def connected_storage(user=Depends(current_user)):
    if not db.storage_ready():raise HTTPException(503,db.storage_info()['reason'])


class PersistenceRoute(APIRoute):
    def __init__(self,path,*args,dependencies=None,**kwargs):
        dependencies=list(dependencies or [])
        if path not in ('/api/health','/api/system/health','/api/session','/api/office/roster') and not any(d.dependency is connected_storage for d in dependencies):
            dependencies.append(Depends(connected_storage))
        super().__init__(path,*args,dependencies=dependencies,**kwargs)


router=APIRouter(prefix='/api',route_class=PersistenceRoute)


class ChatRequest(BaseModel):
    message:str=Field(min_length=1,max_length=8000)
    agent_id:str|None=None

class PlanRequest(BaseModel):
    instruction:str=Field(min_length=1,max_length=12000)
    mode:Literal['sequential','parallel']='sequential'

class SettingsRequest(BaseModel):
    email:str=Field(default='',max_length=254,pattern=r'^(?:[^\s@]+@[^\s@]+\.[^\s@]+)?$')
    telegram_chat_id:str=Field(default='',max_length=40,pattern=r'^(?:-?[0-9]+)?$')
    email_enabled:bool=False
    telegram_enabled:bool=False
    categories:list[Literal['updates','results','failures','replies','reminders','summaries']]=Field(default_factory=lambda:delivery.CATEGORIES.copy())

class TextRequest(BaseModel):content:str=Field(min_length=1,max_length=8000)
class ProfileRequest(BaseModel):key:str=Field(min_length=1,max_length=80);value:str=Field(max_length=8000)
class TaskRequest(BaseModel):title:str=Field(min_length=1,max_length=300);due_at:str|None=None;notes:str=''
class ToggleRequest(BaseModel):enabled:bool
class ReadRequest(BaseModel):ids:list[str]|None=None
class RoutineRequest(BaseModel):
    title:str=Field(min_length=1,max_length=160)
    instruction:str=Field(min_length=1,max_length=8000)
    agent_id:str='friday'
    interval_min:int=Field(default=720,ge=5,le=10080)
    enabled:bool=True


@router.get('/health')
@router.get('/system/health')
def health():
    missing=[]
    database_ready=False
    if db.storage_ready():
        try:
            db.init()
            database_ready=True
        except Exception:missing.append('Persistent database unavailable')
    else:missing.append(db.storage_info()['reason'])
    if not delivery.configured(os.getenv('GROQ_API_KEY')):missing.append('GROQ_API_KEY')
    if not (os.getenv('APP_TOKEN') or os.getenv('FIREBASE_CREDENTIALS') or os.getenv('ALLOW_LOCAL_NO_AUTH')=='true'):missing.append('FIREBASE_CREDENTIALS or APP_TOKEN')
    return {'status':'degraded' if missing else 'ok','agents':{'loaded':len(AGENTS),'errors':{}},'missing_env':missing,'worker':workflows.status(),'scheduler':{'running':workflows.status()['running']},'store':db.storage_info(),'database':{'connected':database_ready},'embeddings':{'ready':tools.rag.init.cache_info().currsize>0,'configured':bool(os.getenv('NEON_URL')),'model':'local-token-hash-v1-384','vector_search':tools.rag.init.cache_info().currsize>0,'semantic':False},'files':{'backend':'r2','configured':tools.object_store.ready()},'delivery':delivery.ready(),'provider':'groq','auth':{'firebase':bool(os.getenv('FIREBASE_CREDENTIALS')),'token':bool(os.getenv('APP_TOKEN')),'local':os.getenv('ALLOW_LOCAL_NO_AUTH')=='true'},'voice':'deferred'}


@router.get('/office/roster')
def public_roster():
    return {'agents':[{'id':a.id,'name':a.name,'role':a.role,'accent':a.accent,'status':'unavailable'} for a in sorted(AGENTS.values(),key=lambda a:(a.id!='nova',a.layer,a.id))],'activity_available':False}


@router.get('/session')
def session(user=Depends(current_user)):return {'user_id':user}


@router.get('/agents')
def agents(user=Depends(current_user)):
    activity=sorted(db.records('activity',user_id=user),key=lambda r:r['started_at'],reverse=True)
    out=[]
    for spec in sorted(AGENTS.values(),key=lambda a:(a.id!='nova',a.layer,a.id)):
        rows=[r for r in activity if r['agent_id']==spec.id];busy=next((r for r in rows if r['status']=='working'),None);latest=rows[0] if rows else {}
        out.append({'id':spec.id,'name':spec.name,'role':spec.role,'accent':spec.accent,'layer':spec.layer,'is_orchestrator':spec.id=='nova','cabin':{'row':0,'col':0,'w':1,'h':1},'model':execution.model(spec.id),'status':'working' if busy else latest.get('status','idle'),'active':bool(busy),'current_task':busy['task'] if busy else None,'last_task':latest.get('task'),'last_active_at':latest.get('finished_at'),'calls_handled':sum(bool(r['finished_at']) for r in rows),'tasks':[spec.role,spec.prompt],'handles':[spec.role],'tools':[s['function']['name'] for s in tools.schemas_for(spec.id,user)]})
    return {'agents':out,'count':len(out)}


@router.post('/agents/reload')
def reload_agents(user=Depends(current_user)):return {'reloaded':len(AGENTS),'errors':{}}


@router.post('/chat')
async def chat(req:ChatRequest,user=Depends(current_user)):
    if req.agent_id and req.agent_id not in AGENTS:raise HTTPException(422,'Unknown agent')
    try:turn=await asyncio.wait_for(execution.respond(user,req.message,req.agent_id),timeout=180)
    except TimeoutError:raise HTTPException(504,'Agent request timed out; review recorded tool actions before retrying') from None
    delivery.queue(user,('Failed reply' if turn.error else AGENTS[turn.handled_by].name+' replied'),turn.reply or turn.error,'failures' if turn.error else 'replies')
    return {'reply':turn.reply or turn.error,'handled_by':turn.handled_by,'agent':{'id':turn.handled_by,'name':AGENTS[turn.handled_by].name},'agents_involved':turn.agents,'routing':{'reason':'Actual routing is recorded in Activity','confidence':None,'degraded':bool(turn.error)},'error':turn.error}


@router.get('/history')
def history(agent_id:str='__auto__',limit:int=Query(40,ge=1,le=200),user=Depends(current_user)):return {'messages':repo.history(user,agent_id,limit)}


@router.delete('/history')
def clear_history(agent_id:str|None=None,user=Depends(current_user)):
    for row in repo.list_for(user,'message',100000):
        if agent_id is None or row['agent_id']==agent_id:repo.delete(user,row['id'])
    return {'ok':True}


@router.post('/workflows/plan')
async def make_plan(req:PlanRequest,user=Depends(current_user)):
    try:return (await asyncio.wait_for(workflows.plan(req.instruction,req.mode,user),timeout=90)).model_dump()
    except TimeoutError:raise HTTPException(504,'NOVA planning timed out') from None
    except (provider.ProviderError,ValueError) as exc:raise HTTPException(502 if isinstance(exc,provider.ProviderError) else 422,str(exc)) from None


@router.post('/workflows',status_code=201)
def create_workflow(req:workflows.BatchInput,user=Depends(current_user)):return workflows.create(user,req)


@router.get('/workflows')
def list_workflows(user=Depends(current_user)):return {'workflows':db.listing(user),'worker':workflows.status()}


@router.get('/workflows/{ident}')
def workflow(ident:str,after:int=Query(0,ge=0),user=Depends(current_user)):
    run=db.get(ident,user)
    if not run:raise HTTPException(404,'Workflow not found')
    return {**run,'events':db.events(user,ident,after)}


@router.post('/workflows/{ident}/{action}')
def control(ident:str,action:Literal['pause','resume','cancel','retry'],user=Depends(current_user)):
    try:return workflows.control(user,ident,action)
    except KeyError:raise HTTPException(404,'Workflow not found') from None
    except ValueError as exc:raise HTTPException(409,str(exc)) from None


@router.get('/workflows/{ident}/stream')
async def stream(ident:str,request:Request,after:int=Query(0,ge=0),user=Depends(current_user)):
    if not await asyncio.to_thread(db.get,ident,user):raise HTTPException(404,'Workflow not found')
    async def generate():
        cursor=after;count=0;yield 'event: ready\ndata: {}\n\n'
        while not await request.is_disconnected():
            for event in await asyncio.to_thread(db.events,user,ident,cursor,100):
                cursor=event['id'];yield f'id: {cursor}\ndata: {json.dumps(event)}\n\n'
            count+=1
            if count%20==0:yield ': keep-alive\n\n'
            await asyncio.sleep(.5)
    return StreamingResponse(generate(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})


@router.get('/events')
def events(limit:int=Query(40,ge=1,le=200),user=Depends(current_user)):
    return {'events':db.recent_events(user,limit)}


@router.get('/delivery/settings')
def prefs(user=Depends(current_user)):return delivery.settings(user)
@router.get('/telegram/status')
def telegram_status(user=Depends(current_user)):
    cfg=telegram.config()
    return telegram.status() if cfg['user']==user else {'configured':False,'running':False,'state':'not_connected'}
@router.put('/delivery/settings')
def save_prefs(req:SettingsRequest,user=Depends(current_user)):return delivery.save_settings(user,req.model_dump())
@router.get('/delivery')
def deliveries(user=Depends(current_user)):return {'deliveries':delivery.history(user)}
@router.post('/delivery/test')
def test_delivery(user=Depends(current_user)):
    ids=delivery.queue(user,'Connection test','This is your NOVA OS connection test. Confirm this message arrives at your destination.',is_test=True)
    if not ids:raise HTTPException(409,'Enable a channel in your preferences before testing')
    return {'delivery_ids':ids,'status':'pending'}
@router.post('/delivery/{ident}/retry')
def retry_delivery(ident:int,user=Depends(current_user)):
    if not delivery.retry(user,ident):raise HTTPException(409,'Delivery unavailable or not retryable')
    return {'ok':True}


@router.get('/memory')
def memory(user=Depends(current_user)):return {'memories':repo.list_for(user,'memory')}
@router.get('/memory/search')
def search(q:str=Query(min_length=1),user=Depends(current_user)):return {'results':repo.recall(user,q)}
@router.post('/memory')
def remember(req:TextRequest,user=Depends(current_user)):return {'ok':True,'memory':repo.put(user,'memory',{'content':req.content,'kind':'fact','agent_id':None})}
@router.delete('/memory/{ident}')
def forget(ident:str,user=Depends(current_user)):return {'ok':repo.delete(user,ident,'memory')}
@router.get('/profile')
def profile(user=Depends(current_user)):return {'facts':{r['key']:r['value'] for r in repo.list_for(user,'profile')}}
@router.post('/profile')
def save_profile(req:ProfileRequest,user=Depends(current_user)):
    row=next((r for r in repo.list_for(user,'profile') if r['key']==req.key),None)
    return {'ok':True,'fact':repo.put(user,'profile',req.model_dump(),row['id'] if row else None)}
@router.delete('/profile/{key}')
def forget_profile(key:str,user=Depends(current_user)):
    for row in repo.list_for(user,'profile'):
        if row['key']==key:repo.delete(user,row['id'])
    return {'ok':True}


@router.get('/tasks')
def tasks(status:str='open',user=Depends(current_user)):return {'tasks':[r for r in repo.list_for(user,'task') if status=='all' or r['status']==status]}
@router.post('/tasks')
async def task(req:TaskRequest,user=Depends(current_user)):
    result=await tools.dispatch(user,'friday','create_task',req.model_dump())
    if not result['ok']:raise HTTPException(422,result['error'])
    return result
@router.post('/tasks/{ident}/complete')
async def complete_task(ident:str,user=Depends(current_user)):return await tools.dispatch(user,'friday','complete_task',{'task_id':ident})
@router.delete('/tasks/{ident}')
def delete_task(ident:str,user=Depends(current_user)):return {'ok':repo.delete(user,ident,'task')}


@router.get('/files')
def files(user=Depends(current_user)):return {'files':repo.list_for(user,'file')}
@router.put('/files/{filename}',openapi_extra={'requestBody':{'required':True,'content':{'application/octet-stream':{'schema':{'type':'string','format':'binary'}}}}})
async def upload(filename:str,request:Request,user=Depends(current_user)):
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>tools.MAX_FILE:raise HTTPException(413,'File limit is 20 MB')
    try:return {'ok':True,'file':await asyncio.to_thread(tools.save_file,user,filename,bytes(data))}
    except ValueError as exc:raise HTTPException(422,str(exc)) from None
@router.get('/files/{filename}')
def download(filename:str,user=Depends(current_user)):
    try:data=tools.file_bytes(user,filename)
    except ValueError as exc:raise HTTPException(422,str(exc)) from None
    except FileNotFoundError:raise HTTPException(404,'File not found') from None
    from urllib.parse import quote
    return Response(data,media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(filename,safe=''),'Cache-Control':'private, no-store'})
@router.delete('/files/{filename}')
def delete_file(filename:str,user=Depends(current_user)):
    try:return tools.delete_file(user,filename)
    except ValueError as exc:raise HTTPException(422,str(exc)) from None


@router.get('/routines')
def routines(user=Depends(current_user)):return {'routines':repo.list_for(user,'routine'),'runs':[]}
@router.post('/routines')
def new_routine(req:RoutineRequest,user=Depends(current_user)):
    if req.agent_id not in AGENTS:raise HTTPException(422,'Unknown agent')
    return {'ok':True,'routine':repo.put(user,'routine',{**req.model_dump(),'run_count':0,'last_run_at':None,'last_error':None,'next_run_at':(datetime.now(timezone.utc)+timedelta(minutes=req.interval_min)).isoformat()})}
@router.post('/routines/{ident}/toggle')
def toggle(ident:str,req:ToggleRequest,user=Depends(current_user)):
    row=repo.get(user,ident,'routine')
    if not row:raise HTTPException(404,'Routine not found')
    return {'ok':True,'routine':repo.put(user,'routine',{**row,'enabled':req.enabled},ident)}
@router.post('/routines/run/{ident}')
def run_routine(ident:str,user=Depends(current_user)):
    row=repo.get(user,ident,'routine')
    if not row:raise HTTPException(404,'Routine not found')
    prior=db.get(row['workflow_id'],user) if row.get('workflow_id') else None
    if prior and prior['status'] in ('queued','running','paused','interrupted'):raise HTTPException(409,'Prior routine work is still active or needs review')
    run=workflows.create(user,workflows.BatchInput(title=row['title'],tasks=[workflows.StepInput(title=row['title'],instruction=row['instruction'],agent_id=row['agent_id'])]))
    repo.put(user,'routine',{**row,'workflow_id':run['id'],'run_count':row['run_count']+1,'last_run_at':db.now(),'next_run_at':(datetime.now(timezone.utc)+timedelta(minutes=row['interval_min'])).isoformat()},ident)
    return {'ok':True,'workflow_id':run['id']}
@router.delete('/routines/{ident}')
def delete_routine(ident:str,user=Depends(current_user)):return {'ok':repo.delete(user,ident,'routine')}


@router.get('/notifications')
def alerts(user=Depends(current_user)):
    rows=sorted([r for r in db.records('notices',user_id=user) if not r.get('is_test')],key=lambda r:r['created_at'],reverse=True)[:200];return {'notifications':rows,'unread':sum(not r.get('read_at') for r in rows)}
@router.post('/notifications/read')
def read_alerts(req:ReadRequest,user=Depends(current_user)):
    for row in db.records('notices',user_id=user):
        if req.ids is None or row['id'] in req.ids:db.update('notices',row['id'],{'read_at':db.now()},user_id=user)
    return {'ok':True}
@router.get('/actions')
def actions(user=Depends(current_user)):
    return {'actions':sorted(db.records('actions',user_id=user),key=lambda r:r['id'],reverse=True)[:100]}
@router.post('/actions/{ident}/approve')
async def approve(ident:int,user=Depends(current_user)):return await tools.approve(user,ident)
@router.post('/actions/{ident}/deny')
def deny(ident:int,user=Depends(current_user)):
    return {'ok':db.update('actions',ident,{'status':'denied','resolved_at':db.now()},user_id=user,status='pending')}
@router.get('/analytics')
def analytics(user=Depends(current_user)):
    runs=db.listing(user);return {'workflows':len(runs),'completed_tasks':sum(r['completed'] for r in runs),'failed_tasks':sum(s['status']=='failed' for r in runs for s in r['steps']),'worker':workflows.status()}
