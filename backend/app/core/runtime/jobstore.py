"""Upstash records, optimistic Lua transactions and distributed worker fencing.

Callbacks are pure: a transaction retry never repeats a model call or send.
Firestore stores user documents; Neon stores file chunks. No SQLite fallback.
"""
import copy
import hashlib
import json
import os
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
import httpx
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[3]
load_dotenv(BACKEND / '.env')
IMPLEMENTED_BACKEND = 'upstash'
TABLES = {'workflows', 'steps', 'activity', 'delivery_settings', 'deliveries', 'connection_tests', 'actions', 'migrations', 'notices'}
fence = ContextVar('redis_worker_fence', default=None)

class StorageUnavailable(RuntimeError): pass
class LeaseLost(StorageUnavailable): pass

def now(): return datetime.now(timezone.utc).isoformat()
def key(name): return os.getenv('REDIS_KEY_PREFIX', 'nova:v1') + ':' + name
def user_key(user): return hashlib.sha256(user.encode()).hexdigest()
def storage_ready():
    return IMPLEMENTED_BACKEND == 'upstash' and os.getenv('STORAGE_BACKEND', 'upstash') == 'upstash' and bool(os.getenv('UPSTASH_REDIS_REST_URL') and os.getenv('UPSTASH_REDIS_REST_TOKEN'))
def storage_info():
    return {'backend': 'upstash', 'implemented': True, 'configured': storage_ready(), 'reason': None if storage_ready() else 'Configure Upstash Redis REST credentials. SQLite fallback is disabled.'}

def command(*args):
    if not storage_ready(): raise StorageUnavailable(storage_info()['reason'])
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(os.environ['UPSTASH_REDIS_REST_URL'].rstrip('/'), headers={'Authorization': 'Bearer ' + os.environ['UPSTASH_REDIS_REST_TOKEN']}, json=list(args))
        if response.status_code != 200: raise StorageUnavailable(f'Upstash request failed (HTTP {response.status_code})')
        body = response.json()
        if 'error' in body: raise StorageUnavailable('Upstash rejected a storage command')
        return body['result']
    except StorageUnavailable: raise
    except Exception as error: raise StorageUnavailable(f'Upstash unavailable ({type(error).__name__})') from None

def script(source, keys, args=()): return command('EVAL', source, len(keys), *keys, *args)

READ = """
local out={}
for i=1,#KEYS,2 do out[#out+1]={redis.call('GET',KEYS[i]) or '0',redis.call('HGETALL',KEYS[i+1])} end
return cjson.encode(out)
"""
COMMIT = """
local n=tonumber(ARGV[1])
if ARGV[2]~='' and redis.call('GET',KEYS[#KEYS])~=ARGV[2] then return -1 end
local changes=cjson.decode(ARGV[3])
for i=1,n do if (redis.call('GET',KEYS[2*i-1]) or '0')~=changes[i].version then return 0 end end
for i=1,n do
 local delta=changes[i]
 for _,row in ipairs(delta.set) do redis.call('HSET',KEYS[2*i],row[1],row[2]) end
 for _,id in ipairs(delta.delete) do redis.call('HDEL',KEYS[2*i],id) end
 if #delta.set>0 or #delta.delete>0 then redis.call('INCR',KEYS[2*i-1]) end
end
return 1
"""
class View:
    def __init__(self, tables): self.tables=tables
    def rows(self, table, **filters): return [r for r in self.tables[table].values() if all(r.get(k)==v for k,v in filters.items())]
    def get(self, table, ident): return self.tables[table].get(str(ident))
    def put(self, table, ident, row): self.tables[table][str(ident)]=copy.deepcopy(row); return row
    def delete(self, table, ident): return self.tables[table].pop(str(ident),None) is not None

def atomic(tables, operation):
    tables=list(dict.fromkeys(tables))
    if not tables or not set(tables)<=TABLES: raise ValueError('Unknown execution table')
    keys=[k for t in tables for k in (key(t+':revision'),key(t))]
    for attempt in range(8):
        snapshots=json.loads(script(READ,keys)); before={}; versions={}
        for name,(version,entries) in zip(tables,snapshots):
            versions[name]=str(version)
            before[name]={entries[i]:json.loads(entries[i+1]) for i in range(0,len(entries),2)}
        view=View(copy.deepcopy(before)); result=operation(view)
        changes=[{'version':versions[t], 'set':[[ident,json.dumps(row,default=str)] for ident,row in view.tables[t].items() if before[t].get(ident)!=row], 'delete':[ident for ident in before[t] if ident not in view.tables[t]]} for t in tables]
        committed=script(COMMIT,keys+[key('worker:lease')],[len(tables),fence.get() or '',json.dumps(changes)])
        if committed==1: return result
        if committed==-1: raise LeaseLost('Worker lease lost; review interrupted work before retrying')
        time.sleep(.005*(attempt+1))
    raise StorageUnavailable('Execution state changed concurrently; retry this request')

def records(table, **filters):
    if table not in TABLES: raise ValueError('Unknown execution table')
    rows=[json.loads(r) for r in command('HVALS',key(table)) or []]
    return [r for r in rows if all(r.get(k)==v for k,v in filters.items())]
def put(table, ident, row): return atomic([table],lambda tx:tx.put(table,ident,row))
def update(table, ident, changes, **conditions):
    def change(tx):
        row=tx.get(table,ident)
        if not row or any(row.get(k)!=v for k,v in conditions.items()): return False
        row.update(changes); return True
    return atomic([table],change)
def next_id(kind): return int(command('INCR',key(kind+':sequence')))
def init():
    if command('PING')!='PONG': raise StorageUnavailable('Upstash PING failed')
def assert_lease():
    token=fence.get()
    if token and command('GET',key('worker:lease'))!=token: raise LeaseLost('Worker lease lost')
def activity_start(call,user,agent,task):
    return put('activity',call,{'call_id':call,'user_id':user,'agent_id':agent,'task':task,'status':'working','started_at':now(),'finished_at':None,'worker_token':fence.get()})
def activity_finish(call,state): return update('activity',call,{'status':state,'finished_at':now()},status='working')
def acquire(token, ttl=30000): return command('SET',key('worker:lease'),token,'NX','PX',ttl)=='OK'
def renew(token, ttl=30000):
    return bool(script("if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('PEXPIRE',KEYS[1],ARGV[2]) end return 0",[key('worker:lease')],[token,ttl]))
def release(token):
    return script("if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) end return 0",[key('worker:lease')],[token])
EVENT="""
if ARGV[2]~='' and redis.call('GET',KEYS[4])~=ARGV[2] then return -1 end
local id=redis.call('INCR',KEYS[1]);local row=cjson.decode(ARGV[1]);row.id=id
redis.call('HSET',KEYS[2],tostring(id),cjson.encode(row));redis.call('ZADD',KEYS[3],id,tostring(id));return id
"""
def event(user_id,kind,workflow_id=None,step_id=None,agent_id=None,**payload):
    row={'user_id':user_id,'kind':kind,'workflow_id':workflow_id,'step_id':step_id,'agent_id':agent_id,'payload':payload,'created_at':now()}; owner=user_key(user_id)
    ident=script(EVENT,[key('events:sequence'),key('events:'+owner),key('events:'+owner+':order'),key('worker:lease')],[json.dumps(row,default=str),fence.get() or ''])
    if ident==-1: raise LeaseLost('Worker lease lost')
    return int(ident)
def events(user_id,workflow_id=None,after=0,limit=500):
    owner=user_key(user_id); ids=command('ZRANGEBYSCORE',key('events:'+owner+':order'),'('+str(after),'+inf') or []; out=[]
    for start in range(0,len(ids),200):
        for raw in command('HMGET',key('events:'+owner),*ids[start:start+200]):
            if raw:
                row=json.loads(raw)
                if workflow_id is None or row['workflow_id']==workflow_id:
                    out.append(row)
                    if len(out)>=limit: return out
    return out
def recent_events(user_id,limit=40):
    owner=user_key(user_id); ids=command('ZREVRANGE',key('events:'+owner+':order'),0,limit-1) or []
    return [json.loads(r) for r in command('HMGET',key('events:'+owner),*ids) if r] if ids else []
def get(run_id,user_id=None):
    def read(tx):
        row=tx.get('workflows',run_id)
        if not row or (user_id is not None and row['user_id']!=user_id): return None
        run=dict(row);run.pop('user_id',None)
        run['steps']=sorted(tx.rows('steps',workflow_id=run_id),key=lambda s:s['position'])
        run['completed']=sum(s['status']=='completed' for s in run['steps']);run['total']=len(run['steps']);return run
    return atomic(['workflows','steps'],read)
def listing(user_id):
    rows=sorted(records('workflows',user_id=user_id),key=lambda r:r['created_at'],reverse=True)[:100]
    return [run for row in rows if (run:=get(row['id'],user_id))]
