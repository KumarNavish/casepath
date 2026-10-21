import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';
import assert from 'node:assert/strict';
import {audit} from '../tools/desktop_overlap_audit.mjs';
const {chromium}=createRequire(new URL('../../casepath-qa/package.json',import.meta.url))('playwright');
const here=path.dirname(fileURLToPath(import.meta.url)),base=process.env.BASE||'http://127.0.0.1:4180';
const fixture=JSON.parse(gunzipSync(fs.readFileSync(path.resolve(here,'../../casepath-qa/fixtures/desk-v3.json.gz'))));
const first=fixture.cases[0],operations=new Map(first.trace.trim().split('\n').map(JSON.parse).filter(r=>r.type==='operation').map(r=>[r.id,r]));
const report={viewport:{width:1440,height:900},overrides:process.env.OVERRIDES==='1',errors:[],writes:[],frames:{}};
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const context=await browser.newContext({viewport:report.viewport,recordVideo:{dir:path.join(here,'video'),size:report.viewport}});
async function setup(page){
 page.on('pageerror',e=>report.errors.push(e.message));
 await page.route('**/*',r=>{const q=r.request(),u=new URL(q.url());if(!['GET','HEAD'].includes(q.method())){report.writes.push(q.method()+' '+u.pathname);return r.abort();}if(u.pathname.endsWith(`/${first.id}/operations`))return r.fulfill({body:first.trace,contentType:'application/x-ndjson'});const asset=u.pathname.split('/').pop();if(report.overrides&&['autonomous-workspace-v1.js','autonomous-workspace-v1.css'].includes(asset))return r.fulfill({path:path.resolve(here,'../../casepath/assets',asset),contentType:asset.endsWith('.css')?'text/css':'text/javascript'});return r.continue();});
 await page.addInitScript(()=>{
  window.__cues=[];window.__active=0;window.__max=0;window.__crossings=[];
  const animate=Element.prototype.animate;
  Element.prototype.animate=function(frames,options){const animation=animate.call(this,frames,options),owner=document.querySelector('[data-au-cue-active]');if(owner){const row={name:owner.dataset.auCueActive,id:owner.dataset.auCueOperation,kind:owner.dataset.auCueKind,start:performance.now(),duration:options.duration};window.__cues.push(row);window.__max=Math.max(window.__max,++window.__active);animation.finished.then(()=>{row.finished=performance.now();window.__active--;},()=>{row.cancelled=performance.now();window.__active--;});
   if(row.name==='thread'){
    const rects=[];const root=document.querySelector('.au-desk-grid'),walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    while(walker.nextNode()){const node=walker.currentNode,e=node.parentElement;if(!node.textContent.trim()||e.closest('svg,[hidden]')||!e.checkVisibility({checkVisibilityCSS:true,checkOpacity:true}))continue;const range=document.createRange();range.selectNodeContents(node);const clip=e.closest('.au-desk-source-scroll')?.getBoundingClientRect();for(const r of range.getClientRects()){if(r.width<2||r.height<2||clip&&(r.bottom<=clip.top||r.top>=clip.bottom))continue;rects.push({left:r.left,right:r.right,top:clip?Math.max(r.top,clip.top):r.top,bottom:clip?Math.min(r.bottom,clip.bottom):r.bottom,text:node.textContent.slice(0,50)});}}
    const matrix=this.getScreenCTM(),length=this.getTotalLength();for(let t=0;t<=length;t+=2){const p=this.getPointAtLength(t).matrixTransform(matrix);for(const r of rects)if(p.x>r.left+1&&p.x<r.right-1&&p.y>r.top+1&&p.y<r.bottom-1)window.__crossings.push({text:r.text,x:p.x,y:p.y,operation:row.id});}
   }
  }return animation;};
 });
}
try{
 const p=await context.newPage();await setup(p);await p.goto(`${base}/#autonomous/claim/${first.id}`,{waitUntil:'networkidle'});await p.waitForFunction(()=>document.querySelector('[data-au-desk-metric=rules] .au-desk-number')?.textContent==='692');await p.locator('[data-au-desk-watch]').click();await p.waitForSelector('[data-au-demo-stop]');
 await p.waitForSelector('.au-desk-thread',{timeout:60000});await p.waitForTimeout(300);await p.screenshot({path:path.join(here,'mid-work-thread.png')});report.frames.work={overlaps:await p.evaluate(audit)};
 await p.waitForSelector('[data-au-desk-answer]',{timeout:180000});await p.waitForTimeout(700);await p.screenshot({path:path.join(here,'case1-answer-motion.png')});report.frames.answer={overlaps:await p.evaluate(audit)};
 report.cues=await p.evaluate(()=>({runs:window.__cues,maxConcurrent:window.__max,textCrossings:window.__crossings}));
 for(const run of report.cues.runs)assert.equal(operations.get(run.id)?.kind,run.kind,`${run.name} has an actual trace trigger`);
 for(const cue of ['reading','thread','landing','node-build','node-arrival','completion','connector','reuse','answer'])assert.ok(report.cues.runs.some(row=>row.name===cue),`missing ${cue}`);
 assert.deepEqual(report.cues.textCrossings,[],'evidence lines stay outside all visible text');assert.equal(report.cues.maxConcurrent,1);
 const video=p.video();await context.close();await video.saveAs(path.join(here,'case1.webm'));
 const c=await browser.newContext({viewport:report.viewport}),q=await c.newPage();await setup(q);await q.goto(`${base}/#autonomous/claim/${first.id}`,{waitUntil:'networkidle'});await q.waitForFunction(()=>document.querySelector('[data-au-desk-metric=rules] .au-desk-number')?.textContent==='692');await q.locator('[data-au-desk-watch]').click();await q.waitForSelector('.au-desk-thread',{timeout:60000});await q.locator('[data-au-demo-stop]').click();const paused=await q.locator('.au-agent-desk').innerText();await q.waitForTimeout(700);assert.equal(await q.locator('.au-agent-desk').innerText(),paused);assert.equal(await q.evaluate(()=>document.getAnimations().length),0);await q.locator('[data-au-demo-resume]').click();await q.locator('[data-au-operation-skip]').click();await q.waitForSelector('[data-au-desk-answer]');assert.equal(await q.locator('[data-au-demo-position]').getAttribute('data-au-demo-position'),'1');report.pauseResumeSkip=true;await c.close();
 for(const [name,frame] of Object.entries(report.frames))assert.deepEqual(frame.overlaps,[],`${name} has no overlapping content`);assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);report.passed=true;
}finally{fs.writeFileSync(path.join(here,'motion-receipt.json'),JSON.stringify(report,null,2));await context.close();await browser.close();}
console.log(JSON.stringify({passed:report.passed,runs:report.cues.runs.length,maxConcurrent:report.cues.maxConcurrent,textCrossings:report.cues.textCrossings.length,frames:report.frames,pauseResumeSkip:report.pauseResumeSkip}));
