import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';
import assert from 'node:assert/strict';
import {audit} from '../tools/desktop_overlap_audit.mjs';
const require=createRequire(new URL('../../casepath-qa/package.json',import.meta.url)),{chromium}=require('playwright'),ui=require('../casepath/assets/autonomous-workspace-v1.js');
const here=path.dirname(fileURLToPath(import.meta.url)),base='http://127.0.0.1:4180',fixture=JSON.parse(gunzipSync(fs.readFileSync(path.resolve(here,'../../casepath-qa/fixtures/desk-v3.json.gz'))));
const traces=new Map(fixture.cases.map(c=>[c.id,c.trace])),data=await(await fetch(base+'/api/claim-loops/v1/autonomous/knowledge')).json(),entries=ui.knowledgeLibrary(data);
const report={viewport:{width:1440,height:900},overrides:process.env.OVERRIDES==='1',domains:[],casesOpened:[],frames:{},errors:[],writes:[]};
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}),context=await browser.newContext({viewport:report.viewport}),p=await context.newPage();
p.on('pageerror',e=>report.errors.push(e.message));
await p.route('**/*',r=>{const q=r.request(),u=new URL(q.url());if(!['GET','HEAD'].includes(q.method())){report.writes.push(q.method()+' '+u.pathname);return r.abort();}const id=u.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1];if(traces.has(id))return r.fulfill({body:traces.get(id),contentType:'application/x-ndjson'});const asset=u.pathname.split('/').pop();if(report.overrides&&['autonomous-workspace-v1.js','autonomous-workspace-v1.css'].includes(asset))return r.fulfill({path:path.resolve(here,'../../casepath/assets',asset),contentType:asset.endsWith('.css')?'text/css':'text/javascript'});return r.continue();});
async function frame(name){await p.evaluate(()=>document.fonts.ready);await p.screenshot({path:path.join(here,name+'.png')});report.frames[name]={overlaps:await p.evaluate(audit),horizontalOverflow:await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth)};}
try{
 await p.goto(base+'/#autonomous/knowledge',{waitUntil:'networkidle'});await p.waitForSelector('[data-au-knowledge-checklist]');assert.equal(await p.locator('[data-au-library-entry]:visible').count(),1);
 for(const entry of entries){
  await p.locator(`[data-au-library-jump="${entry.family}"]`).click();const pane=p.locator(`[data-au-library-entry="${entry.family}"]`);await pane.waitFor({state:'visible'});assert.equal(await p.locator('[data-au-library-entry]:visible').count(),1);
  const v=entry.current,ids=ui.checklistCases(v,data);assert.equal(await pane.locator('.au-library-status').innerText(),`Used in ${ids.length} cases`);assert.deepEqual(await pane.locator('[data-au-checklist-step]').allTextContents(),ui.layoutGraph(v.graph).nodes.map(ui.deskStepLabel));
  for(const predicate of v.source_outcome.legal_predicates)assert.equal(await pane.locator(`[data-au-checklist-test="${predicate.predicate_id}"] .au-desk-law`).innerText(),ui.deskLaw(predicate.rule_refs));
  const noVerdicts=await pane.locator('[data-au-knowledge-checklist]').innerText();assert.doesNotMatch(noVerdicts,/All legal tests met|Does not meet|CHF/);
  await frame(entry.family);report.domains.push({family:entry.family,uses:ids.length,steps:v.graph.nodes.length,documents:v.graph.document_catalog.length,legalTests:v.source_outcome.legal_predicates.length});
  await p.reload({waitUntil:'networkidle'});await pane.waitFor({state:'visible'});assert.equal(await p.locator('[data-au-library-jump][aria-current=true]').getAttribute('data-au-library-jump'),entry.family);
  for(const id of ids){await pane.locator(`.au-checklist-cases [data-au-claim="${id}"]`).click();await p.waitForSelector('[data-au-desk-answer]');assert.equal(await p.locator('.au-desk-next-cue').innerText(),'✓');assert.equal(await p.locator('[data-au-desk-next]').getAttribute('data-status'),'clear');assert.ok(await p.locator('[data-au-desk-next]').evaluate(e=>e.getBoundingClientRect().height<30));if(report.casesOpened.length===0)await frame('next-action-and-law-order');report.casesOpened.push(id);await p.goBack();await pane.waitFor({state:'visible'});}
  await pane.locator('.au-checklist-records > summary').click();await pane.locator('.au-library-source').first().click();await p.locator('.au-source-dialog[open]').waitFor();await p.keyboard.press('Escape');await pane.locator('.au-checklist-records > summary').click();
 }
 await p.goto(base+'/#autonomous/claim/'+fixture.cases[0].id,{waitUntil:'networkidle'});await p.waitForSelector('[data-au-desk-answer]');
 await p.locator('[data-au-desk-draft]').click();await p.locator('[data-au-draft-edit]').click();await p.locator('[data-au-draft-body]').fill('My saved local copy.');await p.locator('[data-au-draft-save]').click();assert.equal(await p.locator('[data-au-draft-status]').innerText(),'Your copy, saved on this device. Not sent — you decide.');await frame('draft-one-line');await p.keyboard.press('Escape');
 await p.locator('.au-identity-header [data-au-nav=work]').click();await p.waitForSelector('.au-request-row');assert.equal(await p.locator('[data-au-case-return]:visible').count(),0);await frame('cases-clean-header');report.cleanCasesHeader=true;report.singleDraftStatus=true;
 const gap={graph:{nodes:[{node_id:'lt_intake',label:'Read the termination documents'},{node_id:'lt_form',label:'Check the termination notice',depends_on:[]}]},outcome:{missing_evidence:[{document_type:'termination_notice',label:'Termination notice',node_ids:['lt_form'],reason:'Check whether the notice uses the required form.'}]}};
 const gapMarkup=ui.deskNextStepMarkup(gap);await p.evaluate(html=>{const host=document.querySelector('[data-au-view-state]');host.innerHTML='<section style="max-width:720px;margin:64px auto"><h1>Missing document</h1><p style="color:#666">UI fixture · no saved case has been changed</p>'+html+'</section>';},gapMarkup);assert.match(await p.locator('[data-au-desk-next]').innerText(),/Needed for step 2:/);assert.match(await p.locator('[data-au-desk-next]').innerText(),/Who to ask is not on file/);await frame('missing-document-fixture');report.missingDocumentFixture=true;
 report.exactSourceInspection=true;report.reloadAndBack=true;
 const first=entries[0].current;await p.goto(`${base}/#autonomous/knowledge?knowledge=${encodeURIComponent(first.knowledge_id)}&version=999`,{waitUntil:'networkidle'});await p.waitForSelector('[data-au-library-unavailable]');assert.equal(await p.locator('[data-au-library-unavailable] [data-au-knowledge-checklist]').count(),0);report.unavailablePinTruthful=true;
 for(const f of Object.values(report.frames)){assert.deepEqual(f.overlaps,[]);assert.equal(f.horizontalOverflow,false);}assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);report.passed=true;
}finally{fs.writeFileSync(path.join(here,'browser-receipt.json'),JSON.stringify(report,null,2));await browser.close();}
console.log(JSON.stringify(report,null,2));
