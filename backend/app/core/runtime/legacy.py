"""Import scoped legacy local records once; never execute old jobs or approvals."""
import json
import uuid
from . import jobstore as db

def migrate(path=None):
    path=path or db.PATH.parent/'local_store.json'
    if not path.is_file():return 0
    try:data=json.loads(path.read_text())
    except (ValueError,OSError):return 0
    count=0
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        for collection,kind in [('messages','message'),('memories','memory'),('tasks','task')]:
            records=data.get(collection,[])
            if not isinstance(records,list):continue
            for record in records:
                if not isinstance(record,dict) or not record.get('user_id') or not record.get('id'):continue
                user=str(record['user_id']);source=f"legacy:{collection}:{user}:{record['id']}"
                if c.execute('SELECT 1 FROM migrations WHERE source=?',(source,)).fetchone():continue
                payload={k:v for k,v in record.items() if k not in ('user_id','id','created_at')}
                if kind=='message':
                    if record.get('role') not in ('user','assistant') or not isinstance(record.get('content'),str):continue
                    payload['agent_id']='nova' if record.get('agent_id')=='jarvis' else record.get('agent_id','__auto__')
                if kind=='memory' and not isinstance(record.get('content'),str):continue
                if kind=='task':
                    if not record.get('title'):continue
                    payload['notified']=True  # Historical reminders must not suddenly send.
                    payload['status']='done' if record.get('status') in ('done','completed') else 'open'
                ident=str(uuid.uuid5(uuid.NAMESPACE_URL,source));stamp=record.get('created_at') or db.now()
                c.execute('INSERT OR IGNORE INTO documents VALUES(?,?,?,?,?,?)',(ident,user,kind,json.dumps(payload),stamp,db.now()))
                c.execute('INSERT INTO migrations VALUES(?,?)',(source,db.now()));count+=1
    return count
