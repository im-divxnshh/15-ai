const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const ts=require('typescript');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
function scene(extra={}){
 const exports={};const source=ts.transpileModule(fs.readFileSync(path.join(root,'lib/officeScene.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 vm.runInNewContext(source,{exports,...extra});return exports;
}
test('Every specialist can reach the CEO and return without crossing another cabin',()=>{
 const s=scene(),roster=JSON.parse(fs.readFileSync(path.join(root,'lib/officeRoster.json'),'utf8'));
 assert.equal(s.ROOMS.length,15);assert.equal(new Set(s.ROOMS.map(r=>r.id)).size,15);
 assert.deepEqual([...s.ROOMS.map(r=>r.id)].sort(),roster.map(a=>a.id).sort());
 const ceo=s.ROOMS.find(r=>r.id==='nova');
 for(const room of s.ROOMS.filter(r=>r.id!=='nova')){
  const route=s.routeToNova(room.id),start=s.assignmentFrame(room.id,0),end=s.assignmentFrame(room.id,8000),brief=s.assignmentFrame(room.id,3500);
  assert.equal(start.point.x,s.home(room).x);assert.equal(end.point.x,start.point.x);assert.equal(end.point.y,start.point.y);assert.ok(end.done);
  assert.ok(brief.point.x>ceo.x&&brief.point.x<ceo.x+ceo.w&&brief.point.y>ceo.y&&brief.point.y<ceo.y+ceo.h);
  for(let p=0;p<=1;p+=.002){
   const point=s.pointAlong(route,p);
   assert.ok(point.x>=0&&point.x<=s.FLOOR.width&&point.y>=0&&point.y<=s.FLOOR.height);
   for(const other of s.ROOMS.filter(r=>r.id!==room.id&&r.id!=='nova'))assert.ok(!(point.x>other.x&&point.x<other.x+other.w&&point.y>other.y&&point.y<other.y+other.h),room.id+' crosses '+other.id);
  }
 }
});
test('Animation reaches the desk, supports cancellation, and honors reduced motion',()=>{
 let id=0;const frames=new Map(),phases=[],positions=[];let done=0;
 const s=scene({window:{matchMedia:()=>({matches:false})},requestAnimationFrame:fn=>{frames.set(++id,fn);return id},cancelAnimationFrame:key=>frames.delete(key)});
 const sprite={dataset:{},setAttribute:(_,value)=>positions.push(value),closest:()=>null};
 const stop=s.animateAssignment(sprite,'friday',p=>phases.push(p),()=>done++);
 function step(time){const [key,fn]=frames.entries().next().value;frames.delete(key);fn(time)}
 for(const time of [0,1500,3000,4400,5900,7400])step(time);
 assert.deepEqual(phases,['to_nova','briefing','returning','at_desk']);assert.equal(done,1);assert.equal(positions[0],positions.at(-1));assert.equal(frames.size,0);stop();
 const cancel=s.animateAssignment(sprite,'friday',()=>{},()=>done++);cancel();assert.equal(frames.size,0);assert.equal(done,1);
 const r=scene({window:{matchMedia:()=>({matches:true})},requestAnimationFrame:fn=>{fn(0);return 1},cancelAnimationFrame:()=>{}});
 let phase;r.animateAssignment(sprite,'friday',p=>phase=p,()=>done++);assert.equal(phase,'at_desk');assert.equal(done,2);
});
test('Only new, recorded assignments produce movement; tool and completion events do not',()=>{
 const s=scene();const event=(id,kind,agent_id,payload={})=>({id,kind,agent_id,payload,created_at:'2026-11-12T00:00:00Z'});
 const events=[event(1,'routing','nova',{agents:['friday']}),event(2,'routing','nova',{agents:['friday','drake','nova','unknown']}),event(3,'agent_started','friday',{task:'Brief me'}),event(4,'tool_started','drake'),event(5,'agent_completed','drake'),event(6,'agent_started','drake',{task:'Research'}),event(7,'agent_started','friday',{task:'A separate task'})];
 const assignments=s.eventAssignments(events,1);
 assert.deepEqual([...assignments.map(a=>a.agent_id)],['friday','drake','friday']);assert.ok(assignments.every(a=>a.source==='event'));
 assert.equal(s.eventAssignments(events,7).length,0);
});
