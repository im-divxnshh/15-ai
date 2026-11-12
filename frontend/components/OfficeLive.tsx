"use client";
import {useEffect,useRef,useState} from 'react';
import {api} from '@/lib/api';
import {eventAssignments,type OfficeAssignment,type AssignmentPhase} from '@/lib/officeScene';
import OfficeGrid,{type OfficeAgent} from './OfficeGrid';
import OfficeHandoff from './OfficeHandoff';

export default function OfficeLive({agents,selected,active,onSelect}:{agents:OfficeAgent[];selected:string|null;active:boolean;onSelect:(agent:OfficeAgent)=>void}){
 const [pending,setPending]=useState<OfficeAssignment[]>([]);const [assignment,setAssignment]=useState<OfficeAssignment|null>(null);const [last,setLast]=useState<OfficeAssignment|null>(null);const [phase,setPhase]=useState<AssignmentPhase>('to_nova');const [eventOffline,setEventOffline]=useState(false);
 const cursor=useRef<number|null>(null);
 useEffect(()=>{
  if(!active){cursor.current=null;setPending([]);setAssignment(null);setLast(null);return;}
  let stopped=false,busy=false;
  async function refresh(){
   if(busy)return;busy=true;
   try{
    const {events}=await api.events();if(stopped)return;
    const max=Math.max(cursor.current??0,...events.map(e=>e.id));setEventOffline(false);
    if(cursor.current!==null){
     const next=eventAssignments(events,cursor.current);
     if(next.length)setPending(previous=>[...previous,...next].slice(-30));
    }
    cursor.current=max;
   }catch{if(!stopped){setEventOffline(true);setPending([]);setAssignment(null);}}
   finally{busy=false;}
  }
  void refresh();const timer=setInterval(()=>void refresh(),3000);return()=>{stopped=true;clearInterval(timer);};
 },[active]);
 useEffect(()=>{if(active&&!eventOffline&&!assignment&&pending.length){setAssignment(pending[0]);setLast(pending[0]);setPhase('to_nova');setPending(previous=>previous.slice(1));}},[active,eventOffline,assignment,pending]);
 return <><OfficeGrid agents={agents} selected={selected} onSelect={onSelect} assignment={active&&!eventOffline?assignment:null} onPhase={setPhase} onMotionEnd={()=>{setPhase('at_desk');setAssignment(null);}}/>{last&&active&&!eventOffline?<div className="office-live-handoff"><OfficeHandoff assignment={assignment||last} phase={phase} agentName={agents.find(a=>a.id===(assignment||last)?.agent_id)?.name||'Agent'}/>{pending.length>0&&<small>{pending.length} recorded hand-offs waiting to be shown</small>}</div>:<p className="office-flow-empty">{eventOffline?'Event connection lost. Office movement is paused until it reconnects.':active?'NOVA’s next assignment will appear here. Hand-offs follow actual backend events.':'Connect the backend to see real assignment workflows. Try the walking demo in the public office preview.'}</p>}</>;
}
