const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert/strict');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const b=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const p=await b.newPage({viewport:{width:1360,height:900}});await p.addInitScript(()=>{window.CASEPATH_PUBLIC_READ_ONLY=true;});await p.clock.install();
 const errors=[],writes=[],streamRequests=[],streamFinished=[];p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.method()!=='GET')writes.push({method:r.method(),url:r.url()});if(r.url().includes('/operations?'))streamRequests.push(r.url());});p.on('requestfinished',r=>{if(r.url().includes('/operations?'))streamFinished.push(r.url());});
 await p.goto('http://127.0.0.1:4189/?journey=autonomous#autonomous/demonstration');
 await p.evaluate(()=>{window.opFrames=[];let last='';new MutationObserver(()=>{const h=document.querySelector('[data-au-view]'),q=h?.querySelector('[data-au-revision]'),op=h?.dataset.auCurrentOperation,key=[location.hash,op,q?.dataset.auRevision].join('|');if(key!==last){last=key;window.opFrames.push({hash:location.hash,op,revision:q?.dataset.auRevision,sha:q?.dataset.auStateSha,markers:document.querySelectorAll('[data-au-operation-attention]').length,kind:document.querySelector('[data-au-operation-object]')?.dataset.auObjectType,empty:!q});}}).observe(document.querySelector('[data-au-view]'),{subtree:true,childList:true,attributes:true});});
 let sourceCaptured=false,extractCaptured=false,settledCaptured=false;
 for(let i=0;i<2500;i++){
  await p.clock.runFor(750);await pause(6);
  const status=await p.locator('[data-au-view]').evaluate(el=>({mode:el.dataset.auOperationPresentation,op:el.dataset.auCurrentOperation,revision:el.querySelector('[data-au-revision]')?.dataset.auRevision,text:el.textContent,hasMark:!!el.querySelector('[data-au-operation-span]'),claim:location.hash}));
  if(status.hasMark&&!sourceCaptured){await p.screenshot({path:'/workspace/op-browser/native-source.png'});sourceCaptured=true;console.log('source captured',i,status.revision);}
  if(status.text.includes('Provisional finding')&&!extractCaptured){await p.screenshot({path:'/workspace/op-browser/native-provisional.png'});extractCaptured=true;console.log('provisional captured',i,status.revision);}
  if(status.text.includes('Document requirements')&&Number(status.revision)>20&&!settledCaptured){await p.screenshot({path:'/workspace/op-browser/native-process-documents.png'});settledCaptured=true;}
  if(streamRequests.length===9&&status.mode==='completed'&&status.text.includes('Assessment complete')){console.log('completed nine',i);break;}
  if(i%200===0)console.log('tick',i,streamRequests.length,status.mode,status.revision);
  if(i===2499)throw Error('nine-case completion timeout: '+JSON.stringify(status));
 }
 const frames=await p.evaluate(()=>window.opFrames);fs.writeFileSync('/workspace/op-browser/nine-frames.json',JSON.stringify(frames,null,2));await p.screenshot({path:'/workspace/op-browser/native-final.png'});
 assert.equal(streamRequests.length,9);assert.equal(streamFinished.length,9);assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);assert.ok(frames.every(f=>f.markers<=1));assert.ok(frames.filter(f=>f.op).length>100);assert.equal(frames.filter(f=>f.empty).length,0,'no empty handoff');
 fs.writeFileSync('/workspace/op-browser/nine-result.json',JSON.stringify({streamRequests,streamFinished,errors,writes,frameCount:frames.length,sourceCaptured,extractCaptured,settledCaptured},null,2));
 await b.close();
})().catch(e=>{console.error(e);process.exit(1);});
