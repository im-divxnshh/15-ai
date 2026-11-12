"""Explicit import of scoped legacy JSON into Firestore; never launches old work."""
import hashlib
import json
from pathlib import Path
from . import jobstore as db,repository as repo

def migrate(path):
    path=Path(path)
    if not path.is_file():return 0
    data=json.loads(path.read_text());count=0
    for collection,kind in [('messages','message'),('memories','memory'),('tasks','task')]:
        records=data.get(collection,[])
        if not isinstance(records,list):continue
        for record in records:
            if not isinstance(record,dict) or not record.get('user_id') or not record.get('id'):continue
            user=str(record['user_id']);source=f"legacy:{collection}:{user}:{record['id']}"
            payload={k:v for k,v in record.items() if k not in ('user_id','id','created_at')}
            if kind=='message':
                if record.get('role') not in ('user','assistant') or not isinstance(record.get('content'),str):continue
                payload['agent_id']='nova' if record.get('agent_id')=='jarvis' else record.get('agent_id','__auto__')
            if kind=='memory' and not isinstance(record.get('content'),str):continue
            if kind=='task':
                if not record.get('title'):continue
                payload['notified']=True
                payload['status']='done' if record.get('status') in ('done','completed') else 'open'
            count+=repo.import_once(user,hashlib.sha256(source.encode()).hexdigest(),kind,payload)
    return count
