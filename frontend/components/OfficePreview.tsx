"use client";
import {useEffect,useRef,useState} from 'react';
import roster from '@/lib/officeRoster.json';
import OfficeGrid from './OfficeGrid';
import ThemeSwitch from './ThemeSwitch';
import OfficeHandoff from './OfficeHandoff';
import {type OfficeAssignment,type AssignmentPhase} from '@/lib/officeScene';

export default function OfficePreview(){
 const [selected,setSelected]=useState<(typeof roster)[number]|null>(null);
 const [specialist,setSpecialist]=useState('friday');const [brief,setBrief]=useState('Prepare my morning briefing');
 const [assignment,setAssignment]=useState<OfficeAssignment|null>(null);const [phase,setPhase]=useState<AssignmentPhase>('to_nova');const [moving,setMoving]=useState(false);const [finished,setFinished]=useState(false);
 const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{if(selected)dialog.current?.showModal();},[selected]);
 const agents=roster.map(agent=>({...agent,status:'unavailable',current_task:null,last_task:null}));
 return <main className="office-preview">
  <header className="topbar"><div className="brand"><span className="nova-logo">N</span><div><b>NOVA <span>OS</span></b><small>Your AI workspace</small></div></div><div className="top-actions"><ThemeSwitch/><a className="preview-signin" data-preview-signin href="/workspace">Enter workspace ↗</a></div></header>
  <section className="preview-intro"><div><span className="eyebrow">NOVA HEADQUARTERS / FLOOR 01</span><h1>Your team.<br/>In their element.</h1><p>One CEO. Fourteen specialists. Every robot has a cabin, a desk, and a place in your next big idea.</p></div><div className="office-preview-summary"><span><b>15</b> robot agents</span><span><b>14 + 1</b> private cabins + CEO</span><small>Live services unconnected</small></div></section>
  <div className="office-tour-layout"><section className="preview-floor" aria-label="NOVA and fourteen specialist cabins"><div className="floor-label"><span>THE OFFICE</span><span>Public preview · Actual activity unavailable</span></div><OfficeGrid agents={agents} selected={selected?.id} assignment={assignment} onPhase={setPhase} onMotionEnd={()=>{setMoving(false);setFinished(true);}} onSelect={agent=>setSelected(roster.find(a=>a.id===agent.id)||null)}/></section>
  <aside className="office-tour-sidebar"><section className="tour-controls"><span className="eyebrow">WATCH A HAND-OFF</span><h2>A task starts at NOVA.</h2><p>See a specialist walk to the CEO cabin, collect a brief, and return to their own desk.</p><form data-assignment-form onSubmit={e=>{e.preventDefault();setPhase('to_nova');setFinished(false);setMoving(true);setAssignment({id:crypto.randomUUID(),agent_id:specialist,task:brief.trim(),source:'demo'});}}><label>Specialist<select data-demo-agent value={specialist} disabled={moving} onChange={e=>setSpecialist(e.target.value)}>{roster.filter(a=>a.id!=='nova').map(a=><option key={a.id} value={a.id}>{a.name} · {a.role}</option>)}</select></label><label>Example task<input data-demo-brief value={brief} maxLength={180} disabled={moving} onChange={e=>setBrief(e.target.value)}/></label><button data-demo-start disabled={moving||!brief.trim()}>{moving?'Hand-off in motion…':finished?'Replay assignment preview':'Preview assignment'}</button><button data-demo-stop className="secondary" type="button" disabled={!moving} onClick={()=>{setAssignment(null);setMoving(false);setFinished(false);}}>Stop preview</button></form><small>Interactive animation demo. No AI work is submitted.</small></section><OfficeHandoff assignment={assignment} phase={phase} agentName={roster.find(a=>a.id===(assignment?.agent_id||specialist))?.name||'Friday'} finished={finished}/></aside></div>
  {selected&&<dialog ref={dialog} className="agent-dialog" onCancel={e=>{e.preventDefault();setSelected(null);}} onClick={e=>{if(e.target===e.currentTarget)setSelected(null);}}><div className="section-top"><div><span className="eyebrow">{selected.id==='nova'?'CEO & ORCHESTRATOR':'YOUR SPECIALIST'}</span><h2>{selected.name}</h2></div><button className="secondary" aria-label="Close agent details" onClick={()=>setSelected(null)}>Close</button></div><p>{selected.role}</p><p className="helper">{selected.description}</p><h3>Configured capabilities</h3><div className="capability-chips">{selected.tools.map(tool=><span key={tool}>{tool.replaceAll('_',' ')}</span>)}</div><p className="helper">Tool execution, actual work status and chat require your authenticated, connected backend.</p><a className="preview-signin" href={`/workspace?agent=${selected.id}`}>Open agent chat after signing in ↗</a></dialog>}
  <footer className="preview-footer">NOVA OS · 15 minds. One workspace.<br/><small>Connect your office to see actual work and results.</small></footer>
 </main>;
}
