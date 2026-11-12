// Local Groq contract subset; deliberately returns 501 for unused routes.
const http=require('node:http');
const server=http.createServer((req,res)=>{
 const reply=(status,body)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(body));};
 if(req.method!=='POST'||req.url!=='/openai/v1/chat/completions')return reply(501,{error:{message:'Endpoint is outside this simulation contract'}});
 const handle=body=>{
  if(!body||typeof body.model!=='string'||!Array.isArray(body.messages))return reply(400,{error:{message:'model and messages are required'}});
  const text=body.messages.at(-1)?.content||'';
  if(text.includes('FAIL_PROVIDER'))return reply(503,{error:{message:'Injected transient provider failure'}});
  if(text.includes('AUTH_FAILURE'))return reply(401,{error:{message:'Injected credential failure'}});
  let message={role:'assistant',content:'Simulated verification reply: '+text};
  if(text.includes('TOOL_REQUEST'))message={role:'assistant',content:null,tool_calls:[{id:'tool-1',type:'function',function:{name:'create_task',arguments:JSON.stringify({title:'Created by actual tool'})}}]};
  return reply(200,{choices:[{message}]});
 };
 if(req.body!==undefined)return handle(req.body);
 let raw='';req.on('data',chunk=>raw+=chunk);req.on('end',()=>{try{handle(JSON.parse(raw));}catch{return reply(400,{error:{message:'Invalid JSON'}});}});
});
server.listen(process.env.PORT||4010);
