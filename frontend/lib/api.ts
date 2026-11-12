import {auth} from './firebaseClient';
export const BASE=(process.env.NEXT_PUBLIC_BACKEND_URL||'http://localhost:8000').replace(/\/$/,'');
export type Agent={id:string;name:string;role:string;layer:string;accent:string;is_orchestrator:boolean;status:string;current_task:string|null;last_task:string|null;tools:string[];tasks:string[];calls_handled:number|null};
export type PlanTask={title:string;instruction:string;agent_id:string|null;dependencies:number[]};
export type Plan={title:string;instruction?:string;mode:'sequential'|'parallel';concurrency:number;tasks:PlanTask[];client_key?:string};
export type Step=PlanTask&{id:string;position:number;status:string;result:string|null;error:string|null;agents:string[];attempts:number};
export type Event={id:number;kind:string;agent_id:string|null;step_id:string|null;payload:Record<string,unknown>;created_at:string};
export type Workflow={id:string;title:string;status:string;mode:string;completed:number;total:number;steps:Step[];events?:Event[]};
export type DeliverySettings={email:string;telegram_chat_id:string;email_enabled:boolean;telegram_enabled:boolean;categories:string[];connections:Record<string,{configured:boolean;verified:boolean;tested_at:string|null}>};
export type Delivery={id:number;channel:string;title:string;body:string;status:string;attempts:number;error:string|null;created_at:string;destination:string};
export type Doc={id:string;created_at:string;[key:string]:unknown};
export type Health={store?:{backend:string;implemented:boolean};status:string;provider:string;missing_env:string[];worker:{running:boolean;active_tasks:number};auth:{local:boolean;firebase:boolean;token:boolean}};
export const message=(e:unknown)=>e instanceof Error?e.message:'Request failed.';
export async function headers(){const user=auth?.currentUser;const token=user?await user.getIdToken():typeof window==='undefined'?'':sessionStorage.getItem('nova-access-token');return token?{Authorization:`Bearer ${token}`}:{ } as Record<string,string>;}
export async function request<T>(path:string,init:RequestInit={}):Promise<T>{
  let response:Response;
  try{response=await fetch(BASE+path,{...init,headers:{...await headers(),...init.headers},cache:'no-store'});}catch{throw new Error('Backend is offline. Reconnecting automatically; start the backend to continue.');}
  if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:Array.isArray(body.detail)?body.detail.map((d:{msg?:string})=>d.msg||'Invalid input').join('; '):`Request failed (${response.status}).`);}
  return response.json();
}
export const get=<T,>(p:string)=>request<T>(p);
export const post=<T,>(p:string,b?:unknown)=>request<T>(p,{method:'POST',headers:{'Content-Type':'application/json'},body:b===undefined?undefined:JSON.stringify(b)});
export const del=(p:string)=>request<{ok:boolean}>(p,{method:'DELETE'});
export const api={
  health:()=>get<Health>('/api/health'),session:()=>get<{user_id:string}>('/api/session'),agents:()=>get<{agents:Agent[]}>('/api/agents'),
  runs:()=>get<{workflows:Workflow[];worker:Health['worker']}>('/api/workflows'),run:(id:string,after=0)=>get<Workflow>(`/api/workflows/${id}?after=${after}`),
  plan:(instruction:string,mode:string)=>post<Plan>('/api/workflows/plan',{instruction,mode}),create:(p:Plan)=>post<Workflow>('/api/workflows',p),control:(id:string,action:string)=>post<Workflow>(`/api/workflows/${id}/${action}`),
  history:(id:string)=>get<{messages:{role:string;content:string;created_at:string}[]}>(`/api/history?agent_id=${encodeURIComponent(id)}`),
  chat:(message:string,agent_id:string|null)=>post<{reply:string;agent:{name:string};error:string|null;agents_involved:string[]}>('/api/chat',{message,agent_id}),
  clearHistory:(id:string)=>del(`/api/history?agent_id=${encodeURIComponent(id)}`),
  settings:()=>get<DeliverySettings>('/api/delivery/settings'),saveSettings:(p:DeliverySettings)=>request<DeliverySettings>('/api/delivery/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)}),
  deliveries:()=>get<{deliveries:Delivery[]}>('/api/delivery'),test:()=>post('/api/delivery/test'),retryDelivery:(id:number)=>post(`/api/delivery/${id}/retry`),
  docs:(kind:string)=>get<Record<string,Doc[]>>('/api/'+kind+(kind==='tasks'?'?status=all':'')),events:()=>get<{events:Event[]}>('/api/events'),
};
export async function stream(id:string,after:number,signal:AbortSignal,onEvent:(e:Event)=>void,onState:(s:string)=>void){
 let cursor=after,delay=1000;
 while(!signal.aborted){
  try{onState('connecting');const res=await fetch(`${BASE}/api/workflows/${id}/stream?after=${cursor}`,{headers:await headers(),signal});if(!res.ok||!res.body)throw new Error('Stream unavailable');onState('live');delay=1000;const reader=res.body.getReader();const decoder=new TextDecoder();let buffer='';
   while(!signal.aborted){const chunk=await reader.read();if(chunk.done)break;buffer+=decoder.decode(chunk.value,{stream:true}).replace(/\r/g,'');let end;
    while((end=buffer.indexOf('\n\n'))>=0){const frame=buffer.slice(0,end);buffer=buffer.slice(end+2);if(frame.includes('event: ready'))continue;const data=frame.split('\n').filter(l=>l.startsWith('data:')).map(l=>l.slice(5).trim()).join('\n');if(data){const event=JSON.parse(data) as Event;if(event.id>cursor){cursor=event.id;onEvent(event);}}}
   }
  }catch{if(signal.aborted)return;onState('reconnecting');}
  if(signal.aborted)return;
  await new Promise<void>(resolve=>{const finish=()=>{clearTimeout(timer);signal.removeEventListener('abort',finish);resolve();};const timer=setTimeout(finish,delay);signal.addEventListener('abort',finish,{once:true});});delay=Math.min(15000,delay*2);
 }
}
