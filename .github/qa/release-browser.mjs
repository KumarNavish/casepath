/* Portable release inspection, not the historical Mac/ego acceptance suite.
 * Uses the real pinned local launcher and an isolated journal. Never calls a provider.
 */
import fs from 'node:fs/promises';
import {openSync, closeSync} from 'node:fs';
import path from 'node:path';
import {spawn, execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const root=process.cwd();
const require=createRequire(path.join(root,'casepath-qa/package.json'));
const {chromium}=require('playwright');
const AxeBuilder=require('@axe-core/playwright').default;
const out=path.resolve(process.argv[2]);
await fs.mkdir(out,{recursive:true});
const base='http://127.0.0.1:4173';
const claim='clm_0e538990cc6ba7ef';
const observation={contract:'casepath.release-browser-observation/1',commit:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),claim_id:claim,checks:[],screenshots:[],page_errors:[],console_errors:[],accessibility:[],scope:'Fresh real product inspection; not model competence, legal correctness, or historical ego acceptance.'};
let browser,context,server;
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function json(url){const r=await fetch(base+url);assert.equal(r.status,200,`${url}: HTTP ${r.status}`);return r.json();}
function check(name,actual){assert.ok(actual,name);observation.checks.push({name,passed:true});}
async function snapshot(page,name,width=1440,height=1000){
  await page.setViewportSize({width,height});
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  await page.screenshot({path:path.join(out,name+'.png'),animations:'disabled'});
  await fs.writeFile(path.join(out,name+'.txt'),await page.locator('body').innerText());
  await fs.writeFile(path.join(out,name+'.html'),await page.content());
  const geometry=await page.evaluate(()=>({viewport:{width:innerWidth,height:innerHeight},document:{width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight},focused:document.activeElement?.outerHTML,controls:[...document.querySelectorAll('button,a,input,select,summary,[role="tab"]')].filter(el=>el.getClientRects().length).map(el=>({tag:el.tagName,id:el.id,text:el.textContent.trim().slice(0,150),label:el.getAttribute('aria-label'),rect:el.getBoundingClientRect().toJSON()}))}));
  await fs.writeFile(path.join(out,name+'-geometry.json'),JSON.stringify(geometry,null,2)+'\n');
  observation.screenshots.push({name,width,height});
}
async function axe(page,name){const result=await new AxeBuilder({page}).analyze();observation.accessibility.push({name,violations:result.violations.map(({id,impact,help,nodes})=>({id,impact,help,nodes:nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});}
try{
  let existing=false;try{await fetch(base,{signal:AbortSignal.timeout(1000)});existing=true;}catch{}
  assert.equal(existing,false,'The QA origin must be idle before this test owns it.');
  const log=openSync(path.join(out,'launcher.log'),'w');
  server=spawn('./bin/casepath',['dev'],{cwd:root,env:process.env,stdio:['ignore',log,log],detached:true});closeSync(log);
  let ready=false;
  for(let i=0;i<120;i++){try{const r=await fetch(base+'/readyz',{signal:AbortSignal.timeout(1000)});if(r.ok){ready=true;break;}}catch{}if(server.exitCode!==null)throw new Error('Launcher stopped: '+server.exitCode);await delay(1000);}
  check('Pinned deterministic product becomes ready',ready);
  const health=await json('/healthz');observation.health=health;check('Reference mode',health.model_mode==='deterministic_reference');
  browser=await chromium.launch({headless:true});observation.browser=browser.version();
  context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1,reducedMotion:'reduce'});
  const page=await context.newPage();
  page.on('pageerror',e=>observation.page_errors.push(String(e)));
  page.on('console',m=>{if(m.type()==='error')observation.console_errors.push(m.text());});
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.locator('.cp-claims-table tbody tr').first().waitFor({timeout:60000});
  check('All 150 claims are visible in the verified overview',(await page.locator('#cwTotal').innerText()).trim()==='150');
  await snapshot(page,'01-queue-desktop');await axe(page,'queue-desktop');
  await snapshot(page,'02-queue-mobile',390,844);await axe(page,'queue-mobile');
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(base+'/#claim='+claim,{waitUntil:'domcontentloaded'});
  await page.locator('#cwStart').waitFor({timeout:60000});
  await page.waitForFunction(()=>document.querySelector('#cwStart')?.textContent.includes('Start agent review'));
  await snapshot(page,'03-claim-before-desktop');await axe(page,'claim-before-desktop');
  await snapshot(page,'04-claim-before-mobile',390,844);
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('#cwStart').click();
  await page.locator('#awClaimWork[data-status="completed"]').waitFor({timeout:90000});
  const runId=await page.locator('#awClaimWork').getAttribute('data-aw-run-id');observation.run_id=runId;
  check('A persisted six-role review completes',Boolean(runId));
  await page.locator('#cwLoopWorkbench[data-outcome]').waitFor({timeout:30000});
  await snapshot(page,'05-reviewed-desktop');await axe(page,'reviewed-desktop');
  await snapshot(page,'06-reviewed-mobile',390,844);await axe(page,'reviewed-mobile');
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('#cpTab-process').click();
  await snapshot(page,'07-process-desktop');
  await page.locator('#cpTab-evidence').click();
  await snapshot(page,'08-evidence-desktop');
  const why=page.locator('#cpPanel-evidence [data-evidence-source]').first();
  if(await why.count()){await why.click();await snapshot(page,'09-evidence-why-desktop');}
  await page.locator('[data-aw-timeline]').first().click();
  await snapshot(page,'10-agent-review-desktop');
  await snapshot(page,'11-agent-review-mobile',390,844);
  await page.reload({waitUntil:'domcontentloaded'});
  await page.locator('#awClaimWork[data-status="completed"]').waitFor({timeout:30000});
  check('Reload resumes the same recorded work',(await page.locator('#awClaimWork').getAttribute('data-aw-run-id'))===runId);
  await snapshot(page,'12-reloaded-mobile',390,844);
  await page.goto(base+'/method.html',{waitUntil:'domcontentloaded'});await snapshot(page,'13-method-desktop');await axe(page,'method-desktop');await snapshot(page,'14-method-mobile',390,844);
  await page.goto(base+'/research.html',{waitUntil:'domcontentloaded'});await snapshot(page,'15-research-desktop');await axe(page,'research-desktop');await snapshot(page,'16-research-mobile',390,844);
  const ledger=await json('/api/model-ledger');observation.model_ledger=ledger;
  check('No provider call occurred',ledger.summary.network_calls===0&&ledger.items.length===0);
  check('No uncaught browser error',observation.page_errors.length===0);
  observation.status='baseline_captured';
}catch(error){observation.status='failed';observation.error=String(error.stack||error);process.exitCode=1;console.error(error);}
finally{
  await fs.writeFile(path.join(out,'observation.json'),JSON.stringify(observation,null,2)+'\n');
  console.log(JSON.stringify({status:observation.status,checks:observation.checks,screenshots:observation.screenshots.length,errors:observation.page_errors,accessibility:observation.accessibility.map(r=>({name:r.name,count:r.violations.length}))},null,2));
  if(browser)await browser.close();
  if(server&&server.exitCode===null){try{process.kill(-server.pid,'SIGINT');}catch{}await delay(1500);}
}
