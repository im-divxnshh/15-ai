"""Disposable SDK stand-ins; Redis runs production Lua via fakeredis/lupa.

Firestore and Neon fixtures establish caller logic and SQL scoping, not live
provider behavior. No credentials or persistent user data are used.
"""
import copy
import json
import os
import threading
from contextlib import contextmanager
from unittest.mock import patch
from app.core.runtime import jobstore as db,repository as repo,rag,object_store

class Snapshot:
    def __init__(self,ref,data):self.id=ref.id;self.data=copy.deepcopy(data);self.exists=data is not None
    def to_dict(self):return copy.deepcopy(self.data)

class Document:
    def __init__(self,store,path):self.store=store;self.path=path;self.id=path[-1]
    def collection(self,name):return Collection(self.store,(*self.path,name))
    def get(self,**kwargs):return Snapshot(self,self.store.rows.get(self.path))
    def set(self,data,**kwargs):self.store.rows[self.path]=copy.deepcopy(data)

class Collection:
    def __init__(self,store,path,filters=()):self.store=store;self.path=path;self.filters=filters
    def document(self,ident):return Document(self.store,(*self.path,ident))
    def where(self,filter):return Collection(self.store,self.path,(*self.filters,filter))
    def stream(self,**kwargs):
        with self.store.lock:
            return [Snapshot(Document(self.store,path),data) for path,data in self.store.rows.items() if path[:-1]==self.path and all(data.get(f.field_path)==f.value for f in self.filters)]

class Transaction:
    def __init__(self,store):self.store=store
    def set(self,ref,data):ref.set(data)
    def delete(self,ref):self.store.rows.pop(ref.path,None)

class Firestore:
    def __init__(self):self.rows={};self.lock=threading.RLock()
    def collection(self,name):return Collection(self,(name,))
    def transaction(self):return Transaction(self)
    @staticmethod
    def transactional(fn):
        def wrapped(tx,*args,**kwargs):
            with tx.store.lock:return fn(tx,*args,**kwargs)
        return wrapped

class Result:
    def __init__(self,rows=()):self.data=rows
    def fetchall(self):return self.data

class Neon:
    def __init__(self):self.rows={};self.calls=[];self.lock=threading.RLock()
    def execute(self,sql,args=()):
        self.calls.append((sql,args))
        if sql.startswith('DELETE'):
            for key in list(self.rows):
                if key[:2]==tuple(args[:2]) and (len(args)==2 or key[2]==args[2]):self.rows.pop(key)
        elif sql.startswith('INSERT'):
            user,source,generation,position,filename,content,vector,model=args
            self.rows[(user,source,generation,position)]=(filename,content,json.loads(vector),model)
        elif 'SELECT source_id' in sql:
            vector,user,sources,generations,model,_,limit=args;q=json.loads(vector);active=set(zip(sources,generations));found=[]
            for (owner,source,generation,position),(filename,content,v,m) in self.rows.items():
                if owner==user and (source,generation) in active and m==model:
                    score=sum(a*b for a,b in zip(q,v));found.append((source,generation,position,filename,content,score))
            return Result(sorted(found,key=lambda r:r[-1],reverse=True)[:limit])
        return Result()
    def executemany(self,sql,rows):
        for row in rows:self.execute(sql,row)
    @contextmanager
    def cursor(self):yield self
    @contextmanager
    def connect(self):
        with self.lock:yield self

class StorageFixtures:
    def __init__(self):
        self.redis=None
        if os.getenv('NOVA_STATE_TESTS')!='1':
            import fakeredis
            self.redis=fakeredis.FakeRedis(decode_responses=True)
        self.firestore=Firestore();self.neon=Neon();self.objects={};self.patches=[]
    def start(self):
        def get(key):
            if key not in self.objects:raise FileNotFoundError('Missing test object')
            return self.objects[key]
        def command(*args):
            result=self.redis.execute_command(*args)
            if args[0]=='PING' and result is True:return 'PONG'
            if args[0]=='SET' and result is True:return 'OK'
            return result
        redis_patches=self.state_patches() if self.redis is None else [patch.object(db,'command',command)]
        self.patches=[*redis_patches,patch.object(repo,'client',lambda:self.firestore),patch('google.cloud.firestore.transactional',Firestore.transactional),patch.object(rag,'connect',self.neon.connect),patch.object(object_store,'put',lambda key,data:self.objects.__setitem__(key,data)),patch.object(object_store,'get',get),patch.object(object_store,'delete',lambda key:self.objects.pop(key,None))]
        rag.init.cache_clear()
        for p in self.patches:p.start()
        return self
    def stop(self):
        for p in reversed(self.patches):p.stop()
        if self.redis:self.redis.close()

    def state_patches(self):
        # Explicit local logic mode. This never claims Redis/Lua verification.
        self.tables={t:{} for t in db.TABLES};self.sequences={};self.events=[];self.lock=threading.RLock();self.lease=None
        def atomic(tables,operation):
            with self.lock:
                if db.fence.get() and self.lease!=db.fence.get():raise db.LeaseLost('Lease lost')
                subset=copy.deepcopy({t:self.tables[t] for t in tables});result=operation(db.View(subset));self.tables.update(subset);return result
        def records(table,**filters):return [copy.deepcopy(r) for r in self.tables[table].values() if all(r.get(k)==v for k,v in filters.items())]
        def next_id(kind):
            with self.lock:self.sequences[kind]=self.sequences.get(kind,0)+1;return self.sequences[kind]
        def event(user,kind,workflow_id=None,step_id=None,agent_id=None,**payload):
            with self.lock:
                ident=next_id('event');self.events.append({'id':ident,'user_id':user,'kind':kind,'workflow_id':workflow_id,'step_id':step_id,'agent_id':agent_id,'payload':payload,'created_at':db.now()});return ident
        def events(user,workflow_id=None,after=0,limit=500):return [copy.deepcopy(r) for r in self.events if r['user_id']==user and (workflow_id is None or r['workflow_id']==workflow_id) and r['id']>after][:limit]
        def acquire(token,*args):
            with self.lock:
                if self.lease:return False
                self.lease=token;return True
        def release(token):
            with self.lock:
                if self.lease==token:self.lease=None;return True
                return False
        return [patch.object(db,'atomic',atomic),patch.object(db,'records',records),patch.object(db,'next_id',next_id),patch.object(db,'event',event),patch.object(db,'events',events),patch.object(db,'recent_events',lambda user,limit=40:list(reversed(events(user)))[0:limit]),patch.object(db,'init',lambda:None),patch.object(db,'assert_lease',lambda:None),patch.object(db,'acquire',acquire),patch.object(db,'renew',lambda token,*args:self.lease==token),patch.object(db,'release',release)]
