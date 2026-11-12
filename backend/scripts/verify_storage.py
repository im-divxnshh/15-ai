"""Write/read/delete an isolated managed-storage fixture, without AI or messages.

Run only after scripts/check_connections.py succeeds. Uses an ephemeral user,
Redis namespace and private R2 objects; never touches real user documents.
"""
import json
import os
from pathlib import Path
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.runtime import jobstore as db,repository as repo,rag,tools,object_store


def main():
    ident=str(uuid.uuid4());user='nova-verification-'+ident
    original_prefix=os.environ.get('REDIS_KEY_PREFIX')
    os.environ['REDIS_KEY_PREFIX']='nova:verification:'+ident
    file=None;message=None;success=False
    try:
        db.init();db.put('actions',1,{'id':1,'user_id':user,'status':'pending'})
        assert db.records('actions',user_id=user)[0]['id']==1
        assert db.acquire(ident);assert not db.acquire('other');assert db.renew(ident)
        db.release(ident)
        event=db.event(user,'verification');assert db.events(user)[0]['id']==event
        assert not db.events('other-user')
        message=repo.add_message(user,'nova','user','Isolated storage verification')
        assert repo.history(user,'nova')[0]['content']=='Isolated storage verification'
        assert not repo.history('other-'+user,'nova')
        file=tools.save_file(user,'verification.txt',b'Copper verification reference')
        assert file['indexed'],file.get('warning')
        assert tools.file_bytes(user,'verification.txt')==b'Copper verification reference'
        assert repo.recall(user,'copper')[0]['source_id']==file['id']
        assert not repo.recall('other-'+user,'copper')
        success=True
        print(json.dumps({'passed':True,'scope':'Isolated live Redis transactions/lease/events, Firestore history, R2 put/get and Neon generation-scoped chunk retrieval. No AI completion or notifications.'}))
    except Exception as error:
        print(json.dumps({'passed':False,'error':type(error).__name__,'scope':'Managed storage integration fixture'}))
    finally:
        # Each cleanup is attempted independently. No real account data is used.
        cleanup=[]
        if file:
            try:
                result=tools.delete_file(user,'verification.txt')
                if result.get('warning'):cleanup.append('file storage cleanup pending')
            except Exception:cleanup.append('file cleanup unavailable')
        if message:
            try:repo.delete(user,message['id'],'message')
            except Exception:cleanup.append('history cleanup unavailable')
        try:
            keys=[];cursor='0'
            while True:
                cursor,found=db.command('SCAN',cursor,'MATCH',db.key('*'),'COUNT',100);keys.extend(found)
                if str(cursor)=='0':break
            if keys:db.command('DEL',*keys)
        except Exception:cleanup.append('isolated Redis cleanup unavailable')
        if original_prefix is None:os.environ.pop('REDIS_KEY_PREFIX',None)
        else:os.environ['REDIS_KEY_PREFIX']=original_prefix
        if cleanup:print(json.dumps({'cleanup':cleanup}));success=False
    return 0 if success else 1

if __name__=='__main__':sys.exit(main())
