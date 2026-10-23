const proofOrigin=process.env.CASEPATH_PROOF_ORIGIN||'http://127.0.0.1:4180';
if(!['127.0.0.1','localhost'].includes(new URL(proofOrigin).hostname))throw new Error('Proof origin must be local.');
import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import {gunzipSync} from 'node:zlib';
import assert from 'node:assert/strict';
import {audit} from '../tools/desktop_overlap_audit.mjs';
const require=createRequire(new URL('../../casepath-qa/package.json',import.meta.url)),{chromium}=require('playwright'),ui=require('../casepath/assets/autonomous-workspace-v1.js');
const root=path.resolve(import.meta.dirname,'../..'),fixture=JSON.parse(gunzipSync(fs.readFileSync(root+'/casepath-qa/fixtures/desk-v3.json.gz'))),row=fixture.cases[0],state=row.envelope.state;
const outDir=process.env.CASEPATH_PROOF_OUTPUT||import.meta.dirname;fs.mkdirSync(outDir,{recursive:true});
const report={viewport:{width:1440,height:900},errors:[],writes:[],staticPrefix:false,overrides:process.env.OVERRIDES==='1',case:row.id,liveLayout:true};
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}),p=await browser.newPage({viewport:report.viewport});p.on('pageerror',e=>report.errors.push(e.message));p.on('console',e=>{if(e.type()==='error')report.errors.push('console: '+e.text());});
await p.route('**/*',r=>{const q=r.request(),u=new URL(q.url()),id=u.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1];if(!['GET','HEAD'].includes(q.method())){report.writes.push(q.method()+' '+u.pathname);return r.abort();}if(id){const c=fixture.cases.find(c=>c.id===id);if(c)return r.fulfill({body:c.trace,contentType:'application/x-ndjson'});}const asset=u.pathname.split('/').pop();if(report.overrides&&['autonomous-workspace-v1.js','autonomous-workspace-v1.css','Mulish.ttf'].includes(asset))return r.fulfill({path:root+'/casepath/assets/'+(asset==='Mulish.ttf'?'fonts/':'')+asset,contentType:asset.endsWith('.css')?'text/css':asset.endsWith('.js')?'text/javascript':'font/ttf'});return r.continue();});
try{
 report.deployment=await(await fetch(proofOrigin+'/deployment.json')).json();
 report.cases=[];
 for(const [i,c]of fixture.cases.entries()){
  await p.goto(proofOrigin+'/#autonomous/claim/'+c.id,{waitUntil:'networkidle'});await p.locator('[data-au-desk-watch]').waitFor({timeout:90000});await p.locator('[data-au-desk-watch]').click();await p.locator('[data-au-ns-start]').waitFor({timeout:90000});await p.locator('[data-au-ns-start]').click();
  const frames=[];
  for(const [name,cue]of [['selected','passage-rest'],['fact','fact-rest']]){
   await p.waitForFunction(cue=>document.querySelector('[data-au-view]')?.dataset.auCueActive===cue,cue,{timeout:90000});
   const check=await p.evaluate(()=>{
    const desk=document.querySelector('[data-au-ns]'),node=desk.querySelector('[data-state=building]'),circle=node.querySelector('.au-ns-building-ring circle'),label=node.querySelector('.au-ns-node-label'),current=desk.querySelector('[data-au-ns-plan-current]'),link=desk.querySelector('.au-ns-fact-connector'),facts=[...desk.querySelectorAll('[data-au-ns-fact]')].filter(el=>getComputedStyle(el).visibility!=='hidden'),last=facts.at(-1),reading=desk.querySelector('.au-ns-canvas').getBoundingClientRect(),path=link?.querySelector('path').getAttribute('d');
    const cards=facts.map(el=>({height:el.getBoundingClientRect().height,label:el.querySelector('[data-au-ns-fact-label]')?.textContent,type:el.querySelector('[data-au-ns-fact-type]')?.dataset.auNsFactType,citation:JSON.parse(el.dataset.auCitation),labelFits:!el.querySelector('[data-au-ns-fact-label]')||el.querySelector('[data-au-ns-fact-label]').scrollHeight<=el.querySelector('[data-au-ns-fact-label]').clientHeight+1,quote:el.querySelector('[data-au-ns-fact-quote]')?.textContent}));
    const planRows=[...desk.querySelectorAll('[data-au-ns-plan-row]')].map(row=>{const bar=row.querySelector('.au-ns-plan-progress');return {operations:JSON.parse(row.dataset.auNsPlanOperations),state:row.dataset.state,current:row.hasAttribute('data-au-ns-plan-current'),hidden:row.hidden,progress:bar?parseFloat(getComputedStyle(bar).getPropertyValue('--au-plan-progress')):null};});
    return {cue:document.querySelector('[data-au-view]').dataset.auCueActive,cueOperation:document.querySelector('[data-au-view]').dataset.auCueOperation,planRows,operation:desk.dataset.auNsOperation,node:node.dataset.auNsNode,title:desk.querySelector('[data-au-ns-plan] h2').textContent,dash:getComputedStyle(circle).strokeDasharray,width:getComputedStyle(circle).strokeWidth,color:getComputedStyle(circle).stroke,labelColor:getComputedStyle(label).color,planState:current.dataset.state,visibleFacts:facts.length,connectorVisible:Boolean(link&&getComputedStyle(link).visibility!=='hidden'),connectorX:path?+path.match(/^M([\d.]+)/)[1]:null,lastCardX:last?last.getBoundingClientRect().right-reading.left:null,cards,animations:document.getAnimations().filter(a=>a.playState==='running').length};
   });
   assert.equal(check.dash,'2.5px, 2.5px');assert.equal(check.width,'1.5px');assert.equal(check.color,'rgb(196, 197, 198)');assert.equal(check.labelColor,'rgb(156, 155, 160)');assert.equal(check.cue,cue);assert.equal(check.cueOperation,check.operation);assert.equal(check.animations,0);assert.ok(check.title.includes(ui.northStarQuestion(c.envelope.state.graph.nodes.find(n=>n.node_id===check.node))));
   if(name==='selected'){assert.equal(check.visibleFacts,0);assert.equal(check.connectorVisible,false);}else{assert.ok(check.visibleFacts>0);assert.equal(check.connectorVisible,true);assert.ok(Math.abs(check.connectorX-check.lastCardX)<=1);assert.equal(new Set(check.cards.map(c=>c.height)).size,1);assert.ok(check.cards.every(c=>c.labelFits));const ops=c.trace.trim().split('\n').map(JSON.parse),op=ops.find(o=>o.id===check.operation),key=op.input.document_type||op.object.id.replace(/^fact:/,''),label=ui.NS_FACT_TYPES[key];assert.ok(label);assert.equal(check.cards.at(-1).label,label);assert.equal(check.cards.at(-1).type,key);assert.deepEqual(check.cards.at(-1).citation,op.source);}
   const rows=c.trace.trim().split('\n').map(JSON.parse).filter(o=>o.type==='operation'),op=rows.find(o=>o.id===check.operation),catalogue=ui.northStarPlanModel(c.envelope.state,rows),groups=ui.northStarPlanGroups(catalogue.plans.get(check.node));assert.ok(op);assert.equal(check.planRows.length,groups.length);
   // Fact-rest starts after the exact operation settles. A group with future
   // operations waits; it must not keep spinning between recorded operations.
   for(const [index,group]of groups.entries()){
    const actual=check.planRows[index],ids=group.operations.map(o=>o.id),current=ids.includes(op.id),completed=group.operations.filter(o=>o.seq<op.seq||cue==='fact-rest'&&o.id===op.id).length,expected=completed===ids.length?'done':cue==='passage-rest'&&current?'active':'waiting';
    assert.deepEqual(actual.operations,ids);assert.equal(actual.current,current);assert.equal(actual.state,expected,`${c.id} ${cue} ${group.label}`);
    if(expected==='active'){assert.equal(actual.hidden,false);assert.notEqual(actual.progress,null);}
    if(actual.progress!==null)assert.equal(actual.progress,100*completed/ids.length);
   }
   const active=check.planRows.filter(row=>row.state==='active');assert.ok(active.length<=1);assert.equal(active.length,cue==='passage-rest'?1:0);assert.ok(active.every(row=>row.current&&row.operations.includes(op.id)));
   console.log('Live phase',c.id,cue,JSON.stringify({operation:op.id,currentState:check.planState,activeRows:active.length}));
   const overlaps=(await p.evaluate(audit)).filter(hit=>!hit.some(v=>typeof v==='string'&&v.startsWith('au-ns-role-badge ')));assert.deepEqual(overlaps,[]);frames.push({name,overlapCount:overlaps.length,...check});
  }
  // All recorded extraction types have W10 glossary entries. Preserve the
  // unknown-type fallback check in a temporary DOM probe, without changing
  // any source, operation, case state or API response.
  const sourceQuote=await p.locator('[data-au-ns-quote]').textContent();
  const fallbackHTML=ui.northStarFactCopy({}, {object:{id:'unrecognized-verifier-type'},input:{},source:{quote:sourceQuote}});
  const quote=await p.evaluate(html=>{const probe=document.createElement('button');probe.className='au-ns-fact';probe.style.cssText='position:fixed;left:-10000px;top:0';probe.innerHTML=html;document.querySelector('.au-workspace').appendChild(probe);try{const text=probe.querySelector('[data-au-ns-fact-quote]'),copy=probe.querySelector('.au-ns-fact-quotation');return {text:text.textContent,title:copy.title,clamp:getComputedStyle(copy).webkitLineClamp,overflow:getComputedStyle(copy).overflowY};}finally{probe.remove();}},fallbackHTML);
  assert.equal(quote.text,sourceQuote);assert.equal(quote.title,sourceQuote);assert.equal(quote.clamp,'3');assert.equal(quote.overflow,'hidden');
  const quoteOverlaps=(await p.evaluate(audit)).filter(hit=>!hit.some(v=>typeof v==='string'&&v.startsWith('au-ns-role-badge ')));assert.deepEqual(quoteOverlaps,[]);
  frames.push({name:'unknown-type-fallback-diagnostic',overlapCount:quoteOverlaps.length,fullQuote:true,temporaryDOMProbe:true,doesNotRepresentRecordedOperation:true});
  await p.locator('[data-au-demo-stop]').click();report.cases.push({id:c.id,frames,overlapCount:frames.reduce((n,f)=>n+f.overlapCount,0)});console.log('Live layout',i+1);
 }
 assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);report.passed=true;
}finally{
 report.cleanup=[];
 try{await p.unrouteAll({behavior:'ignoreErrors'});}catch(error){report.passed=false;report.cleanup.push({name:'routes',status:'failed',error:String(error)});}
 for(const [name,close]of [['page',()=>p.close()],['context',()=>p.context().close()],['browser',()=>browser.close()]]){
  const start=Date.now();try{await close();report.cleanup.push({name,status:'closed',ms:Date.now()-start});}catch(error){report.passed=false;report.cleanup.push({name,status:'failed',error:String(error)});}
 }
 fs.writeFileSync(outDir+'/live-layout-receipt.json',JSON.stringify(report,null,2));
 if(report.cleanup.some(row=>row.status==='failed'))throw new Error('Browser cleanup failed; see original receipt');
}
console.log(JSON.stringify({passed:report.passed,cases:report.cases?.length}));
