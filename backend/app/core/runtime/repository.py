"""Firestore user documents: every path is scoped to authenticated identity."""
import re
import uuid
from . import jobstore as db
from .firebase_store import client

def collection(user): return client().collection('nova_users').document(db.user_key(user)).collection('documents')
def put(user,kind,payload,ident=None,with_previous=False):
    from google.cloud import firestore
    ident=ident or str(uuid.uuid4())
    if '/' in ident or not ident: raise ValueError('Invalid document ID')
    db.assert_lease()
    if kind in ('task','routine'):register_schedule_user(user)
    ref=collection(user).document(ident); stamp=db.now()
    @firestore.transactional
    def write(transaction):
        prior=ref.get(transaction=transaction);existing=prior.to_dict() if prior.exists else None
        if existing and existing['kind']!=kind: raise ValueError('Document kind cannot be changed')
        created=existing['created_at'] if existing else stamp
        clean={k:v for k,v in payload.items() if k not in ('id','created_at','updated_at','user_id')}
        transaction.set(ref,{'kind':kind,'payload':clean,'created_at':created,'updated_at':stamp})
        current={**clean,'id':ident,'created_at':created}
        return (current,decode(prior) if prior.exists else None) if with_previous else current
    try: return write(client().transaction())
    except ValueError: raise
    except Exception as error: raise db.StorageUnavailable(f'Firestore write unavailable ({type(error).__name__})') from None

def decode(snapshot):
    row=snapshot.to_dict();return {**row['payload'],'id':snapshot.id,'created_at':row['created_at']}
def list_for(user,kind,limit=200):
    from google.cloud.firestore_v1.base_query import FieldFilter
    try:
        rows=[decode(s) for s in collection(user).where(filter=FieldFilter('kind','==',kind)).stream(timeout=10)]
        return sorted(rows,key=lambda r:(r['created_at'],r['id']),reverse=True)[:limit]
    except db.StorageUnavailable:raise
    except Exception as error: raise db.StorageUnavailable(f'Firestore query unavailable ({type(error).__name__})') from None

def get(user,ident,kind=None):
    if '/' in ident or not ident: return None
    try:
        row=collection(user).document(ident).get(timeout=10)
        return decode(row) if row.exists and (kind is None or row.to_dict()['kind']==kind) else None
    except db.StorageUnavailable:raise
    except Exception as error: raise db.StorageUnavailable(f'Firestore read unavailable ({type(error).__name__})') from None

def delete(user,ident,kind=None):
    return take(user,ident,kind) is not None

def take(user,ident,kind=None):
    from google.cloud import firestore
    if '/' in ident or not ident: return None
    ref=collection(user).document(ident)
    @firestore.transactional
    def remove(transaction):
        snapshot=ref.get(transaction=transaction)
        if not snapshot.exists or (kind and snapshot.to_dict()['kind']!=kind): return None
        transaction.delete(ref);return decode(snapshot)
    try: return remove(client().transaction())
    except Exception as error: raise db.StorageUnavailable(f'Firestore delete unavailable ({type(error).__name__})') from None

def register_schedule_user(user):
    try:client().collection('nova_schedule_users').document(db.user_key(user)).set({'user_id':user},timeout=10)
    except Exception as error:raise db.StorageUnavailable(f'Firestore scheduler unavailable ({type(error).__name__})') from None
def schedule_users():
    try:return [s.to_dict()['user_id'] for s in client().collection('nova_schedule_users').stream(timeout=10)]
    except db.StorageUnavailable:raise
    except Exception as error:raise db.StorageUnavailable(f'Firestore scheduler unavailable ({type(error).__name__})') from None
def history(user,agent,limit=40):
    rows=[r for r in list_for(user,'message',100000) if r['agent_id']==agent];return list(reversed(rows[:limit]))
def add_message(user,agent,role,content): return put(user,'message',{'agent_id':agent,'role':role,'content':content})
def recall(user,query,k=6):
    from . import rag
    words=set(re.findall(r'\w+',query.lower()))
    if not words: return []
    ranked=[{**r,'score':len(words & set(re.findall(r'\w+',r.get('content','').lower())))/len(words)} for r in list_for(user,'memory',100000)]
    return sorted([r for r in ranked if r['score']>0]+rag.search(user,query,k),key=lambda r:r['score'],reverse=True)[:k]

def import_once(user,source,kind,payload):
    """Import and tombstone marker share a Firestore transaction."""
    from google.cloud import firestore
    root=client().collection('nova_users').document(db.user_key(user))
    marker=root.collection('imports').document(source)
    target=collection(user).document('legacy-'+source)
    @firestore.transactional
    def import_record(tx):
        if marker.get(transaction=tx).exists:return False
        tx.set(target,{'kind':kind,'payload':payload,'created_at':db.now(),'updated_at':db.now()})
        tx.set(marker,{'imported_at':db.now()});return True
    if kind in ('task','routine'):register_schedule_user(user)
    try:return import_record(client().transaction())
    except Exception as error:raise db.StorageUnavailable(f'Firestore import unavailable ({type(error).__name__})') from None
