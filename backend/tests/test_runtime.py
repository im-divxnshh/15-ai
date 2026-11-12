"""Durable runtime tests. HTTP simulations are in-process by default.

Set NOVA_HTTP_TESTS=1 for actual loopback HTTP transport checks outside a
workspace that restricts socket listeners. Neither mode verifies live services.
"""
import asyncio
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import httpx
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.runtime import jobstore as db,workflows as work,execution,delivery,provider,repository as repo,tools
from app.api.nova import router,current_user
from fastapi import FastAPI
from fastapi.testclient import TestClient

class Base(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'GROQ_API_KEY':'test-key','APP_TOKEN':'test-access','FIREBASE_CREDENTIALS':'','ALLOW_LOCAL_NO_AUTH':'false','SYSTEM_ACCESS_USER_ID':'one','TELEGRAM_BOT_TOKEN':'','SMTP_HOST':'','SMTP_USER':'','SMTP_PASSWORD':''})
        self.env.start();self.paths=patch.multiple(db,PATH=self.root/'office.sqlite3');self.paths.start();self.toolpaths=patch.multiple(tools,FILES=self.root/'files',ROOT=self.root);self.toolpaths.start();db.init()
    async def asyncTearDown(self):
        await work.stop()
        for _,task in work._active.values():task.cancel()
        await asyncio.gather(*(t for _,t in work._active.values()),return_exceptions=True);work._active.clear()
        self.env.stop();self.paths.stop();self.toolpaths.stop();self.tmp.cleanup()
    def create(self,tasks,mode='sequential',user='one',key=None,concurrency=3):
        return work.create(user,work.BatchInput(title='Test mission',mode=mode,concurrency=concurrency,client_key=key,tasks=[work.StepInput(title=f'Task {i+1}',instruction=t if isinstance(t,str) else t[0],dependencies=[] if isinstance(t,str) else t[1],agent_id='friday') for i,t in enumerate(tasks)]))
    async def drain(self,ident,timeout=3):
        until=asyncio.get_running_loop().time()+timeout
        while asyncio.get_running_loop().time()<until:
            await work.tick();await asyncio.sleep(.01)
            run=db.get(ident)
            if run['status'] in ('completed','failed','cancelled'):return run
        self.fail('Queue did not settle: '+str(db.get(ident)))

class QueueTests(Base):
    async def test_background_worker_and_implicit_sequential_chain(self):
        messages=[]
        async def respond(user,msg,agent_id=None):messages.append(msg);return execution.Turn('persisted result',agent_id,[agent_id])
        with patch.object(execution,'respond',respond):
            run=self.create(['first','second']);self.assertEqual(run['steps'][1]['dependencies'],[0]);work.start()
            # No browser requests or manual ticks drive this worker.
            deadline=asyncio.get_running_loop().time()+3
            while db.get(run['id'])['status']!='completed' and asyncio.get_running_loop().time()<deadline:await asyncio.sleep(.05)
            await work.stop()
        self.assertEqual(db.get(run['id'])['status'],'completed');self.assertIn('persisted result',messages[1]);self.assertEqual(db.get(run['id'])['steps'][1]['attempts'],1)

    async def test_legacy_import_preserves_owner_and_does_not_restore_deleted_history(self):
        from app.core.runtime.legacy import migrate
        path=self.root/'local_store.json';path.write_text(json.dumps({'messages':[{'id':'old','user_id':'one','agent_id':'jarvis','role':'user','content':'Old private conversation'}],'tasks':[{'id':'old-task','user_id':'one','title':'Historical reminder','due_at':'2020'}]}))
        self.assertEqual(migrate(path),2);self.assertEqual(len(repo.history('one','nova')),1);self.assertEqual(repo.history('two','nova'),[])
        ident=repo.history('one','nova')[0]['id'];repo.delete('one',ident);self.assertEqual(migrate(path),0);self.assertEqual(repo.history('one','nova'),[])
        await work.scheduled();self.assertEqual(repo.list_for('one','notification'),[])
    async def test_sequential_dependencies_and_next_batch(self):
        calls=[]
        async def respond(user,msg,agent_id=None):
            calls.append(msg);await asyncio.sleep(.015);return execution.Turn('RESULT '+str(len(calls)),agent_id,[agent_id])
        with patch.object(execution,'respond',respond):
            a=self.create(['first',('second',[0]),('third',[1])]);b=self.create(['next batch'])
            out=await self.drain(a['id']);other=await self.drain(b['id'])
        self.assertEqual(out['completed'],3);self.assertEqual(other['completed'],1)
        self.assertIn('RESULT 1',calls[1]);self.assertIn('RESULT 2',calls[2]);self.assertEqual(calls[-1],'next batch')
    async def test_parallel_limits_and_join(self):
        active=0;maximum=0;messages=[]
        async def respond(user,msg,agent_id=None):
            nonlocal active,maximum
            active+=1;maximum=max(maximum,active);messages.append(msg);await asyncio.sleep(.035);active-=1
            return execution.Turn(msg,agent_id,[agent_id])
        with patch.object(execution,'respond',respond):
            run=self.create(['left','right',('join',[0,1]),'independent'],'parallel',concurrency=2)
            out=await self.drain(run['id'])
        self.assertEqual(maximum,2);self.assertEqual(out['completed'],4);joined=next(m for m in messages if m.startswith('join\n'));self.assertIn('left',joined);self.assertIn('right',joined)
    async def test_failure_skips_dependants_and_explicit_retry(self):
        count={}
        async def respond(user,msg,agent_id=None):
            count[msg]=count.get(msg,0)+1
            return execution.Turn('useful' if msg!='fail' else '',agent_id,[agent_id], 'provider failed' if msg=='fail' else None)
        with patch.object(execution,'respond',respond):
            run=self.create(['fail',('dependent',[0]),'independent'],'parallel');out=await self.drain(run['id'])
            self.assertEqual([s['status'] for s in out['steps']],['failed','skipped','completed']);self.assertEqual(count['fail'],1)
            work.control('one',run['id'],'retry');await self.drain(run['id'])
        self.assertEqual(count['independent'],1);self.assertEqual(count['fail'],2)
    async def test_pause_resume_and_cancellation(self):
        gate=asyncio.Event();calls=[]
        async def respond(user,msg,agent_id=None):calls.append(msg);await gate.wait();return execution.Turn('done',agent_id,[agent_id])
        with patch.object(execution,'respond',respond):
            run=self.create(['first','second']);await work.tick();await asyncio.sleep(.01)
            work.control('one',run['id'],'pause');gate.set();await asyncio.sleep(.015);await work.tick()
            self.assertEqual(calls,['first']);self.assertEqual(db.get(run['id'])['status'],'paused')
            work.control('one',run['id'],'resume');out=await self.drain(run['id']);self.assertEqual(out['completed'],2)
            gate.clear();cancel=self.create(['active','queued']);await work.tick();await asyncio.sleep(.01);work.control('one',cancel['id'],'cancel');await work.tick();await asyncio.sleep(.01);await work.tick()
            self.assertEqual([s['status'] for s in db.get(cancel['id'])['steps']],['cancelled','cancelled']);self.assertNotIn('queued',calls)
    async def test_idempotency_validation_and_ownership(self):
        a=self.create(['same'],key='same-key');b=self.create(['same'],key='same-key');other=self.create(['same'],user='two',key='same-key')
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['id'],other['id']);self.assertIsNone(db.get(a['id'],'two'))
        with self.assertRaises(KeyError):work.control('two',a['id'],'cancel')
        with self.assertRaises(ValueError):self.create([('bad',[0])])
    async def test_restart_marks_interrupted_without_replay(self):
        run=self.create(['was running','never started'])
        with db.connect() as c:c.execute("UPDATE steps SET status='running',attempts=1 WHERE id=?",(run['steps'][0]['id'],));c.execute("UPDATE workflows SET status='running' WHERE id=?",(run['id'],))
        calls=[]
        async def respond(*args,**kwargs):calls.append(args);return execution.Turn('done','friday',['friday'])
        with patch.object(execution,'respond',respond):
            work.start();await asyncio.sleep(.06);await work.stop();out=db.get(run['id']);self.assertEqual(out['status'],'interrupted');self.assertEqual(out['steps'][0]['status'],'interrupted');self.assertEqual(calls,[])
            with self.assertRaises(ValueError):work.control('one',run['id'],'resume')
            work.control('one',run['id'],'retry');await self.drain(run['id'])
        self.assertEqual(len(calls),2)
    async def test_waiting_approval_does_not_reexecute_task(self):
        async def respond(user,msg,agent_id=None):
            result=await tools.dispatch(user,'michel','request_command',{'command':'pwd'})
            self.assertEqual(result['status'],'awaiting approval');return execution.Turn('Awaiting command approval','michel',['michel'])
        with patch.object(execution,'respond',respond):
            run=self.create(['command']);await work.tick();await asyncio.sleep(.05);await work.tick()
            self.assertEqual(db.get(run['id'])['steps'][0]['status'],'waiting_approval')
            with db.connect() as c:ident=c.execute('SELECT id FROM actions').fetchone()[0]
            self.assertFalse((await tools.approve('two',ident))['ok']);self.assertTrue((await tools.approve('one',ident))['ok']);self.assertFalse((await tools.approve('one',ident))['ok'])
            result=await self.drain(run['id']);self.assertEqual(result['completed'],1);self.assertEqual(result['steps'][0]['attempts'],1)
    async def test_event_replay_and_file_memory_isolation(self):
        run=self.create(['event']);first=db.events('one',run['id']);db.event('one','tool_started',run['id'],tool='read_file')
        replay=db.events('one',run['id'],first[-1]['id']);self.assertEqual(replay[0]['kind'],'tool_started');self.assertEqual(db.events('two',run['id']),[])
        row=tools.save_file('one','notes.txt',b'Project preference: use copper.');self.assertTrue(row['indexed']);self.assertTrue(repo.recall('one','copper'));self.assertEqual(repo.recall('two','copper'),[])
        with self.assertRaises(ValueError):tools.file_path('one','../secret')
        with self.assertRaises(ValueError):tools.system_path('../outside')
        with self.assertRaises(ValueError):tools.system_path('.env')
        denied=await tools.dispatch('one','pepper','request_command',{'command':'pwd'});self.assertFalse(denied['ok'])
    async def test_reminders_routines_and_failure_review(self):
        task=repo.put('one','task',{'title':'Due task','status':'open','due_at':'2020-01-01T00:00:00+00:00','notified':False})
        routine=repo.put('one','routine',{'title':'Routine','instruction':'check','agent_id':'friday','interval_min':5,'enabled':True,'next_run_at':'2020','run_count':0})
        await work.scheduled();await work.scheduled();self.assertEqual(len([r for r in repo.list_for('one','notification') if r['category']=='reminders']),1);self.assertEqual(len(db.listing('one')),1)
        run=db.listing('one')[0]
        with db.connect() as c:c.execute("UPDATE workflows SET status='failed' WHERE id=?",(run['id'],))
        await work.scheduled();self.assertFalse(repo.get('one',routine['id'])['enabled'])

    async def test_user_batches_overlap_without_cross_user_results(self):
        active=set();overlap=False;messages=[]
        async def respond(user,msg,agent_id=None):
            nonlocal overlap
            active.add(user);overlap|=len(active)>1;messages.append((user,msg));await asyncio.sleep(.03);active.discard(user)
            return execution.Turn('private-'+user,agent_id,[agent_id])
        with patch.object(execution,'respond',respond):
            a=self.create(['A',('A join',[0])],user='one');b=self.create(['B',('B join',[0])],user='two')
            await self.drain(a['id']);await self.drain(b['id'])
        self.assertTrue(overlap)
        for user,msg in messages:self.assertNotIn('private-'+('two' if user=='one' else 'one'),msg)

    async def test_secret_and_system_permissions_and_cancelled_approval(self):
        tools.ROOT.joinpath('.env').write_text('secret')
        self.assertFalse((await tools.dispatch('two','michel','read_system_file',{'path':'anything.py'}))['ok'])
        self.assertNotIn('request_command',[s['function']['name'] for s in tools.schemas_for('michel','two')])
        for command in ('git diff','git log -p','git diff --output=leak','pwd; ls','npm run arbitrary'):
            with self.assertRaises(ValueError):tools.validate_command(command)
        with self.assertRaises(ValueError):tools.system_path('.env')
        a=self.create(['approve']);token=execution.context.set({'workflow_id':a['id'],'step_id':a['steps'][0]['id']})
        try:
            first=await tools.dispatch('one','michel','request_command',{'command':'pwd'})
            second=await tools.dispatch('one','michel','request_command',{'command':'pwd'})
            self.assertEqual(first['action_id'],second['action_id'])
            work.control('one',a['id'],'cancel');self.assertFalse((await tools.approve('one',first['action_id']))['ok'])
            self.assertFalse((await tools.dispatch('one','michel','request_command',{'command':'pwd'}))['ok'])
        finally:execution.context.reset(token)

    async def test_replace_delete_and_profile_recall_are_isolated(self):
        file=tools.save_file('one','notes.txt',b'copper preference')
        tools.save_file('one','notes.txt',b'titanium preference')
        self.assertEqual(repo.recall('one','copper'),[]);self.assertTrue(repo.recall('one','titanium'))
        fact=repo.put('one','profile',{'key':'name','value':'Private name'})
        with self.assertRaises(PermissionError):repo.put('two','profile',{'value':'changed'},fact['id'])
        self.assertEqual(repo.list_for('two','profile'),[])
        self.assertFalse(tools.save_file('one','unsupported.bin',b'\x00\xff')['indexed'])

    async def test_old_agent_history_and_memory_survive_a_busy_account(self):
        repo.add_message('one','nova','user','Old NOVA conversation');repo.put('one','memory',{'content':'Rare titanium preference'})
        with db.connect() as c:
            for i in range(2100):
                c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',(f'busy-{i}','one','message',json.dumps({'agent_id':'friday','role':'user','content':'Busy thread'}),db.now(),db.now()))
                c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',(f'memory-{i}','one','memory',json.dumps({'content':'Unrelated newer fact'}),db.now(),db.now()))
        self.assertEqual(repo.history('one','nova')[0]['content'],'Old NOVA conversation');self.assertTrue(repo.recall('one','titanium'));self.assertEqual(repo.recall('two','titanium'),[])

    async def test_symlink_directory_cannot_expose_another_users_files(self):
        private=tools.user_dir('one');other=tools.FILES/ __import__('hashlib').sha256(b'two').hexdigest();other.symlink_to(private,target_is_directory=True)
        with self.assertRaises(ValueError):tools.file_path('two','notes.txt')

    async def test_parallel_file_writes_leave_one_consistent_index(self):
        await asyncio.gather(asyncio.to_thread(tools.save_file,'one','shared.txt',b'copper'*1000),asyncio.to_thread(tools.save_file,'one','shared.txt',b'titanium'*1000))
        text=tools.file_path('one','shared.txt').read_text();rows=repo.list_for('one','file');memories=repo.list_for('one','memory')
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['size_bytes'],len(text.encode()));self.assertEqual(len(memories),rows[0]['chunks_indexed'])
        keyword='titanium' if 'titanium' in text else 'copper'
        self.assertTrue(all(keyword in row['content'] for row in memories));tools.delete_file('one','shared.txt');self.assertEqual(repo.list_for('one','memory'),[])

class HTTPHandler(BaseHTTPRequestHandler):
    requests=[]
    def log_message(self,*args):pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));self.requests.append((self.path,body))
        text=body.get('messages',[{}])[-1].get('content','')
        status=503 if 'FAIL_PROVIDER' in text else 401 if 'AUTH_FAILURE' in text else 200
        if self.path.endswith('sendMessage'):status=503 if 'fail-telegram' in self.path else 200;result={'ok':True,'result':{'message_id':1}}
        elif status!=200:result={'error':'Injected failure'}
        else:
            if 'TOOL_REQUEST' in text:
                msg={'role':'assistant','content':None,'tool_calls':[{'id':'tool-1','type':'function','function':{'name':'create_task','arguments':'{"title":"Created by actual tool"}'}}]}
            else:msg={'role':'assistant','content':'Useful local HTTP answer'}
            result={'choices':[{'message':msg}]}
        self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(result).encode())

class TransportTests(Base):
    async def asyncSetUp(self):
        await super().asyncSetUp();HTTPHandler.requests=[];self.server=None;self.clientpatch=None
        if os.getenv('NOVA_HTTP_TESTS')=='1':
            self.server=ThreadingHTTPServer(('127.0.0.1',0),HTTPHandler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base=f'http://127.0.0.1:{self.server.server_port}'
        else:
            self.base='http://simulation.invalid'
            def respond(request):
                body=json.loads(request.content);HTTPHandler.requests.append((request.url.path,body))
                text=body.get('messages',[{}])[-1].get('content','')
                status=503 if 'FAIL_PROVIDER' in text else 401 if 'AUTH_FAILURE' in text else 200
                if request.url.path.endswith('sendMessage'):
                    status=503 if 'fail-telegram' in request.url.path else 200;result={'ok':True,'result':{'message_id':1}}
                elif status!=200:result={'error':'Injected failure'}
                else:
                    msg={'role':'assistant','content':'Useful local HTTP answer'}
                    if 'TOOL_REQUEST' in text:msg={'role':'assistant','content':None,'tool_calls':[{'id':'tool-1','type':'function','function':{'name':'create_task','arguments':'{"title":"Created by actual tool"}'}}]}
                    result={'choices':[{'message':msg}]}
                return httpx.Response(status,json=result)
            self.mocktransport=httpx.MockTransport(respond);client=httpx.AsyncClient
            self.clientpatch=patch.object(httpx,'AsyncClient',lambda **kw:client(**kw,transport=self.mocktransport));self.clientpatch.start()
        self.transportenv=patch.dict(os.environ,{'GROQ_BASE_URL':self.base,'TELEGRAM_API_BASE_URL':self.base});self.transportenv.start();self.backoff=patch.object(provider,'BACKOFF',.001);self.backoff.start()
    async def asyncTearDown(self):
        if self.server:self.server.shutdown();self.server.server_close()
        if self.clientpatch:self.clientpatch.stop()
        self.transportenv.stop();self.backoff.stop();await super().asyncTearDown()
    async def test_http_provider_errors_do_not_become_success(self):
        failed=await execution.respond('one','FAIL_PROVIDER','friday');self.assertTrue(failed.error);self.assertEqual(failed.reply,'');self.assertEqual(len(HTTPHandler.requests),3)
        auth=await execution.respond('one','AUTH_FAILURE','friday');self.assertTrue(auth.error);self.assertEqual(len(HTTPHandler.requests),4)
        run=self.create(['FAIL_PROVIDER',('dependent',[0])]);out=await self.drain(run['id']);self.assertEqual(out['status'],'failed');self.assertEqual(out['steps'][1]['status'],'skipped')

    async def test_malformed_provider_message_is_a_configuration_error(self):
        if self.clientpatch:self.clientpatch.stop();self.clientpatch=None
        actual=httpx.AsyncClient
        for invalid in (None,'not an object',{'content':42},{'content':'answer','tool_calls':'invalid'}):
            with patch.object(httpx,'AsyncClient',lambda **kw:actual(**kw,transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'choices':[{'message':invalid}]})))):
                with self.assertRaises(provider.ProviderError):await provider.request([{'role':'user','content':'test'}])
    async def test_tool_round_and_activity(self):
        result=await execution.respond('one','TOOL_REQUEST','friday');self.assertFalse(result.error);self.assertEqual(result.reply,'Useful local HTTP answer');self.assertEqual(len(repo.list_for('one','task')),1)
        events=db.events('one');self.assertIn('tool_started',[e['kind'] for e in events]);self.assertIn('tool_completed',[e['kind'] for e in events])
        with db.connect() as c:row=c.execute('SELECT status FROM activity').fetchone();self.assertEqual(row[0],'idle')
    async def test_missing_credentials_and_bounded_delivery_failures(self):
        prefs={'email':'divyansh20060@gmail.com','telegram_chat_id':'123','email_enabled':True,'telegram_enabled':True,'categories':delivery.CATEGORIES}
        delivery.save_settings('one',prefs);delivery.queue('one','Test','Body',is_test=True);await delivery.tick();history=delivery.history('one');self.assertEqual({r['status'] for r in history},{'blocked'});self.assertFalse(delivery.settings('one')['connections']['telegram']['verified'])
        with patch.dict(os.environ,{'TELEGRAM_BOT_TOKEN':'fail-telegram'}):
            for i in range(3):
                with db.connect() as c:c.execute('UPDATE deliveries SET next_attempt=0')
                await delivery.tick()
            telegram=next(r for r in delivery.history('one') if r['channel']=='telegram');self.assertEqual(telegram['status'],'failed');self.assertEqual(telegram['attempts'],3);self.assertFalse(delivery.settings('one')['connections']['telegram']['verified'])
        self.assertEqual(delivery.history('two'),[])
    async def test_test_acknowledgement_and_fingerprint_invalidation(self):
        prefs={'email':'','telegram_chat_id':'123','email_enabled':False,'telegram_enabled':True,'categories':delivery.CATEGORIES}
        delivery.save_settings('one',prefs)
        with patch.dict(os.environ,{'TELEGRAM_BOT_TOKEN':'test-bot'}):
            delivery.queue('one','Connection test','actual local test',is_test=True);await delivery.tick();self.assertEqual(delivery.history('one')[0]['status'],'sent');self.assertTrue(delivery.settings('one')['connections']['telegram']['verified'])
        with patch.dict(os.environ,{'TELEGRAM_BOT_TOKEN':'changed-bot'}):self.assertFalse(delivery.settings('one')['connections']['telegram']['verified'])
    async def test_smtp_failure_is_recorded_and_never_marked_verified(self):
        prefs={'email':'divyansh20060@gmail.com','telegram_chat_id':'','email_enabled':True,'telegram_enabled':False,'categories':delivery.CATEGORIES};delivery.save_settings('one',prefs)
        import smtplib
        with patch.dict(os.environ,{'SMTP_HOST':'localhost','SMTP_USER':'test','SMTP_PASSWORD':'test'}),patch.object(delivery,'email',side_effect=smtplib.SMTPAuthenticationError(535,b'No')):
            delivery.queue('one','SMTP test','test',is_test=True);await delivery.tick();self.assertEqual(delivery.history('one')[0]['status'],'failed');self.assertFalse(delivery.settings('one')['connections']['email']['verified'])

    async def test_ambiguous_acknowledgement_is_not_auto_retried(self):
        delivery.save_settings('one',{'email':'divyansh20060@gmail.com','telegram_chat_id':'','email_enabled':True,'telegram_enabled':False,'categories':delivery.CATEGORIES})
        import smtplib
        with patch.dict(os.environ,{'SMTP_HOST':'smtp.test','SMTP_USER':'sender','SMTP_PASSWORD':'test'}),patch.object(delivery,'email',side_effect=smtplib.SMTPServerDisconnected('lost reply')) as sender:
            delivery.queue('one','Result','May already have arrived',is_test=True);await delivery.tick();await delivery.tick()
            self.assertEqual(sender.call_count,1);self.assertEqual(delivery.history('one')[0]['status'],'interrupted');self.assertFalse(delivery.settings('one')['connections']['email']['verified'])

    async def test_partial_telegram_delivery_is_not_replayed(self):
        delivery.save_settings('one',{'email':'','telegram_chat_id':'123','email_enabled':False,'telegram_enabled':True,'categories':delivery.CATEGORIES})
        calls=[]
        def response(request):
            calls.append(request);return httpx.Response(200,json={'ok':True}) if len(calls)==1 else httpx.Response(503,json={'ok':False})
        if self.clientpatch:self.clientpatch.stop();self.clientpatch=None
        actual=httpx.AsyncClient
        with patch.dict(os.environ,{'TELEGRAM_BOT_TOKEN':'test-bot'}),patch.object(httpx,'AsyncClient',lambda **kw:actual(**kw,transport=httpx.MockTransport(response))):
            delivery.queue('one','Large result','x'*8000,is_test=True);await delivery.tick();await delivery.tick()
        self.assertEqual(len(calls),2);self.assertEqual(delivery.history('one')[0]['status'],'interrupted');self.assertFalse(delivery.settings('one')['connections']['telegram']['verified'])

    async def test_destination_change_blocks_old_message(self):
        settings={'email':'old@example.org','telegram_chat_id':'','email_enabled':True,'telegram_enabled':False,'categories':delivery.CATEGORIES}
        delivery.save_settings('one',settings);delivery.queue('one','Private result','Body')
        delivery.save_settings('one',{**settings,'email':'new@example.org'})
        with patch.dict(os.environ,{'SMTP_HOST':'smtp.test','SMTP_USER':'sender','SMTP_PASSWORD':'test'}),patch.object(delivery,'email') as sender:
            await delivery.tick();sender.assert_not_called()
        row=delivery.history('one')[0];self.assertEqual(row['status'],'blocked');self.assertEqual(row['destination'],'old@example.org')

    async def test_smtp_tls_submission_contract_and_restart_outbox(self):
        calls=[]
        class SMTP:
            def __init__(self,*args,**kw):calls.append(('connect',args))
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def starttls(self,**kw):calls.append(('tls',bool(kw.get('context'))))
            def login(self,*args):calls.append(('login',True))
            def send_message(self,msg):calls.append(('send',msg['To']));return {}
        delivery.save_settings('one',{'email':'divyansh20060@gmail.com','telegram_chat_id':'','email_enabled':True,'telegram_enabled':False,'categories':delivery.CATEGORIES})
        with patch.dict(os.environ,{'SMTP_HOST':'smtp.test','SMTP_PORT':'587','SMTP_USER':'sender@example.org','SMTP_PASSWORD':'test'}),patch.object(delivery.smtplib,'SMTP',SMTP):
            delivery.queue('one','SMTP test','Test body',is_test=True);await delivery.tick()
            self.assertEqual([c[0] for c in calls],['connect','tls','login','send']);self.assertTrue(delivery.settings('one')['connections']['email']['verified'])
            delivery.queue('one','In-flight','Message')
            with db.connect() as c:c.execute("UPDATE deliveries SET status='sending' WHERE status='pending'")
            delivery.start();await delivery.stop()
            self.assertEqual(delivery.history('one')[0]['status'],'interrupted')

    async def test_routing_collaboration_and_plan_use_real_provider_path(self):
        count=[]
        async def answer(messages,model=None,tools=None):
            system=messages[0]['content'];count.append(system)
            if system.startswith('Route'):return {'content':'{"agents":["drake","stark"],"reason":"Research and business"}'}
            if system.startswith('Create an editable plan'):return {'content':'{"title":"Prepared plan","tasks":[{"title":"Research","instruction":"Research","agent_id":"drake","dependencies":[]},{"title":"Recommend","instruction":"Compare","agent_id":"stark","dependencies":[0]}]}'}
            return {'content':'Contributor or synthesis result'}
        with patch.object(provider,'request',answer):
            turn=await execution.respond('one','Research pricing');planned=await work.plan('Research pricing','parallel','one')
        self.assertFalse(turn.error);self.assertEqual(turn.handled_by,'nova');self.assertEqual(turn.agents,['drake','stark']);self.assertEqual(planned.tasks[1].dependencies,[0])
        self.assertIn('collaboration',[e['kind'] for e in db.events('one')]);self.assertIn('plan_completed',[e['kind'] for e in db.events('one')]);self.assertEqual(len(repo.history('one','__auto__')),2)

class APITests(Base):
    async def test_dashboard_crud_and_openapi_contract(self):
        from main import app
        client=TestClient(app);headers={'Authorization':'Bearer test-access'}
        contract=client.get('/openapi.json').json()
        self.assertEqual(contract['paths']['/api/workflows']['post']['security'],[{'BearerAuth':[]}])
        self.assertNotIn('security',contract['paths']['/api/health']['get'])
        self.assertEqual(client.post('/api/tasks',headers=headers,json={'title':' '}).status_code,422)
        task=client.post('/api/tasks',headers=headers,json={'title':'Dashboard task','due_at':'2020-01-01T00:00:00Z'}).json()['task']
        self.assertTrue(client.post('/api/tasks/'+task['id']+'/complete',headers=headers).json()['ok'])
        self.assertEqual(client.get('/api/tasks?status=all',headers=headers).json()['tasks'][0]['status'],'done')
        self.assertTrue(client.delete('/api/tasks/'+task['id'],headers=headers).json()['ok'])
        client.post('/api/profile',headers=headers,json={'key':'project','value':'NOVA'})
        self.assertEqual(client.get('/api/profile',headers=headers).json()['facts']['project'],'NOVA')
        client.delete('/api/profile/project',headers=headers)
        memory=client.post('/api/memory',headers=headers,json={'content':'Persistent copper preference'}).json()['memory']
        self.assertTrue(client.get('/api/memory/search?q=copper',headers=headers).json()['results'])
        self.assertTrue(client.delete('/api/memory/'+memory['id'],headers=headers).json()['ok'])
        self.assertTrue(client.put('/api/files/notes.txt',headers=headers,content=b'File content').json()['file']['indexed'])
        self.assertEqual(client.get('/api/files/notes.txt',headers=headers).content,b'File content')
        self.assertTrue(client.delete('/api/files/notes.txt',headers=headers).json()['ok'])
        routine=client.post('/api/routines',headers=headers,json={'title':'Check','instruction':'Review tasks','interval_min':5}).json()['routine']
        run=client.post('/api/routines/run/'+routine['id'],headers=headers).json()
        self.assertTrue(run['ok']);self.assertEqual(client.post('/api/routines/run/'+routine['id'],headers=headers).status_code,409)
        self.assertFalse(client.post('/api/routines/'+routine['id']+'/toggle',headers=headers,json={'enabled':False}).json()['routine']['enabled'])
        self.assertTrue(client.delete('/api/routines/'+routine['id'],headers=headers).json()['ok'])
        self.assertGreater(client.get('/api/notifications',headers=headers).json()['unread'],0)
        client.post('/api/notifications/read',headers=headers,json={});self.assertEqual(client.get('/api/notifications',headers=headers).json()['unread'],0)
        self.assertEqual(client.post('/api/delivery/test',headers=headers).status_code,409)

    async def test_sse_stream_frames_replay_persisted_events(self):
        from app.api.nova import stream
        class Connection:
            async def is_disconnected(self):return False
        run=self.create(['stream']);first=db.events('one',run['id'])[-1]['id'];ident=db.event('one','tool_started',run['id'],tool='memory_search')
        response=await stream(run['id'],Connection(),after=first,user='one');iterator=response.body_iterator
        self.assertIn('event: ready',await anext(iterator));frame=await anext(iterator)
        self.assertIn(f'id: {ident}',frame);self.assertIn('tool_started',frame);self.assertNotIn(f'id: {first}\n',frame);await iterator.aclose()

    async def test_authenticated_contract_and_scoping(self):
        app=FastAPI();app.include_router(router)
        client=TestClient(app)
        self.assertEqual(client.get('/api/tasks').status_code,401)
        headers={'Authorization':'Bearer test-access'}
        self.assertEqual(client.get('/api/session',headers=headers).json()['user_id'],'owner')
        self.assertEqual(len(client.get('/api/agents',headers=headers).json()['agents']),15)
        a=client.post('/api/workflows',headers=headers,json={'title':'API mission','tasks':[{'title':'task','instruction':'work'}]}).json()
        app.dependency_overrides[current_user]=lambda:'two'
        self.assertEqual(client.get('/api/workflows/'+a['id']).status_code,404);self.assertEqual(client.get('/api/workflows/'+a['id']+'/stream').status_code,404)
        self.assertEqual(client.post('/api/workflows/'+a['id']+'/cancel').status_code,404)
        app.dependency_overrides.clear()
        self.assertEqual(client.post('/api/workflows/'+a['id']+'/cancel',headers=headers).json()['status'],'cancelled')
        self.assertEqual(client.post('/api/workflows/'+a['id']+'/resume',headers=headers).status_code,409)
        self.assertEqual(client.post('/api/workflows',headers=headers,json={'tasks':[{'title':'bad','instruction':'work','dependencies':[0]}]}).status_code,422)
        self.assertEqual(client.put('/api/delivery/settings',headers=headers,json={'email':'bad\naddress'}).status_code,422)

if __name__=='__main__':unittest.main()
