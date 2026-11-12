"""Redis Lua concurrency and fencing checks; require requirements-dev.txt."""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.runtime import jobstore as db,workflows
from storage_fixtures import StorageFixtures

@unittest.skipIf(os.getenv('NOVA_STATE_TESTS')=='1','Local logic mode excludes Redis/Lua verification')
class RedisTransactions(unittest.TestCase):
    def setUp(self):
        self.fixture=StorageFixtures().start();self.addCleanup(self.fixture.stop)
    def test_stale_owner_cannot_commit_or_emit_events(self):
        self.assertTrue(db.acquire('old'));self.assertFalse(db.acquire('second'))
        self.assertFalse(db.renew('second'));self.assertFalse(db.release('second'))
        db.release('old');self.assertTrue(db.acquire('new'))
        token=db.fence.set('old')
        try:
            with self.assertRaises(db.LeaseLost):db.put('activity','stale',{'status':'working'})
            with self.assertRaises(db.LeaseLost):db.event('one','agent_started')
        finally:db.fence.reset(token)
        self.assertEqual(db.records('activity'),[]);self.assertEqual(db.events('one'),[])
    def test_concurrent_idempotency_and_claims_are_atomic(self):
        req=workflows.BatchInput(client_key='same-key',tasks=[workflows.StepInput(title='A',instruction='A',agent_id='friday')])
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids=list(pool.map(lambda _:workflows.create('one',req)['id'],range(4)))
        self.assertEqual(len(set(ids)),1)
        self.assertEqual(len(db.records('workflows')),1);self.assertEqual(len(db.records('steps')),1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            claimed=list(pool.map(lambda _:db.atomic(['workflows','steps','actions'],workflows.advance)[0],range(2)))
        self.assertEqual(sum(len(rows) for rows in claimed),1)
        self.assertEqual(db.get(ids[0])['steps'][0]['attempts'],1)
    def test_transaction_conflict_retries_without_duplicate_mutation(self):
        actual=db.script;attempts=[]
        def script(source,keys,args=()):
            if source==db.COMMIT:
                attempts.append(1)
                if len(attempts)==1:return 0
            return actual(source,keys,args)
        with patch.object(db,'script',script):db.put('actions',1,{'id':1,'status':'pending'})
        self.assertEqual(len(attempts),2);self.assertEqual(len(db.records('actions')),1)
    def test_event_cursor_is_scoped_and_replays_in_order(self):
        a=db.event('one','first');db.event('two','private');b=db.event('one','second')
        self.assertEqual([r['id'] for r in db.events('one',after=a)],[b])
        self.assertEqual([r['kind'] for r in db.recent_events('one')],['second','first'])

if __name__=='__main__':unittest.main()
