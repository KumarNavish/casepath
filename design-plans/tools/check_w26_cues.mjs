// Local deterministic desktop evidence: one full case, timed cue frames and read-only checks.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const {chromium}=createRequire(new URL('../../casepath-qa/package.json',import.meta.url))('playwright');
const [,,out,...pairs]=process.argv,overrides=Object.fromEntries(pairs.map(p=>p.split('=')));
const base=process.env.BASE || 'http://127.0.0.1:4180';
fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM});
const context=await browser.newContext({viewport:{width:1440,height:900},recordVideo:{dir:`${out}/video`,size:{width:1440,height:900}}});
const page=await context.newPage(),errors=[],writes=[],operations=new Map(),reads=new Set();
page.on('pageerror',e=>errors.push(e.message));
page.on('response',response=>{
 if(response.url().includes('/operations?') && response.status()===200)reads.add(response.url());
});
async function routes(page){await page.route('**/*',route=>{
 const request=route.request(),name=new URL(request.url()).pathname.split('/').pop();
 if(!['GET','HEAD'].includes(request.method())){writes.push(request.url());return route.abort();}
 return overrides[name]?route.fulfill({path:overrides[name],contentType:name.endsWith('.css')?'text/css':'text/javascript'}):route.continue();
});}
const instrument=()=>{
 window.__cueRuns=[];window.__cueActive=0;window.__cueMax=0;window.__threadHits=[];window.__threadCount=0;window.__needed=new Set();window.__received=new Set();
 new MutationObserver(()=>{for(const slot of document.querySelectorAll('[data-au-stage-document]')){if(slot.querySelector('.au-document-needed'))window.__needed.add(slot.dataset.auStageDocument);if(slot.dataset.auDocumentChecked==='true')window.__received.add(slot.dataset.auStageDocument);}}).observe(document,{childList:true,subtree:true,attributes:true,attributeFilter:['data-au-document-checked']});
 if(document.startViewTransition){const start=document.startViewTransition.bind(document);document.startViewTransition=function(update){
  const owner=document.querySelector('[data-au-cue-active]'),record={name:owner?.dataset.auCueActive,kind:owner?.dataset.auCueKind,id:owner?.dataset.auCueOperation,duration:300,target:'native-view-transition'};
  const transition=start(update);transition.ready.then(()=>{record.time=performance.now();window.__cueRuns.push(record);window.__cueMax=Math.max(window.__cueMax,++window.__cueActive);});transition.finished.then(()=>{record.finished=performance.now();window.__cueActive--;});return transition;
 };}

 const animate=Element.prototype.animate;
 Element.prototype.animate=function(frames,options){
  const animation=animate.call(this,frames,options),owner=document.querySelector('[data-au-cue-active]');
  if(owner){
   if(owner.dataset.auCueActive==='thread'){
    window.__threadCount++;const matrix=this.getScreenCTM(),length=this.getTotalLength(),titles=[...document.querySelectorAll('.au-node-title')].map(el=>({text:el.textContent,rect:el.getBoundingClientRect()}));
    for(let at=0;at<=length;at+=1){const point=this.getPointAtLength(at).matrixTransform(matrix);for(const title of titles)if(point.x>=title.rect.left-.5&&point.x<=title.rect.right+.5&&point.y>=title.rect.top-.5&&point.y<=title.rect.bottom+.5)window.__threadHits.push({title:title.text,x:point.x,y:point.y});}
   }
   const record={name:owner.dataset.auCueActive,kind:owner.dataset.auCueKind,id:owner.dataset.auCueOperation,time:performance.now(),duration:options.duration,target:this.className?.baseVal ?? this.className};window.__cueRuns.push(record);window.__cueMax=Math.max(window.__cueMax,++window.__cueActive);animation.finished.then(()=>{record.finished=performance.now();window.__cueActive--;},()=>{record.cancelled=performance.now();window.__cueActive--;});}
  return animation;
 };
};
await page.addInitScript(instrument);await routes(page);
const frames={},capture=await context.newCDPSession(page);
try{
 await page.goto(base+'/#autonomous/demonstration');
 for(const [name,cue] of [['fact-landing','landing'],['step-completion','completion'],['answer-arrival','answer-crossfade']]){
  await page.waitForFunction(cue=>window.__cueRuns.some(row=>row.name===cue),cue,{timeout:120000});
  const started=Date.now();frames[name]=[];fs.mkdirSync(`${out}/${name}`,{recursive:true});
  for(let index=0;index<8;index++){
   const wait=started+120*index-Date.now();if(wait>0)await page.waitForTimeout(wait);
   frames[name].push({index,time:await page.evaluate(()=>performance.now())});
   const shot=await capture.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(`${out}/${name}/${index}.png`,Buffer.from(shot.data,'base64'));
  }
 }
 const contrast=await page.evaluate(()=>{
  const rgba=value=>(value.match(/[\d.]+/g)||[]).map(Number),lum=rgb=>rgb.slice(0,3).map(c=>{c/=255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4;}).reduce((sum,c,i)=>sum+c*[.2126,.7152,.0722][i],0);
  return [...document.querySelectorAll('.au-node-title,.au-stage-fact,.au-stage-source-name,.au-stage-source-check,.au-demo-transport')].filter(el=>el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true})).map(el=>{
   const style=getComputedStyle(el),chain=[];let opacity=1;for(let node=el;node;node=node.parentElement){chain.unshift(getComputedStyle(node));opacity*=+getComputedStyle(node).opacity;}
   let background=[255,255,255];for(const css of chain){const c=rgba(css.backgroundColor),alpha=c[3]??1;background=background.map((v,i)=>(c[i]||0)*alpha+v*(1-alpha));}
   const text=rgba(style.color),a=lum(text),b=lum(background);return {text:el.textContent.trim().slice(0,70),fontSize:parseFloat(style.fontSize),opacity,foreground:style.color,background,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
  });
 });
 assert.ok(contrast.length>0);for(const row of contrast){assert.ok(row.ratio>=4.5,`text contrast ${row.ratio}: ${row.text}`);assert.ok(row.fontSize>=15);assert.equal(row.opacity,1);}
 await page.waitForSelector('[data-au-demo-position="2"]',{timeout:120000});
 const cues=await page.evaluate(()=>({runs:window.__cueRuns,maxConcurrent:window.__cueMax,threadSamples:window.__threadCount,threadTitleHits:window.__threadHits,needed:[...window.__needed],received:[...window.__received]}));
 // Chromium may discard completed streaming bodies after replay. Re-read the
 // observed loopback URLs with GET, after capture, to verify cue trigger IDs.
 for(const url of reads){const response=await fetch(url);assert.ok(response.ok);for(const line of (await response.text()).split('\n').filter(Boolean)){const row=JSON.parse(line);if(row.type==='operation')operations.set(row.id,row);}}
 fs.writeFileSync(`${out}/diagnostics.json`,JSON.stringify({frames,cues,contrast,recordedOperations:operations.size,errors,writes},null,2)+'\n');
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
 assert.ok(cues.threadSamples>0);assert.deepEqual(cues.threadTitleHits,[],'thread never crosses step titles');
 assert.ok(cues.needed.some(type=>cues.received.includes(type)),'active document goes from Needed to Received');
 assert.equal(cues.maxConcurrent,1,'only one scripted cue animates at a time');
 for(const run of cues.runs){assert.equal(operations.get(run.id)?.kind,run.kind,`${run.name}: recorded trigger`);assert.ok(!run.cancelled,`${run.name} unexpectedly cancelled`);}
 for(const cue of ['reading','thread','landing','document','completion','connector','progress','answer','reuse'])assert.ok(cues.runs.some(row=>row.name===cue),`missing ${cue}`);
 const video=page.video();await context.close();await video.saveAs(`${out}/full-case.webm`);
 const reduced=await browser.newContext({viewport:{width:1440,height:900},reducedMotion:'reduce'}),quiet=await reduced.newPage();
 quiet.on('pageerror',e=>errors.push(e.message));await quiet.addInitScript(instrument);await routes(quiet);
 await quiet.goto(base+'/#autonomous/demonstration');await quiet.waitForSelector('[data-au-demo-transport]',{timeout:60000});await quiet.waitForTimeout(3000);
 assert.equal(await quiet.evaluate(()=>window.__cueRuns.length),0,'reduced motion runs no cues');
 await quiet.screenshot({path:`${out}/reduced-motion.png`});await reduced.close();
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
 fs.writeFileSync(`${out}/cues.json`,JSON.stringify({status:'passed',viewport:{width:1440,height:900},frames,cues,contrast,recordedOperations:operations.size,reducedMotionCues:0,errors,writes},null,2)+'\n');
 console.log('Recorded cues, single motion, full case and reduced motion passed');
}finally{await context.close();await browser.close();}
