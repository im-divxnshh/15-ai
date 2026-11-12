// Render the actual office components into a standalone, read-only HTML preview.
// This does not run next build, initialize Firebase, access databases or make API calls.
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {createRequire}=require('node:module');
const root=path.resolve(__dirname,'..');const frontend=path.join(root,'frontend');
const use=createRequire(path.join(frontend,'package.json'));
const ts=use('typescript'),React=use('react'),{renderToStaticMarkup}=use('react-dom/server');
const cache=new Map();
function resolve(file){for(const extension of ['','.tsx','.ts','.json'])if(fs.existsSync(file+extension))return file+extension;throw Error('Missing preview component '+file)}
function load(file){
 file=resolve(file);if(cache.has(file))return cache.get(file);
 if(file.endsWith('.json'))return JSON.parse(fs.readFileSync(file,'utf8'));
 const exports={};cache.set(file,exports);
 const source=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
 vm.runInNewContext(source,{exports,module:{exports},require:specifier=>specifier.startsWith('@/')?load(path.join(frontend,specifier.slice(2))):specifier.startsWith('.')?load(path.resolve(path.dirname(file),specifier)):use(specifier)});
 return exports;
}
const roster=load(path.join(frontend,'lib/officeRoster.json'));
const Preview=load(path.join(frontend,'components/OfficePreview.tsx')).default;
const Robot=load(path.join(frontend,'components/OfficeRobot.tsx')).default;
const markup=renderToStaticMarkup(React.createElement(Preview));
const styles=fs.readFileSync(path.join(frontend,'app/globals.css'),'utf8');
const data=JSON.stringify(roster).replaceAll('<','\\u003c');
const geometry=load(path.join(frontend,'lib/officeScene.ts'));
const robotMarkup=Object.fromEntries(roster.map(agent=>[agent.id,renderToStaticMarkup(React.createElement(Robot,{name:agent.name,variant:geometry.ROOMS.findIndex(room=>room.id===agent.id)}))]));
const motionSource=ts.transpileModule(fs.readFileSync(path.join(frontend,'lib/officeScene.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const interactions=`
const roster=${data};
const scene=(()=>{const exports={};${motionSource};return exports})();
const robots=${JSON.stringify(robotMarkup).replaceAll('<','\\u003c')};
const themeButton=document.querySelector('[data-theme-toggle]');
function updateTheme(){const light=document.documentElement.dataset.theme==='light';themeButton.textContent=light?'☾ Dark':'☀ Light';themeButton.setAttribute('aria-label','Switch to '+(light?'dark':'light')+' theme')}
themeButton.addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='light'?'dark':'light';document.documentElement.dataset.theme=next;try{localStorage.setItem('nova-theme',next)}catch{}updateTheme()});updateTheme();
const dialog=document.getElementById('preview-agent-dialog');
document.querySelectorAll('[data-agent-id]').forEach(button=>button.addEventListener('click',()=>{
 const agent=roster.find(a=>a.id===button.dataset.agentId);
 dialog.querySelector('h2').textContent=agent.name;dialog.querySelector('[data-role]').textContent=agent.role;dialog.querySelector('[data-description]').textContent=agent.description;
 const tools=dialog.querySelector('.capability-chips');tools.replaceChildren();agent.tools.forEach(tool=>{const chip=document.createElement('span');chip.textContent=tool.replaceAll('_',' ');tools.appendChild(chip)});
 dialog.querySelector('[data-chat-link]').href='http://localhost:3000/workspace?agent='+encodeURIComponent(agent.id);dialog.showModal();
}));
dialog.querySelector('[data-close]').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()});
document.querySelectorAll('[data-preview-signin]').forEach(a=>a.href='http://localhost:3000/workspace');
document.querySelectorAll('[data-office-view-button]').forEach(button=>button.addEventListener('click',()=>{
 document.querySelector('.office-map-shell').dataset.officeView=button.dataset.officeViewButton;
 document.querySelectorAll('[data-office-view-button]').forEach(other=>{const chosen=other===button;other.classList.toggle('active',chosen);other.setAttribute('aria-pressed',String(chosen))});
}));
const form=document.querySelector('[data-assignment-form]'),select=form.querySelector('[data-demo-agent]'),brief=form.querySelector('[data-demo-brief]'),startButton=form.querySelector('[data-demo-start]'),stopButton=form.querySelector('[data-demo-stop]');
const overlay=document.querySelector('.office-motion'),floor=document.querySelector('.office-floorplan');
let stopMotion=null,moving=false;
function controls(active,finished=false){moving=active;select.disabled=active;brief.disabled=active;startButton.disabled=active||!brief.value.trim();stopButton.disabled=!active;startButton.textContent=active?'Hand-off in motion…':finished?'Replay assignment preview':'Preview assignment'}
function phase(id){const active=scene.PHASE_ORDER.indexOf(id);document.querySelectorAll('[data-flow-phase]').forEach((step,index)=>{step.classList.toggle('done',index<active);step.classList.toggle('current',index===active)})}
function clearMotion(){if(stopMotion)stopMotion();stopMotion=null;overlay.replaceChildren();floor.dataset.travelling='';document.querySelectorAll('[data-away=true]').forEach(room=>room.dataset.away='false')}
brief.addEventListener('input',()=>controls(moving));
select.addEventListener('change',()=>{if(!moving)document.querySelector('[data-flow-agent]').textContent=roster.find(a=>a.id===select.value).name});
form.addEventListener('submit',event=>{
 event.preventDefault();if(moving||!brief.value.trim())return;clearMotion();
 const agent=roster.find(a=>a.id===select.value),svgNS='http://www.w3.org/2000/svg';
 const group=document.createElementNS(svgNS,'g');group.style.setProperty('--agent',agent.accent);
 const route=document.createElementNS(svgNS,'path');route.setAttribute('class','assignment-route');route.setAttribute('d',scene.pathData(scene.routeToNova(agent.id)));
 const sprite=document.createElementNS(svgNS,'g');sprite.setAttribute('class','walking-bot');sprite.innerHTML=robots[agent.id]+'<rect class="assignment-envelope" x="15" y="8" width="13" height="10" rx="2"/><path class="envelope-line" d="M16 9l5 4 6-4"/><text y="48" text-anchor="middle" class="traveller-name"></text>';sprite.querySelector('text.traveller-name').textContent=agent.name;
 group.append(route,sprite);overlay.append(group);floor.dataset.travelling=agent.id;document.querySelector('[data-room="'+agent.id+'"]').dataset.away='true';
 document.querySelector('[data-flow-agent]').textContent=agent.name;document.querySelector('[data-flow-task]').textContent=brief.value.trim();document.querySelector('[data-flow-note]').textContent='Animation demo. No AI work is being executed.';
 controls(true);phase('to_nova');stopMotion=scene.animateAssignment(sprite,agent.id,phase,()=>{controls(false,true);document.querySelector('[data-flow-note]').textContent='Preview finished. No AI task was executed.'});
});
stopButton.addEventListener('click',()=>{clearMotion();controls(false);document.querySelectorAll('[data-flow-phase]').forEach(step=>step.classList.remove('done','current'));document.querySelector('[data-flow-note]').textContent='Preview stopped. No AI work was submitted.'});
`;
const html=`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA OS — Your 15-agent office</title><script>try{document.documentElement.dataset.theme=localStorage.getItem('nova-theme')||(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark')}catch{document.documentElement.dataset.theme='dark'}</script><style>${styles}</style></head><body>${markup}<dialog id="preview-agent-dialog" class="agent-dialog" aria-labelledby="preview-agent-title"><div class="section-top"><div><span class="eyebrow">YOUR SPECIALIST</span><h2 id="preview-agent-title"></h2></div><button class="secondary" data-close>Close</button></div><p data-role></p><p class="helper" data-description></p><h3>Configured capabilities</h3><div class="capability-chips"></div><p class="helper">Live status is unavailable. Sign in to chat after the office is connected.</p><a class="preview-signin" data-chat-link>Open agent chat ↗</a></dialog><script>${interactions}</script></body></html>`;
const target=path.join(frontend,'public/office-preview.html');fs.writeFileSync(target,html);
if((html.match(/data-agent-id=/g)||[]).length!==15)throw Error('Preview must contain all 15 cabins');
if(/cabin--working/.test(markup))throw Error('Read-only preview must not claim working activity');
new vm.Script(interactions);
console.log('Rendered office-preview.html: CEO + 14 cabins, persistent themes, agent details and assignment walking demo. No production build or live execution.');
