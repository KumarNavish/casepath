const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert/strict');
const wait=ms=>new Promise(r=>setTimeout(r,ms)),first='clm_314f2d309fea25e6',second='clm_4a07dbbbd859a3ce';
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']}),page=await browser.newPage({viewport:{width:1360,height:900}});await page.addInitScript(()=>window.CASEPATH_PUBLIC_READ_ONLY=true);await page.clock.install();
const observed=()=>page.locator('[data-au-view]').evaluate(el=>({hash:location.hash,revision:el.querySelector('[data-au-revision]')?.dataset.auRevision,title:el.querySelector('h1')?.textContent,op:el.dataset.auCurrentOperation,presentation:el.dataset.auOperationPresentation,available:el.dataset.auOperationResultAvailable,verified:el.dataset.auOperationResultVerified,text:el.textContent}));
const head=JSON.parse(fs.readFileSync('/workspace/operation-runtime-evidence/native-sidecars/'+second+'.json')).frames.at(-1).current_revision;
await page.goto('http://127.0.0.1:4189/?journey=autonomous#autonomous/claim/'+second+'?collection=reference&mode=replay&through='+head);await page.locator('[data-au-revision="'+head+'"]').waitFor();
await page.locator('[data-au-source]').first().click();await page.locator('[data-au-close]').click();
let release,held=false;await page.route('**/claims/'+first+'/replay?through_seq=0',async route=>{if(!held){held=true;await new Promise(r=>release=r);}await route.continue();});
await page.locator('[data-au-nav="demonstration"]').click();for(let i=0;i<100&&!held;i++)await wait(5);assert.ok(held);
const loading=await observed();fs.writeFileSync('/workspace/op-browser/repeated-demo-loading.json',JSON.stringify(loading,null,2));release();
for(let i=0;i<200;i++){await page.clock.runFor(250);await wait(10);const row=await observed();if(row.op&&row.presentation==='playing')break;}
const active=await observed();fs.writeFileSync('/workspace/op-browser/repeated-demo-active.json',JSON.stringify(active,null,2));assert.match(active.hash,new RegExp(first));assert.ok(active.op,'fresh first-case operation consumer must exist');assert.equal(active.presentation,'playing');
await page.locator('[data-au-source]').first().click();const paused=await observed();assert.equal(paused.presentation,'paused');await page.locator('[data-au-close]').click();await page.locator('[data-au-operation-skip]').click();
for(let i=0;i<200;i++){await page.clock.runFor(250);await wait(10);if((await observed()).verified==='true')break;}
const result=await observed();assert.equal(result.verified,'true');assert.equal(result.presentation,'completed');assert.match(result.hash,new RegExp(first));
await page.locator('[data-au-nav="demonstration"]').click();for(let i=0;i<200;i++){await page.clock.runFor(250);await wait(10);if((await observed()).op)break;}
assert.match((await observed()).hash,new RegExp(first));assert.equal((await observed()).presentation,'playing');
fs.writeFileSync('/workspace/op-browser/repeated-demo-result.json',JSON.stringify({loading,active,paused,result},null,2));console.log('PASS repeated demonstration opening, source inspection, paused Skip and restart');await browser.close();
})().catch(error=>{console.error(error);process.exitCode=1;});
