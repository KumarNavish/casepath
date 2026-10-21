import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';
import assert from 'node:assert/strict';
import {audit} from '../tools/desktop_overlap_audit.mjs';
const require=createRequire(new URL('../../casepath-qa/package.json',import.meta.url)),{chromium}=require('playwright');
const ui=require('../casepath/assets/autonomous-workspace-v1.js'),here=path.dirname(fileURLToPath(import.meta.url)),base='http://127.0.0.1:4180',api='/api/claim-loops/v1/autonomous';
const fixture=JSON.parse(gunzipSync(fs.readFileSync(path.resolve(here,'../../casepath-qa/fixtures/desk-v3.json.gz')))),traces=new Map(fixture.cases.map(c=>[c.id,c.trace]));
const catalog=await(await fetch(base+api+'/claims')).json();assert.equal(catalog.total,150);assert.equal(catalog.claims.filter(c=>c.customer_request).length,150);
const rows=new Map(catalog.claims.map(c=>[c.claim_id,c])),report={viewport:{width:1440,height:900},overrides:process.env.OVERRIDES==='1',requests:150,answers:[],frames:{},errors:[],writes:[]};
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}),context=await browser.newContext({viewport:report.viewport}),p=await context.newPage();
p.on('pageerror',e=>report.errors.push(e.message));
await p.route('**/*',r=>{const q=r.request(),u=new URL(q.url());if(!['GET','HEAD'].includes(q.method())){report.writes.push(q.method()+' '+u.pathname);return r.abort();}const id=u.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1];if(traces.has(id))return r.fulfill({body:traces.get(id),contentType:'application/x-ndjson'});const asset=u.pathname.split('/').pop();if(report.overrides&&['autonomous-workspace-v1.js','autonomous-workspace-v1.css'].includes(asset))return r.fulfill({path:path.resolve(here,'../../casepath/assets',asset),contentType:asset.endsWith('.css')?'text/css':'text/javascript'});return r.continue();});
async function frame(name){await p.evaluate(()=>document.fonts.ready);await p.screenshot({path:path.join(here,name+'.png')});report.frames[name]={overlaps:await p.evaluate(audit),horizontalOverflow:await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth)};}
async function waitRows(n){await p.waitForFunction(n=>document.querySelectorAll('.au-request-row').length===n,n);}
try{
 await p.goto(base+'/#autonomous/work',{waitUntil:'networkidle'});await waitRows(20);await frame('cases');
 assert.equal(await p.locator('[data-au-claim-row] .au-claim-status-word').first().innerText(),'Not started');
 await p.locator('[data-au-page="2"]').click();await p.waitForFunction(()=>document.querySelector('.au-pagination').textContent.includes('Page 2'));assert.equal(await p.locator('.au-request-row').count(),20);report.pagination=true;
 await p.locator('[data-au-filter=investigation_complete]').click();await waitRows(9);await frame('answers-ready');
 for(const item of fixture.cases){const r=p.locator(`[data-au-claim-row="${item.id}"]`);assert.equal(await r.locator('[data-au-customer-request]').innerText(),`“${rows.get(item.id).customer_request}”`);assert.equal(await r.locator('.au-claim-status-word').innerText(),'Answer ready');const failed=item.envelope.state.outcome.legal_predicates.filter(x=>x.status==='failed');for(const f of failed)assert.ok((await r.innerText()).includes(ui.deskLegalLabel(f.predicate_id)));}
 for(const domain of ui.DOMAINS){await p.locator(`[data-au-domain="${domain.id}"]`).click();await waitRows(3);const ids=await p.locator('[data-au-claim-row]').evaluateAll(es=>es.map(e=>e.dataset.auClaimRow));assert.ok(ids.every(id=>rows.get(id).browse_metadata.domain===domain.id));}report.domainFilters=true;
 await p.locator('[data-au-domain=all]').click();await waitRows(9);
 for(const item of fixture.cases){await p.locator(`[data-au-claim="${item.id}"]`).click();await p.waitForSelector('[data-au-desk-answer]');assert.equal(await p.locator('.au-desk-asks q').innerText(),rows.get(item.id).customer_request);report.answers.push(item.id);await p.goBack();await waitRows(9);}
 await p.locator('[data-au-claim-search]').fill('lasting repair');await waitRows(1);assert.equal(await p.locator('[data-au-claim-row]').getAttribute('data-au-claim-row'),fixture.cases[0].id);await frame('request-search');report.requestSearch=true;
 await p.reload({waitUntil:'networkidle'});await waitRows(1);assert.equal(await p.locator('[data-au-claim-search]').inputValue(),'lasting repair');report.reload=true;
 await p.locator('[data-au-claim-search]').fill('no such request 999999');await p.waitForFunction(()=>document.querySelector('.au-empty')?.textContent==='No cases match this search.');assert.match(await p.locator('.au-empty').innerText(),/No cases match/);report.emptySearch=true;
 for(const f of Object.values(report.frames)){assert.deepEqual(f.overlaps,[]);assert.equal(f.horizontalOverflow,false);}assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);report.passed=true;
}finally{fs.writeFileSync(path.join(here,'browser-receipt.json'),JSON.stringify(report,null,2));await browser.close();}
console.log(JSON.stringify(report,null,2));
