import fs from 'node:fs/promises';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
export async function run(page,dir) {
  await fs.mkdir(`${dir}/frames`,{recursive:true});
  await page.cdp('Emulation.setDeviceMetricsOverride',{width:1600,height:900,deviceScaleFactor:1.2,mobile:false});
  const frames=[],samples=[],events=[]; let pos={x:1515,y:840},running=true,error=null,drain;
  const event=(type,extra={})=>events.push({t:Date.now()/1000,type,...extra});
  const state=()=>page.evaluate(()=>{
    const rect=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};};
    const stage=document.querySelector('[data-au-operation-presentation]');
    return {t:Date.now()/1000,op:Number(document.querySelector('[data-au-operation-scrub]')?.value),state:stage?.dataset.auOperationPresentation,operation:stage?.dataset.auCurrentOperation,readheadRect:rect('.au-operation-attention'),factRect:rect('.au-operation-fact-token'),sourceRect:rect('.au-stage-source'),railRect:rect('.au-stage-process'),transportRect:rect('.au-stage-transport'),sourceTitle:document.querySelector('.au-stage-source-title')?.textContent,sourceText:document.querySelector('.au-operation-passage')?.textContent,checkedSlots:document.querySelectorAll('.au-stage-slot[data-au-document-checked=true]').length,dialog:!!document.querySelector('dialog[open]'),heading:document.querySelector('h1')?.textContent,outcome:document.querySelector('.au-stage-outcome')?.textContent,mode:document.querySelector('[data-au-operation-mode]')?.textContent,url:location.href};
  });
  const pointer=async(x,y,ms=650)=>{const from={...pos},start=Date.now();while(true){const p=Math.min(1,(Date.now()-start)/ms),q=p*p*(3-2*p);pos={x:from.x+(x-from.x)*q,y:from.y+(y-from.y)*q};await page.cdp('Input.dispatchMouseEvent',{type:'mouseMoved',...pos});event('ptr',pos);if(p>=1)break;await sleep(25);}};
  const click=async(selector,role)=>{const r=await page.evaluate(s=>{const e=document.querySelector(s);if(!e)throw Error('Missing click target '+s);const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};},selector);await pointer(r.x,r.y);event('click',{...pos,role});await page.cdp('Input.dispatchMouseEvent',{type:'mousePressed',...pos,button:'left',buttons:1,clickCount:1});await sleep(60);await page.cdp('Input.dispatchMouseEvent',{type:'mouseReleased',...pos,button:'left',buttons:0,clickCount:1});};
  const save=()=>fs.writeFile(`${dir}/capture.json`,JSON.stringify({source_commit:'7904c8050a10568d4168c92b77ee55ec1d7b2b13',viewport:{width:1600,height:900,deviceScaleFactor:1.2},frames,samples,events,error:error?.message||null}));
  await page.click('loc=css:[data-au-inspect="demo"]',{label:'Choose the first demonstration'});
  console.log(await page.snapshot());
  await page.events();
  await page.cdp('Page.startScreencast',{format:'jpeg',quality:83,maxWidth:1920,maxHeight:1080,everyNthFrame:2});
  const pump=(async()=>{try{while(running){for(const e of await page.events())if(e.method==='Page.screencastFrame'){const p=e.params,file=`frames/f${String(frames.length).padStart(6,'0')}.jpg`;await fs.writeFile(`${dir}/${file}`,Buffer.from(p.data,'base64'));frames.push({file,t:p.metadata.timestamp});await page.cdp('Page.screencastFrameAck',{sessionId:p.sessionId});}await sleep(8);}}catch(e){error=e;}})();
  try {
    await click('.au-demo-case-open[data-au-demo-case="clm_314f2d309fea25e6"]','choose-first-case');
    await pointer(1515,840,500);
    await page.waitForFunction(()=>document.querySelector('[data-au-operation-presentation]')?.dataset.auOperationPresentation==='playing'&&Number(document.querySelector('[data-au-operation-scrub]')?.value)<50,undefined,{timeout:30000});
    let first=null,inspected=false,completed=null,lastSave=0;
    const started=Date.now();
    while(Date.now()-started<300000){
      if(error)throw error;
      const s=await state();samples.push(s);
      if(s.railRect&&!first){first=s.t;event('film-start');}
      if(first&&!inspected&&s.checkedSlots>=1&&s.state==='playing'){
        inspected=true;event('inspection-start');await click('.au-stage-source-title','inspect-source');
        await page.waitForFunction(()=>document.querySelector('.au-source-body'),undefined,{timeout:30000});
        const held=await state();samples.push(held);event('inspection-held',{op:held.op});
        await sleep(2300);const after=await state();samples.push(after);
        if(after.state!=='paused'||after.op!==held.op)throw Error('Inspection did not hold playback');
        await click('[data-au-close]','close-source');await click('[data-au-demo-resume]','resume');event('resumed');
        await pointer(1515,840,700);
      }
      if(s.state==='completed'&&s.heading==='Repeated heating failure and reported repair calls'){
        completed=s;event('film-result',{op:s.op,checkedSlots:s.checkedSlots,outcome:s.outcome});
        await page.screenshot({path:`${dir}/result.png`,fullPage:true});await sleep(1200);break;
      }
      if(Date.now()-lastSave>6000){lastSave=Date.now();await save();console.log(JSON.stringify({elapsed:(Date.now()-started)/1000,frames:frames.length,op:s.op,state:s.state,slots:s.checkedSlots,source:s.sourceTitle}));}
      await sleep(130);
    }
    if(!inspected||!completed)throw Error('Capture did not reach both inspection and first outcome');
    event('film-end');
  }catch(e){error=e;throw e;}finally{running=false;await pump;await page.cdp('Page.stopScreencast');await save();console.log(JSON.stringify({frames:frames.length,samples:samples.length,error:error?.message||null}));}
}
