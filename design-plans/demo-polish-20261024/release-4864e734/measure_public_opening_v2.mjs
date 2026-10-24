import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire('/Users/kumar0002/Documents/Die Mobiliar/casepath-canonical/casepath-qa/node_modules/playwright/package.json');
const {chromium}=require('playwright');
const out=process.argv[2],expected=process.argv[3];
if(!out||!expected||fs.existsSync(out))throw Error('A fresh output folder and expected source are required.');
fs.mkdirSync(out);
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const context=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:'block'});
const page=await context.newPage(),started=performance.now(),requests=[],errors=[],snapshots=[];
const seen=new Map(),time=()=>Math.round(performance.now()-started);
page.on('pageerror',error=>errors.push(error.message));
page.on('request',r=>{const u=new URL(r.url());if(u.protocol==='https:'){const item={path:u.pathname+u.search,method:r.method(),at:time()};requests.push(item);seen.set(r,item);}});
page.on('response',r=>{const item=seen.get(r.request());if(item){item.status=r.status();item.response_at=time();}});
page.on('requestfailed',r=>{const item=seen.get(r);if(item)item.failure=r.failure()?.errorText;});
let completed=false,probe,error;
try{
 await page.goto('https://casepath-autonomous.kumarnavish.chatgpt.site/?present=1#autonomous/demonstration',{waitUntil:'domcontentloaded',timeout:60000});
 probe=setInterval(()=>{page.evaluate(()=>({purpose:!!document.querySelector('[data-au-ns-purpose]'),preparing:!!document.querySelector('[data-au-presentation-preparing]'),claim:document.querySelector('[data-au-claim-id]')?.dataset.auClaimId||null,heading:document.querySelector('.au-ns-case-title,.au-ns-title,h1')?.textContent||null,active:!!window.CasepathPresentation?.active})).then(v=>snapshots.push({at:time(),...v})).catch(()=>{});},250);
 await page.waitForFunction(()=>window.CasepathPresentation?.active,undefined,{timeout:60000});
 clearInterval(probe);probe=null;
 const ready_at=time();
 await page.evaluate(()=>CasepathPresentation.active.pause());
 await page.evaluate(()=>document.fonts.ready);
 const identity=await page.evaluate(async()=>{const r=await fetch('/deployment.json',{cache:'no-store'});if(!r.ok)throw Error('Deployment identity unavailable');return r.json();});
 if(identity.source_commit!==expected)throw Error('Unexpected public source identity '+identity.source_commit);
 const opening=await page.evaluate(()=>({claim:CasepathPresentation.active.manifest.showcase?.claimId,purpose:document.querySelector('[data-au-ns-purpose]')?.textContent,act:document.querySelector('[data-au-view]')?.dataset.auPresentationAct,controls:[...document.querySelectorAll('.au-executive-transport button')].map(e=>({text:e.textContent,disabled:e.disabled})),state:CasepathPresentation.active.time}));
 await page.screenshot({path:path.join(out,'ready.png')});
 const applicationWrites=requests.filter(r=>!['GET','HEAD'].includes(r.method)&&!r.path.startsWith('/cdn-cgi/'));
 if(errors.length||applicationWrites.length)throw Error('Browser errors or application writes observed.');
 const record={status:'passed',source_commit:expected,measured_at:new Date().toISOString(),ready_at_ms:ready_at,opening,requests,snapshots,errors,application_writes:applicationWrites};
 fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify(record,null,2)+'\n');
 console.log(JSON.stringify({status:record.status,source_commit:expected,ready_at_ms:ready_at,application_requests:requests.filter(r=>r.path.includes('/api/')).length,claim:opening.claim,errors:errors.length,application_writes:applicationWrites.length}));
 completed=true;
}catch(e){error=String(e);try{await page.screenshot({path:path.join(out,'failure.png')});}catch(_){}fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({status:'failed',error,requests,snapshots,errors},null,2)+'\n');throw e;}
finally{if(probe)clearInterval(probe);await context.close();await browser.close();}
