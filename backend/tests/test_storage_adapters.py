"""Transport and indexing failure boundaries without live service calls."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.runtime import jobstore as db,object_store,rag,repository as repo,tools
from storage_fixtures import Firestore,Neon

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'STORAGE_BACKEND':'upstash','UPSTASH_REDIS_REST_URL':'https://redis.invalid','UPSTASH_REDIS_REST_TOKEN':'private-test-token','FILE_STORAGE_BACKEND':'r2','R2_ACCOUNT_ID':'test-account','R2_BUCKET':'test-bucket','R2_ACCESS_KEY_ID':'test-key','R2_SECRET_ACCESS_KEY':'private-test-secret'})
        self.env.start();self.addCleanup(self.env.stop);rag.init.cache_clear()
    def test_upstash_serializes_commands_and_never_retries_uncertain_writes(self):
        actual=httpx.Client;calls=[]
        def response(request):
            calls.append(request);return httpx.Response(200,json={'result':'PONG'})
        with patch.object(httpx,'Client',lambda **kw:actual(**kw,transport=httpx.MockTransport(response))):
            self.assertEqual(db.command('PING'),'PONG')
        self.assertEqual(json.loads(calls[0].content),['PING'])
        self.assertEqual(calls[0].headers['Authorization'],'Bearer private-test-token')
        calls.clear()
        def lost(request):calls.append(request);raise httpx.ReadTimeout('secret URL must not escape')
        with patch.object(httpx,'Client',lambda **kw:actual(**kw,transport=httpx.MockTransport(lost))):
            with self.assertRaises(db.StorageUnavailable) as error:db.command('INCR','job:sequence')
        self.assertEqual(len(calls),1);self.assertNotIn('secret URL',str(error.exception))
    def test_r2_signs_private_binary_objects_and_does_not_leak_credentials(self):
        actual=httpx.Client;calls=[];data=b'\x00\xff private bytes'
        def response(request):calls.append(request);return httpx.Response(200,content=data)
        with patch.object(httpx,'Client',lambda **kw:actual(**kw,transport=httpx.MockTransport(response))):
            object_store.put('users/hash/a b+é.txt',data)
            self.assertEqual(object_store.get('users/hash/a b+é.txt'),data)
        self.assertEqual(calls[0].content,data)
        self.assertIn('/test-bucket/users/hash/a%20b%2B%C3%A9.txt',str(calls[0].url))
        self.assertEqual(calls[0].headers['x-amz-content-sha256'],hashlib.sha256(data).hexdigest())
        self.assertIn('SignedHeaders=host;x-amz-content-sha256;x-amz-date',calls[0].headers['Authorization'])
        self.assertNotIn('private-test-secret',calls[0].headers['Authorization'])
        with patch.object(httpx,'Client',lambda **kw:actual(**kw,transport=httpx.MockTransport(lambda request:httpx.Response(403,text='private-test-secret')))):
            with self.assertRaises(db.StorageUnavailable) as error:object_store.put('a',data)
        self.assertNotIn('private-test-secret',str(error.exception))
    def test_failed_r2_write_never_publishes_a_file(self):
        with patch.object(object_store,'put',side_effect=db.StorageUnavailable('R2 down')),patch.object(repo,'put') as publish:
            with self.assertRaises(db.StorageUnavailable):tools.save_file('one','private.txt',b'text')
        publish.assert_not_called()
    def test_neon_failure_publishes_a_downloadable_unindexed_file(self):
        store=Firestore();objects={}
        with patch.object(repo,'client',lambda:store),patch('google.cloud.firestore.transactional',Firestore.transactional),patch.object(object_store,'put',lambda key,data:objects.__setitem__(key,data)),patch.object(rag,'replace',side_effect=db.StorageUnavailable('private connection URL')):
            row=tools.save_file('one','notes.txt',b'copper reference')
        self.assertFalse(row['indexed']);self.assertEqual(row['chunks_indexed'],0)
        self.assertTrue(row['readable']);self.assertNotIn('private connection URL',row['warning'])
        self.assertEqual(objects[row['object_key']],b'copper reference')
    def test_neon_retrieval_scopes_owner_and_current_generation(self):
        neon=Neon();store=Firestore()
        with patch.object(rag,'connect',neon.connect),patch.object(repo,'client',lambda:store),patch('google.cloud.firestore.transactional',Firestore.transactional):
            rag.replace('one','file-a','old','a.txt','copper old')
            rag.replace('one','file-a','current','a.txt','copper current')
            rag.replace('two','file-a','current','a.txt','copper private')
            repo.put('one','file',{'filename':'a.txt','generation':'current','indexed':True},'file-a')
            results=rag.search('one','copper')
        self.assertEqual(len(results),1);self.assertEqual(results[0]['content'],'copper current')
        sql,args=next((sql,args) for sql,args in neon.calls if 'SELECT source_id' in sql)
        self.assertIn('user_id=%s',sql);self.assertEqual(args[1],'one');self.assertEqual(args[3],['current'])
    def test_chunk_overlap_and_empty_text_do_not_fabricate_indexing(self):
        neon=Neon()
        with patch.object(rag,'connect',neon.connect):
            self.assertEqual(rag.replace('one','f','g','f.txt',''),0)
            self.assertEqual(rag.replace('one','f','g','f.txt','a'*7000),3)
        chunks=[row[1] for row in neon.rows.values()]
        self.assertEqual([len(c) for c in chunks],[3200,3200,1400])
        self.assertAlmostEqual(sum(v*v for v in rag.embedding('copper reference')),1)

if __name__=='__main__':unittest.main()
