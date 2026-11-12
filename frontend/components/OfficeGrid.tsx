"use client";
import {useEffect,useRef,useState,type CSSProperties} from 'react';
import {FLOOR,ROOMS,home,routeToNova,pathData,animateAssignment,type OfficeAssignment,type AssignmentPhase} from '@/lib/officeScene';
import OfficeRobot from './OfficeRobot';
export type OfficeAgent={id:string;name:string;role:string;accent:string;status:string;current_task:string|null;last_task:string|null};
type Props={agents:OfficeAgent[];selected?:string|null;onSelect:(agent:OfficeAgent)=>void;assignment?:OfficeAssignment|null;onPhase?:(phase:AssignmentPhase)=>void;onMotionEnd?:()=>void};
export default function OfficeGrid({agents,selected,onSelect,assignment,onPhase,onMotionEnd}:Props){
 const [view,setView]=useState('map');const sprite=useRef<SVGGElement>(null);
 const callbacks=useRef({onPhase,onMotionEnd});callbacks.current={onPhase,onMotionEnd};
 useEffect(()=>{
  if(!assignment||!sprite.current)return;
  return animateAssignment(sprite.current,assignment.agent_id,phase=>callbacks.current.onPhase?.(phase),()=>callbacks.current.onMotionEnd?.());
 },[assignment?.id]);
 const traveller=assignment&&agents.find(a=>a.id===assignment.agent_id);
 return <div className="office-map-shell" data-office-view={view}>
  <div className="map-toolbar"><div><span className="map-floor-icon">⌘</span><b>Workspace / Floor 01</b><span className="map-toolbar-hint">Select a cabin to open its agent</span></div><div className="map-view-switch" aria-label="Office view"><button className={view==='map'?'active':''} data-office-view-button="map" aria-pressed={view==='map'} onClick={()=>setView('map')}>Floor plan</button><button className={view==='team'?'active':''} data-office-view-button="team" aria-pressed={view==='team'} onClick={()=>setView('team')}>Cabin list</button></div></div>
  <div className="office-viewport" tabIndex={0} aria-label="Office floor, scroll to explore all cabins">
   <div className="office-floorplan" data-travelling={assignment?.agent_id||''}>
    <svg className="office-architecture" viewBox={`0 0 ${FLOOR.width} ${FLOOR.height}`} aria-hidden="true"><defs><pattern id="floor-tiles" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" fill="none" className="floor-tile-line"/></pattern></defs><rect x="4" y="4" width="1092" height="822" rx="18" className="floor-base"/><rect x="4" y="4" width="1092" height="822" rx="18" fill="url(#floor-tiles)"/>{[277,527,777].map(y=><g key={y}><path d={`M18 ${y}H1080`} className="hallway-line"/><path d={`M20 ${y}H1080`} className="hallway-center"/></g>)}<path d="M18 277V777" className="hallway-line"/><text x="34" y="30" className="floor-text">NOVA HEADQUARTERS</text><text x="1074" y="30" textAnchor="end" className="floor-text">15 PRIVATE CABINS</text>{[277,527,777].map((y,i)=><text key={y} x="550" y={y+5} textAnchor="middle" className="hall-label">{i===0?'EXECUTIVE WALKWAY':i===1?'COLLABORATION WALKWAY':'SPECIALIST WALKWAY'}</text>)}</svg>
    {ROOMS.map((room,index)=>{const agent=agents.find(a=>a.id===room.id);if(!agent)return null;
     const task=agent.current_task||(agent.status==='unavailable'?'Live activity unavailable':agent.status==='failed'?'Review failure':agent.status==='interrupted'?'Review interrupted work':'Ready for your next task');
     return <button key={agent.id} data-agent-id={agent.id} data-room={agent.id} data-away={assignment?.agent_id===agent.id} className={`cabin office-cabin ${agent.id==='nova'?'cabin-nova ceo-cabin':''} cabin--${agent.status} ${selected===agent.id?'cabin-selected':''}`} style={{'--agent':agent.accent,left:`${room.x/FLOOR.width*100}%`,top:`${room.y/FLOOR.height*100}%`,width:`${room.w/FLOOR.width*100}%`,height:`${room.h/FLOOR.height*100}%`} as CSSProperties} onClick={()=>onSelect(agent)} aria-label={`${agent.name}, ${agent.id==='nova'?'CEO and orchestrator':agent.role}, ${agent.status}`} aria-pressed={selected===agent.id} title={agent.current_task||agent.last_task||agent.role}>
      <div className="cabin-room"><span className="room-plaque">{agent.id==='nova'?'CEO OFFICE':`CABIN ${String(index+1).padStart(2,'0')}`}</span><span className="room-window"/><span className="room-rug"/><span className="room-plant"><i/><i/><i/></span><span className="room-shelf"/><span className="room-desk"><i className="desk-keyboard"/><i className="desk-coffee"/></span><span className="room-monitor"><i/>{agent.status==='working'&&<span className="monitor-code">•••</span>}</span><span className="room-chair"/><span className="room-bot"><OfficeRobot name={agent.name} variant={index}/></span><span className="room-door"/>{agent.id==='nova'&&<span className="ceo-meeting-chair"/>}</div>
      <div className="cabin-name"><span className={`status-dot status-dot--${agent.status}`}/><b>{agent.name}</b>{agent.id==='nova'&&<span className="orchestrator-tag">CEO</span>}</div><div className="cabin-role">{agent.role}</div><div className="cabin-task"><span>{agent.status==='unavailable'?'Unconnected':agent.status}</span> · {task}</div>
     </button>;
    })}
    <svg className="office-motion" viewBox={`0 0 ${FLOOR.width} ${FLOOR.height}`} aria-hidden="true">
     {traveller&&assignment&&<g key={assignment.id} style={{'--agent':traveller.accent} as CSSProperties}><path className="assignment-route" d={pathData(routeToNova(traveller.id))}/><g ref={sprite} className="walking-bot" transform={`translate(${home(ROOMS.find(r=>r.id===traveller.id)!).x} ${home(ROOMS.find(r=>r.id===traveller.id)!).y})`}><OfficeRobot name={traveller.name} variant={ROOMS.findIndex(r=>r.id===traveller.id)}/><rect className="assignment-envelope" x="15" y="8" width="13" height="10" rx="2"/><path className="envelope-line" d="M16 9l5 4 6-4"/><text y="48" textAnchor="middle" className="traveller-name">{traveller.name}</text></g></g>}
    </svg>
   </div>
  </div>
  <div className="map-caption"><span>▧ Each agent has a private cabin and desk</span><span>Scroll to explore · Use cabin list for a compact view</span></div>
 </div>;
}
