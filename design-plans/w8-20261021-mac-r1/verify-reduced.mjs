import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import {gunzipSync} from 'node:zlib';
import assert from 'node:assert/strict';
import {audit} from '../tools/desktop_overlap_audit.mjs';
const require=createRequire(new URL('../../casepath-qa/package.json',import.meta.url)),{chromium}=require('playwright'),ui=require('../casepath/assets/autonomous-workspace-v1.js');
const root=path.resolve(import.meta.dirname,'../..'),fixture=JSON.parse(gunzipSync(fs.readFileSync(root+'/casepath-qa/fixtures/desk-v3.json.gz'))),row=fixture.cases[0],state=row.envelope.state;
const outDir=process.env.CASEPATH_PROOF_OUTPUT||import.meta.dirname;fs.mkdirSync(outDir,{recursive:true});
const report={viewport:{width:1440,height:900},errors:[],writes:[],staticPrefix:false,overrides:process.env.OVERRIDES==='1',case:row.id,reducedMotion:true};
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}),p=await browser.newPage({viewport:report.viewport,reducedMotion:'reduce'});p.on('pageerror',e=>report.errors.push(e.message));p.on('console',e=>{if(e.type()==='error')report.errors.push('console: '+e.text());});
await p.route('**/*',r=>{const q=r.request(),u=new URL(q.url()),id=u.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1];if(!['GET','HEAD'].includes(q.method())){report.writes.push(q.method()+' '+u.pathname);return r.abort();}if(id){const c=fixture.cases.find(c=>c.id===id);if(c)return r.fulfill({body:c.trace,contentType:'application/x-ndjson'});}const asset=u.pathname.split('/').pop();if(report.overrides&&['autonomous-workspace-v1.js','autonomous-workspace-v1.css','Mulish.ttf'].includes(asset))return r.fulfill({path:root+'/casepath/assets/'+(asset==='Mulish.ttf'?'fonts/':'')+asset,contentType:asset.endsWith('.css')?'text/css':asset.endsWith('.js')?'text/javascript':'font/ttf'});return r.continue();});
try{
 report.deployment=await(await fetch('http://127.0.0.1:4180/deployment.json')).json();
 await p.goto('http://127.0.0.1:4180/#autonomous/demonstration',{waitUntil:'networkidle'});await p.locator('[data-au-ns-start]').waitFor({timeout:90000});await p.locator('[data-au-ns-start]').click();await p.locator('[data-au-ns-completed]').waitFor({timeout:90000});await p.locator('.au-ns-tabs [data-au-ns-role=result]').click();await p.locator('[data-au-desk-answer]').waitFor();assert.equal(await p.evaluate(()=>document.getAnimations().filter(a=>a.playState==='running').length),0);assert.equal(await p.locator('.au-ns-cursor').count(),0);assert.equal(await p.locator('.au-ns-tabs [aria-current]').getAttribute('data-au-ns-role'),'result');assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);report.passed=true;
}finally{fs.writeFileSync(outDir+'/reduced-receipt.json',JSON.stringify(report,null,2));await p.unrouteAll({behavior:'ignoreErrors'});await browser.close();}
console.log(JSON.stringify(report));
