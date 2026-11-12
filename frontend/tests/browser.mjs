// Real Chromium checks against the production frontend and disposable backend.
// This establishes UI behavior with simulated providers, never live connectivity.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import puppeteer from 'puppeteer-core';

const base=process.env.NOVA_BROWSER_URL||'http://localhost:3000';
const candidates=[process.env.CHROME_BIN,'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/usr/bin/chromium','/usr/bin/google-chrome',path.join(os.homedir(),'.cache/puppeteer/chrome-headless-shell/mac-146.0.7680.31/chrome-headless-shell-mac-x64/chrome-headless-shell')].filter(Boolean);
let executablePath;
for(const candidate of candidates){try{await fs.access(candidate);executablePath=candidate;break;}catch{}}
if(!executablePath)throw new Error('Install Chrome/Chromium or set CHROME_BIN to its executable.');
const artifacts=path.resolve('../artifacts/browser');await fs.mkdir(artifacts,{recursive:true});
let browser;
const report={provider:'simulated',checks:[],screenshots:[]};
try{
 browser=await puppeteer.launch({executablePath,headless:true,pipe:true,args:process.env.NOVA_CHROME_NO_SANDBOX==='1'?['--no-sandbox']:[]});
 const page=await browser.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const click=async text=>{await page.waitForFunction(t=>[...document.querySelectorAll('button')].some(b=>b.textContent.trim()===t&&!b.disabled),{},text);await page.evaluate(t=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===t&&!b.disabled).click(),text);};
 const fill=async(selector,text)=>{await page.waitForSelector(selector);await page.$eval(selector,(el,text)=>{const setter=Object.getOwnPropertyDescriptor(el instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set;setter.call(el,text);el.dispatchEvent(new Event('input',{bubbles:true}));},text);};
 await page.goto(base+'/workspace',{waitUntil:'networkidle2'});
 const fixture=await page.evaluate(async()=>{const r=await fetch('http://localhost:8000/api/health');return r.json()});
 assert.equal(fixture.verification,'simulated-disposable-harness','Run backend/tests/browser_server.py; never run these writes against your live office.');
 await fill('[aria-label="Office access token"]','nova-browser-test');await click('Connect office');await page.waitForSelector('.cabin');
 assert.equal(await page.$$eval('.cabin',e=>e.length),15);report.checks.push('15 cabins and authenticated roster');
 for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
  await page.setViewport(viewport);
  for(const theme of ['dark','light']){
   await page.evaluate(t=>{localStorage.setItem('nova-theme',t);document.documentElement.dataset.theme=t},theme);await page.reload({waitUntil:'networkidle2'});await page.waitForSelector('.cabin');
   assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),theme);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Page must not overflow horizontally');
   assert.equal(await page.$$eval('.room-bot .office-robot',e=>e.length),15);
   const file=path.join(artifacts,`${viewport.width}-${theme}.png`);await page.screenshot({path:file,fullPage:true});report.screenshots.push(file);
  }
 }
 report.checks.push('Desktop/mobile layout and persistent dark/light themes');
 await page.click('.cabin[aria-label^="Michel,"]');await page.waitForFunction(()=>document.querySelector('h2')?.textContent==='Michel');await page.click('details.card summary');
 assert.ok((await page.$eval('details.card',el=>el.textContent)).includes('Available tools'));report.checks.push('Cabin opens matching agent capabilities');
 await fill('[aria-label="Chat message"]','Verify a reply');await click('Send');await page.waitForFunction(()=>document.querySelector('.conversation')?.textContent.includes('Simulated verification reply'));
 await click('Clear history');report.checks.push('Chat reply and history clearing');
 await click('Missions');await fill('[aria-label="Task 1 title"]','Slow verification');await fill('[aria-label="Task 1 instruction"]','slow verification');await click('Queue 1 task');
 await page.waitForFunction(()=>[...document.querySelectorAll('.cabin')].some(e=>e.classList.contains('cabin--working')),{timeout:15000});
 await click('Pause');await page.waitForFunction(()=>[...document.querySelectorAll('.badge')].some(e=>e.textContent==='paused'));await click('Cancel');report.checks.push('Working animation, pause and cancellation');
 await click('+ Add work');await fill('[aria-label="Task 1 title"]','Provider failure');await fill('[aria-label="Task 1 instruction"]','FAIL_PROVIDER');await click('Queue 1 task');
 await page.waitForFunction(()=>[...document.querySelectorAll('.badge')].some(e=>e.textContent==='failed'),{timeout:20000});
 await click('Retry unsuccessful tasks');await page.waitForFunction(()=>document.querySelector('.screen')?.textContent.includes('attempt 2'),{timeout:20000});report.checks.push('Provider error and explicit retry');
 await click('+ Add work');await click('NOVA plan');await fill('[aria-label="Batch or plan instruction"]','Inspect, then recommend');await click('Generate editable plan');await page.waitForSelector('[aria-label="Task 2 title"]');
 await fill('[aria-label="Task 2 title"]','Edited recommendation');await click('Queue 2 tasks');await page.waitForFunction(()=>document.querySelector('.screen')?.textContent.includes('2 of 2 tasks completed'),{timeout:20000});report.checks.push('Editable plan, dependency results and live workflow completion');
 await click('Tasks');await fill('[aria-label="tasks title"]','Verify reminder');await click('Save task');await click('Mark done');assert.ok((await page.$eval('.screen',e=>e.textContent)).includes('done'));report.checks.push('Task creation and completion');
 await click('Memory');await fill('[aria-label="memory title"]','Remember copper preference');await click('Save memory');assert.ok((await page.$eval('.screen',e=>e.textContent)).includes('copper'));report.checks.push('Memory persistence controls');
 await click('Files');const file=path.join(artifacts,'verification.txt');await fs.writeFile(file,'Uploaded verification document');await (await page.$('[aria-label="Upload file"]')).uploadFile(file);await page.waitForFunction(()=>document.querySelector('.screen')?.textContent.includes('verification.txt'));await click('Delete');report.checks.push('File upload/index/delete');
 await click('Routines');await fill('[aria-label="routines title"]','Verification routine');await fill('[aria-label="Routine instruction"]','Review current tasks');await click('Save routine');await click('Disable');await click('Queue now');report.checks.push('Routine creation, toggle and run');
 await click('Alerts');await click('Approve command');await page.waitForFunction(()=>document.querySelector('.screen')?.textContent.includes('exit_code'));await click('Mark alerts read');report.checks.push('Command approval and alert controls');
 await click('Delivery');await page.click('input[type=checkbox]');await click('Save & test connections');await page.waitForFunction(()=>document.querySelector('.screen')?.textContent.includes('Add SMTP sender settings'),{timeout:10000});report.checks.push('Missing credentials produce blocked delivery');
 await page.setOfflineMode(true);await new Promise(r=>setTimeout(r,4000));assert.ok((await page.$eval('body',e=>e.textContent)).includes('Reconnecting'));await page.setOfflineMode(false);await page.waitForFunction(()=>!document.querySelector('.connection-banner[role=alert]'),{timeout:15000});report.checks.push('Offline indicator and recovery');
 assert.deepEqual(errors,[],'No browser runtime errors');await click('Sign out');await page.waitForSelector('[aria-label="Office access token"]');report.checks.push('Sign out');
 report.passed=true;console.log(JSON.stringify(report,null,2));
}catch(error){report.passed=false;report.error=error.message;console.error(error.message);process.exitCode=1;}
finally{await fs.writeFile(path.join(artifacts,'report.json'),JSON.stringify(report,null,2));if(browser)await browser.close();}
