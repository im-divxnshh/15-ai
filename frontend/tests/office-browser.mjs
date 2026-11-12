// The standalone office needs neither credentials, an HTTP listener nor AI calls.
import puppeteer from 'puppeteer-core';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const output=path.join(root,'artifacts/office');fs.mkdirSync(output,{recursive:true});
const report={checks:[],passed:false,scope:'Standalone office UI only. Live execution and service connections are not tested.'};
let browser;
try{
 browser=await puppeteer.launch({executablePath:process.env.CHROME_BIN||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,pipe:true,args:['--no-sandbox','--disable-gpu','--disable-background-networking','--disable-dev-shm-usage'],timeout:15000});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const url=pathToFileURL(path.join(root,'frontend/public/office-preview.html')).href;
 for(const [size,width,height] of [['desktop',1440,1000],['mobile',390,844]]){
  await page.setViewport({width,height});await page.goto(url,{waitUntil:'load'});
  assert.equal(await page.$$eval('[data-room]',rooms=>rooms.length),15);
  assert.equal(await page.$$eval('.ceo-cabin',rooms=>rooms.length),1);
  for(const theme of ['dark','light']){
   await page.evaluate(theme=>{localStorage.setItem('nova-theme',theme);document.documentElement.dataset.theme=theme},theme);
   await page.reload({waitUntil:'load'});
   assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),theme);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'page overflow');
   await page.screenshot({path:path.join(output,`${size}-${theme}.png`),fullPage:true});
   report.checks.push(`${size} ${theme}: 15 cabins, theme persistence and page overflow`);
  }
  await page.click('[data-office-view-button=team]');
  await page.click('[data-room=friday]');await page.waitForSelector('dialog[open]');
  assert.equal(await page.$eval('dialog h2',e=>e.textContent),'Friday');
  assert.ok(await page.$$eval('dialog .capability-chips span',chips=>chips.length)>0);
  await page.click('[data-close]');await page.click('[data-office-view-button=map]');
  await page.select('[data-demo-agent]','friday');await page.click('[data-demo-start]');
  await page.waitForSelector('.walking-bot[data-phase=to_nova]');
  await page.waitForSelector('.walking-bot[data-phase=briefing]',{timeout:6000});
  await page.waitForSelector('.walking-bot[data-phase=returning]',{timeout:4000});
  await page.waitForSelector('.walking-bot[data-phase=at_desk]',{timeout:5000});
  assert.match(await page.$eval('[data-flow-note]',e=>e.textContent),/No AI task was executed/);
  await page.click('[data-demo-start]');await page.click('[data-demo-stop]');
  assert.equal(await page.$('.walking-bot'),null);assert.equal(await page.$$eval('[data-away=true]',rooms=>rooms.length),0);
  report.checks.push(`${size}: cabin details, walk to CEO, brief collection, return and cancellation`);
 }
 await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);
 await page.click('[data-demo-start]');await page.waitForSelector('.walking-bot[data-phase=at_desk]');
 report.checks.push('Reduced motion skips travel animation');
 assert.deepEqual(errors,[]);report.passed=true;
 console.log('Standalone office browser checks passed.');
}catch(error){report.error=error.message;console.error('Office browser verification failed:',error.message);process.exitCode=1;}
finally{if(browser)await browser.close();fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');}
