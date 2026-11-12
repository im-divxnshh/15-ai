export type Point={x:number;y:number};
export type Room={id:string;x:number;y:number;w:number;h:number};
export type AssignmentPhase='to_nova'|'briefing'|'returning'|'at_desk';
export type OfficeAssignment={id:string;agent_id:string;task:string;source:'demo'|'event';created_at?:string};
export const FLOOR={width:1100,height:830};
const ORDER=['echo','veronica','nova','michel','oracle','zeus','athena','drake','friday','stark','elena','gecko','gaya','kratos','pepper'];
export const ROOMS:Room[]=ORDER.map((id,index)=>({id,x:34+(index%5)*212,y:54+Math.floor(index/5)*250,w:184,h:198}));
export const PHASE_LABELS:Record<AssignmentPhase,string>={to_nova:'Going to NOVA',briefing:'Collecting assignment',returning:'Returning to cabin',at_desk:'At the desk'};
export const PHASE_ORDER:AssignmentPhase[]=['to_nova','briefing','returning','at_desk'];
export function home(room:Room):Point{return {x:room.x+room.w*.32,y:room.y+room.h*.39};}
export function routeToNova(agentId:string):Point[]{
 const room=ROOMS.find(r=>r.id===agentId),ceo=ROOMS.find(r=>r.id==='nova')!;
 if(!room||room.id==='nova')return [];
 const door={x:room.x+room.w/2,y:room.y+room.h},hall=door.y+25,ceoDoor={x:ceo.x+ceo.w/2,y:ceo.y+ceo.h};
 return [home(room),{x:home(room).x,y:door.y-22},door,{x:door.x,y:hall},{x:18,y:hall},{x:18,y:ceoDoor.y+25},{x:ceoDoor.x,y:ceoDoor.y+25},ceoDoor,{x:ceoDoor.x,y:ceo.y+145}];
}
export function pathData(points:Point[]):string{return points.map((p,i)=>`${i?'L':'M'} ${p.x} ${p.y}`).join(' ');}
export function pointAlong(points:Point[],progress:number):Point{
 if(!points.length)return {x:0,y:0};
 const lengths=points.slice(1).map((p,i)=>Math.hypot(p.x-points[i].x,p.y-points[i].y));
 let distance=lengths.reduce((a,b)=>a+b,0)*Math.max(0,Math.min(1,progress));
 for(let i=0;i<lengths.length;i++){if(distance<=lengths[i]&&lengths[i]>0){const t=distance/lengths[i];return {x:points[i].x+(points[i+1].x-points[i].x)*t,y:points[i].y+(points[i+1].y-points[i].y)*t};}distance-=lengths[i];}
 return points[points.length-1];
}
// These phases illustrate a recorded hand-off. They never change execution state.
export function assignmentFrame(agentId:string,elapsed:number):{point:Point;phase:AssignmentPhase;done:boolean}{
 const path=routeToNova(agentId);
 if(elapsed<3000)return {point:pointAlong(path,elapsed/3000),phase:'to_nova',done:false};
 if(elapsed<4400)return {point:pointAlong(path,1),phase:'briefing',done:false};
 if(elapsed<7400)return {point:pointAlong([...path].reverse(),(elapsed-4400)/3000),phase:'returning',done:false};
 return {point:pointAlong(path,0),phase:'at_desk',done:true};
}
export function animateAssignment(sprite:SVGGElement,agentId:string,onPhase:(phase:AssignmentPhase)=>void,onDone:()=>void):()=>void{
 let frame=0,start:number|undefined,last:AssignmentPhase|undefined;
 const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 function tick(now:number){
  start??=now;const state=assignmentFrame(agentId,reduced?7400:now-start);
  sprite.setAttribute('transform',`translate(${state.point.x} ${state.point.y})`);
  sprite.dataset.phase=state.phase;
  const viewport=sprite.closest('.office-viewport') as HTMLElement|null;
  const floor=sprite.closest('.office-floorplan') as HTMLElement|null;
  if(viewport&&floor&&floor.closest('[data-office-view=map]')){
   const scale=floor.clientWidth/FLOOR.width;
   viewport.scrollLeft=Math.max(0,state.point.x*scale-viewport.clientWidth/2);
   viewport.scrollTop=Math.max(0,state.point.y*scale-viewport.clientHeight/2);
  }
  if(last!==state.phase){last=state.phase;onPhase(state.phase);}
  if(state.done){onDone();return;}frame=requestAnimationFrame(tick);
 }
 frame=requestAnimationFrame(tick);return ()=>cancelAnimationFrame(frame);
}
export type AssignmentEvent={id:number;kind:string;agent_id:string|null;payload:Record<string,unknown>;created_at:string};
export function eventAssignments(events:AssignmentEvent[],after:number):OfficeAssignment[]{
 const out:OfficeAssignment[]=[];
 for(const event of [...events].sort((a,b)=>a.id-b.id)){
  if(event.id<=after)continue;
  const ids=event.kind==='agent_started'?[event.agent_id]:[];
  for(const id of ids){
   if(typeof id!=='string'||id==='nova'||!ROOMS.some(r=>r.id===id))continue;
   out.push({id:String(event.id)+'-'+id,agent_id:id,task:String(event.payload.task||'NOVA assigned work'),source:'event',created_at:event.created_at});
  }
 }
 return out;
}
