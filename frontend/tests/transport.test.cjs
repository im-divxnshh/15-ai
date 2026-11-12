const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const ts=require('typescript');

function client(fetch){
 const exports={};const source=ts.transpileModule(fs.readFileSync('lib/api.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 vm.runInNewContext(source,{exports,module:{exports},require:()=>({auth:{currentUser:{getIdToken:async()=> 'verification-token'}}}),process:{env:{NEXT_PUBLIC_BACKEND_URL:'http://verification.invalid'}},fetch,TextDecoder,AbortController,setTimeout:(fn,ms)=>setTimeout(fn,Math.min(ms,5)),clearTimeout,Error,JSON});
 return exports;
}

test('SSE reconnect carries the cursor and authorization, ignores duplicates, and aborts cleanly',async()=>{
 const calls=[],states=[],events=[];const controller=new AbortController();let attempt=0;
 const api=client(async(url,options)=>{
  calls.push({url,headers:options.headers});attempt++;
  if(attempt===1)throw Error('offline');
  const frames=attempt===2?'event: ready\ndata: {}\n\nid: 1\ndata: {"id":1,"kind":"step_started"}\n\nid: 1\ndata: {"id":1,"kind":"step_started"}\n\nid: 2\ndata: {"id":2,"kind":"tool_completed"}\n\n':'id: 3\ndata: {"id":3,"kind":"step_completed"}\n\n';
  const bytes=new TextEncoder().encode(frames);
  return new Response(new ReadableStream({start(s){s.enqueue(bytes.slice(0,23));s.enqueue(bytes.slice(23));s.close()}}),{status:200});
 });
 await api.stream('run',0,controller.signal,event=>{events.push(event);if(event.id===3)controller.abort()},state=>states.push(state));
 assert.deepEqual(events.map(e=>e.id),[1,2,3]);assert.ok(states.includes('reconnecting'));
 assert.ok(calls.at(-1).url.endsWith('?after=2'));assert.equal(calls.length,3);
 for(const call of calls){assert.equal(call.headers.Authorization,'Bearer verification-token');assert.ok(!call.url.includes('verification-token'))}
});

test('Validation, offline and authentication errors surface without fake responses',async()=>{
 let scenario='validation';const api=client(async()=>{
  if(scenario==='offline')throw Error('no route');
  if(scenario==='authentication')return new Response(JSON.stringify({detail:'Invalid or expired token'}),{status:401});
  return new Response(JSON.stringify({detail:[{msg:'Invalid dependency'}]}),{status:422});
 });
 await assert.rejects(api.get('/api/workflows'),/Invalid dependency/);
 scenario='offline';await assert.rejects(api.get('/api/workflows'),/Backend is offline/);
 scenario='authentication';await assert.rejects(api.get('/api/workflows'),/Invalid or expired token/);
});
