// Local deterministic GET-only desk verification. OVERRIDES=1 reads working assets.
import {createRequire} from 'node:module';
import fs from 'node:fs';
import {gzipSync,gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const require=createRequire(new URL('../../casepath-qa/package.json',import.meta.url));
const {chromium}=require('playwright'),ui=require('../casepath/assets/autonomous-workspace-v1.js');
const here=path.dirname(fileURLToPath(import.meta.url)),base=process.env.BASE||'http://127.0.0.1:4180',api='/api/claim-loops/v1/autonomous';
const fixturePath=path.join(here,'desk-fixtures.json.gz');
if(process.argv.includes('--capture-fixtures')){
 const cases=[];
 for(const row of ui.REFERENCE_DEMO_CASES){
  const stateResponse=await fetch(`${base}${api}/claims/${row.claim_id}`);assert.ok(stateResponse.ok);
  const envelope=await stateResponse.json();
  const response=await fetch(`${base}${api}/claims/${row.claim_id}/operations?mode=live`);assert.equal(response.status,200,'respect the local read limit; retry later if it is exhausted');
  cases.push({id:row.claim_id,envelope,trace:await response.text()});console.log('Captured',row.claim_id);
 }
 fs.writeFileSync(fixturePath,gzipSync(JSON.stringify({captured_at:new Date().toISOString(),origin:base,method:'GET only; deterministic reconstruction',cases}),{level:9}));
 process.exit(0);
}
const fixture=JSON.parse(gunzipSync(fs.readFileSync(fixturePath))),report={viewport:{width:1440,height:900},overrides:process.env.OVERRIDES==='1',fixtureSha256:createHash('sha256').update(fs.readFileSync(fixturePath)).digest('hex'),cases:[],frames:{},interactions:{},errors:[],writes:[]};
const byId=new Map(fixture.cases.map(row=>[row.id,row]));
import {audit} from '../tools/desktop_overlap_audit.mjs';
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
async function makePage(reduced=false){
 const context=await browser.newContext({viewport:report.viewport,reducedMotion:reduced?'reduce':'no-preference',acceptDownloads:true});
 const page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
 await page.route('**/*',r=>{const q=r.request(),u=new URL(q.url());if(!['GET','HEAD'].includes(q.method())){report.writes.push(q.method()+' '+u.pathname);return r.abort();}const id=u.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1];if(id&&byId.has(id))return r.fulfill({body:byId.get(id).trace,contentType:'application/x-ndjson'});const asset=u.pathname.split('/').pop();if(report.overrides&&['autonomous-workspace-v1.js','autonomous-workspace-v1.css'].includes(asset))return r.fulfill({path:path.resolve(here,'../../casepath/assets',asset),contentType:asset.endsWith('.css')?'text/css':'text/javascript'});return r.continue();});return page;
}
async function open(page,id){await page.goto(`${base}/#autonomous/claim/${id}`,{waitUntil:'networkidle'});await page.waitForFunction(()=>document.querySelector('[data-au-desk-metric=rules] .au-desk-number')?.textContent!=='—'&&!!document.querySelector('[data-au-desk-answer]'));}
async function frame(page,name){await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:path.join(here,`${name}.png`)});report.frames[name]={overlaps:await page.evaluate(audit),horizontalOverflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),whiteSurfaces:await page.evaluate(()=>['.au-workspace','.au-identity-header','.au-desk-footer','.au-desk-answer','.au-desk-source'].map(s=>document.querySelector(s)).filter(Boolean).map(e=>({selector:e.className,color:getComputedStyle(e).backgroundColor})))};}
try{
 const p=await makePage();
 for(const [i,row]of fixture.cases.entries()){
  await open(p,row.id);const state=row.envelope.state,ops=row.trace.trim().split('\n').map(JSON.parse).filter(r=>r.type==='operation'),groups=new Map(state.source_descriptors.map(s=>[s.artifact_id,`${s.role}:${s.file_name}`]));
  const expected={documents:String(new Set(ops.filter(r=>r.kind==='span.read').map(r=>groups.get(r.source?.artifact_id||r.object.id)).filter(Boolean)).size),facts:String(ops.filter(r=>r.kind==='fact.extract'&&r.source&&r.result?.verification_required!==false).length),rules:String(ops.filter(r=>['condition.evaluate','node.evaluate','dependency.evaluate','process.inspect','document.require'].includes(r.kind)).length),met:`${new Set(ops.filter(r=>r.kind==='step.complete'&&r.result?.status==='completed'&&state.graph.nodes.some(n=>n.node_id===r.object.id)).map(r=>r.object.id)).size}/${state.graph.nodes.length}`};
  const actual=await p.locator('[data-au-desk-metric]').evaluateAll(els=>Object.fromEntries(els.map(e=>[e.dataset.auDeskMetric,e.querySelector('.au-desk-number').textContent])));assert.deepEqual(actual,expected);
  const legal=await p.locator('[data-au-legal-label]').evaluateAll(els=>els.map(e=>({id:e.dataset.auLegalLabel,label:e.textContent})));for(const row of legal)assert.equal(row.label,ui.deskLegalLabel(row.id));
  assert.equal(await p.locator('[data-au-desk-file-state=read]').count(),4);assert.equal(await p.locator('.au-desk-test-status').innerText(),ui.deskLegalStatus(state.outcome.legal_predicates).label);
  report.cases.push({id:row.id,stateSha256:state.state_sha256,counts:actual,legalLabels:legal.length});console.log('Verified case',i+1);
  if(i===0||i===3)await frame(p,`case${i+1}-answer`);
 }
 const first=fixture.cases[0];await open(p,first.id);
 await p.locator('[data-au-desk-draft]').click();await p.locator('[data-au-draft-edit]').click();await p.locator('[data-au-draft-subject]').fill('My local review');await p.locator('[data-au-draft-body]').fill('A draft kept on this device.');await p.locator('[data-au-draft-save]').click();assert.equal(await p.locator('[data-au-draft-status]').innerText(),'Saved on this device.');await p.locator('[data-au-close-record]').click();await p.reload({waitUntil:'networkidle'});await p.locator('[data-au-desk-draft]').click();await p.waitForSelector('[data-au-draft-edit]');assert.match(await p.locator('.au-desk-draft').innerText(),/My local review/);
 await p.evaluate(()=>{window.__copied=null;Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>window.__copied=text},configurable:true});});await p.locator('[data-au-draft-copy]').click();assert.equal(await p.evaluate(()=>window.__copied),'My local review\n\nA draft kept on this device.');
 const downloaded=p.waitForEvent('download');await p.locator('[data-au-draft-download]').click();const download=await downloaded;assert.equal(fs.readFileSync(await download.path(),'utf8'),'My local review\n\nA draft kept on this device.');await p.locator('[data-au-draft-original]').click();assert.match(await p.locator('.au-record-body').innerText(),/The sources support/);await p.locator('[data-au-close-record]').click();
 await open(p,fixture.cases[3].id);await p.locator('[data-au-desk-draft]').click();assert.doesNotMatch(await p.locator('.au-desk-draft').innerText(),/My local review/);await p.locator('[data-au-close-record]').click();await p.locator('[data-au-desk-predicate-source=canton_approved_form]').first().click();assert.equal(await p.locator('[data-au-desk-quote]').innerText(),'It was a plain letter, not a canton-approved termination form.');assert.match(await p.locator('.au-desk-landing').innerText(),/^Does not meet/);
 await p.locator('.au-desk-source-name').click();await p.locator('.au-source-dialog[open]').waitFor();await p.keyboard.press('Escape');
 report.interactions={localDraftPersists:true,copy:true,download:true,originalRetained:true,otherCaseIsolated:true,failedLegalExactPassage:true,sourceViewer:true};
 await open(p,fixture.cases[7].id);await p.locator('[data-au-desk-document-select]').first().click();await p.waitForSelector('[data-au-desk-quote]');const quote=await p.locator('[data-au-desk-quote]').innerText();await p.reload({waitUntil:'networkidle'});await p.waitForSelector('[data-au-desk-quote]');assert.equal(await p.locator('[data-au-desk-quote]').innerText(),quote);await frame(p,'rent-step-selected');report.interactions.selectedDocumentReload=true;
 await p.close();const reduced=await makePage(true);await reduced.goto(`${base}/#autonomous/demonstration`,{waitUntil:'networkidle'});await reduced.waitForSelector('[data-au-desk-answer]',{timeout:60000});assert.equal(await reduced.evaluate(()=>document.getAnimations().length),0);assert.equal(await reduced.locator('.au-desk-thread').count(),0);report.interactions.reducedMotionStill=true;await reduced.close();
 assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);report.passed=true;
}finally{fs.writeFileSync(path.join(here,'verification-receipt.json'),JSON.stringify(report,null,2));await browser.close();}
console.log(JSON.stringify(report,null,2));
