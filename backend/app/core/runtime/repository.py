"""User-scoped history, memory, files, tasks and routine documents."""
import json
import uuid
from . import jobstore as db


def put(user,kind,payload,ident=None):
    ident=ident or str(uuid.uuid4());stamp=db.now()
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        existing=c.execute('SELECT user_id,kind,created_at FROM documents WHERE id=?',(ident,)).fetchone()
        if existing and existing['user_id']!=user:raise PermissionError('Document belongs to another user')
        if existing and existing['kind']!=kind:raise ValueError('Document kind cannot be changed')
        c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',(ident,user,kind,json.dumps(payload,default=str),stamp,stamp))
    return {**payload,'id':ident,'created_at':existing['created_at'] if existing else stamp}


def list_for(user,kind,limit=200):
    with db.connect() as c: rows=c.execute('SELECT * FROM documents WHERE user_id=? AND kind=? ORDER BY created_at DESC LIMIT ?',(user,kind,limit)).fetchall()
    return [{**json.loads(r['payload']),'id':r['id'],'created_at':r['created_at']} for r in rows]


def get(user,ident,kind=None):
    with db.connect() as c: row=c.execute('SELECT * FROM documents WHERE id=? AND user_id=?'+(' AND kind=?' if kind else ''),(ident,user,kind) if kind else (ident,user)).fetchone()
    return {**json.loads(row['payload']),'id':row['id'],'created_at':row['created_at']} if row else None


def delete(user,ident,kind=None):
    with db.connect() as c:return bool(c.execute('DELETE FROM documents WHERE user_id=? AND id=?'+(' AND kind=?' if kind else ''),(user,ident,kind) if kind else (user,ident)).rowcount)


def history(user,agent,limit=40):
    with db.connect() as c:
        rows=c.execute("SELECT * FROM documents WHERE user_id=? AND kind='message' AND json_extract(payload,'$.agent_id')=? ORDER BY created_at DESC LIMIT ?",(user,agent,limit)).fetchall()
    return [{**json.loads(r['payload']),'id':r['id'],'created_at':r['created_at']} for r in reversed(rows)]


def add_message(user,agent,role,content):return put(user,'message',{'agent_id':agent,'role':role,'content':content})


def recall(user,query,k=6):
    import re
    words=set(re.findall(r'\w+',query.lower()))
    if not words:return []
    # Filter all persisted memory first so busy files/threads do not hide older facts.
    terms=sorted(words,key=len,reverse=True)[:12]
    predicates=' OR '.join("lower(json_extract(payload,'$.content')) LIKE ?" for _ in terms)
    with db.connect() as c:
        found=c.execute("SELECT * FROM documents WHERE user_id=? AND kind='memory' AND ("+predicates+") ORDER BY created_at DESC LIMIT 1000",(user,*('%'+term+'%' for term in terms))).fetchall()
    rows=[{**json.loads(r['payload']),'id':r['id'],'created_at':r['created_at']} for r in found]
    ranked=[{**r,'score':len(words & set(re.findall(r'\w+',r['content'].lower())))/max(1,len(words))} for r in rows]
    return sorted((r for r in ranked if r['score']>0),key=lambda r:r['score'],reverse=True)[:k]
