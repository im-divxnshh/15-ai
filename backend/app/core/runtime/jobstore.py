"""One durable, user-scoped local state store. Single machine, persistent volume."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from dotenv import load_dotenv

BACKEND=Path(__file__).resolve().parents[3]
load_dotenv(BACKEND/'.env')
_raw=Path(os.getenv('WORKFLOW_DB_PATH','data/office.sqlite3'))
PATH=_raw if _raw.is_absolute() else BACKEND/_raw
IMPLEMENTED_BACKEND='sqlite'

class StorageUnavailable(RuntimeError):pass

def storage_ready():
    # The requested Redis migration has not been implemented. Do not fall back
    # to the legacy SQLite store merely because service env fields are filled.
    return IMPLEMENTED_BACKEND=='upstash' and os.getenv('STORAGE_BACKEND','upstash')=='upstash'

def storage_info():
    return {'backend':'upstash','implemented':storage_ready(),'reason':None if storage_ready() else 'Upstash persistence migration is pending. Task execution is disabled; SQLite fallback is disabled.'}


def now(): return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect():
    if not storage_ready():raise StorageUnavailable(storage_info()['reason'])
    PATH.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(PATH,timeout=10)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        with c: yield c
    finally: c.close()


def init():
    with connect() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY,user_id TEXT,title TEXT,instruction TEXT,mode TEXT,concurrency INTEGER,status TEXT,client_key TEXT,created_at TEXT,updated_at TEXT,UNIQUE(user_id,client_key));
        CREATE TABLE IF NOT EXISTS steps(id TEXT PRIMARY KEY,workflow_id TEXT REFERENCES workflows(id),position INTEGER,title TEXT,instruction TEXT,agent_id TEXT,dependencies TEXT,status TEXT,result TEXT,error TEXT,agents TEXT DEFAULT '[]',attempts INTEGER DEFAULT 0,started_at TEXT,finished_at TEXT,UNIQUE(workflow_id,position));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,workflow_id TEXT,step_id TEXT,agent_id TEXT,kind TEXT,payload TEXT,created_at TEXT);
        CREATE INDEX IF NOT EXISTS events_run ON events(workflow_id,id);
        CREATE TABLE IF NOT EXISTS activity(call_id TEXT PRIMARY KEY,user_id TEXT,agent_id TEXT,task TEXT,status TEXT,started_at TEXT,finished_at TEXT);
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,user_id TEXT,kind TEXT,payload TEXT,created_at TEXT,updated_at TEXT);
        CREATE INDEX IF NOT EXISTS docs_owner ON documents(user_id,kind);
        CREATE TABLE IF NOT EXISTS delivery_settings(user_id TEXT PRIMARY KEY,email TEXT,telegram_chat_id TEXT,email_enabled INTEGER,telegram_enabled INTEGER,categories TEXT);
        CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,channel TEXT,title TEXT,body TEXT,status TEXT,attempts INTEGER DEFAULT 0,error TEXT,next_attempt REAL DEFAULT 0,created_at TEXT,sent_at TEXT,is_test INTEGER DEFAULT 0,destination TEXT);
        CREATE TABLE IF NOT EXISTS connection_tests(user_id TEXT,channel TEXT,destination TEXT,fingerprint TEXT,tested_at TEXT,PRIMARY KEY(user_id,channel));
        CREATE TABLE IF NOT EXISTS actions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,agent_id TEXT,workflow_id TEXT,step_id TEXT,kind TEXT,summary TEXT,payload TEXT,status TEXT DEFAULT 'pending',result TEXT,created_at TEXT,resolved_at TEXT);
        CREATE TABLE IF NOT EXISTS migrations(source TEXT PRIMARY KEY,imported_at TEXT);
        ''')


def event(user_id,kind,workflow_id=None,step_id=None,agent_id=None,**payload):
    with connect() as c:
        cur=c.execute('INSERT INTO events(user_id,workflow_id,step_id,agent_id,kind,payload,created_at) VALUES(?,?,?,?,?,?,?)',(user_id,workflow_id,step_id,agent_id,kind,json.dumps(payload,default=str),now()))
        return cur.lastrowid


def events(user_id,workflow_id=None,after=0,limit=500):
    with connect() as c:
        rows=c.execute('SELECT * FROM events WHERE user_id=? AND id>?'+(' AND workflow_id=?' if workflow_id else '')+' ORDER BY id LIMIT ?',(user_id,after,workflow_id,limit) if workflow_id else (user_id,after,limit)).fetchall()
    return [{**dict(r),'payload':json.loads(r['payload'])} for r in rows]


def get(run_id,user_id=None):
    with connect() as c:
        row=c.execute('SELECT * FROM workflows WHERE id=?'+(' AND user_id=?' if user_id else ''),(run_id,user_id) if user_id else (run_id,)).fetchone()
        if not row:return None
        steps=c.execute('SELECT * FROM steps WHERE workflow_id=? ORDER BY position',(run_id,)).fetchall()
    run=dict(row);run.pop('user_id',None)
    run['steps']=[{**dict(s),'dependencies':json.loads(s['dependencies']),'agents':json.loads(s['agents'])} for s in steps]
    run['completed']=sum(s['status']=='completed' for s in steps)
    run['total']=len(steps)
    return run


def listing(user_id):
    with connect() as c: ids=c.execute('SELECT id FROM workflows WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(user_id,)).fetchall()
    return [get(r['id'],user_id) for r in ids]
