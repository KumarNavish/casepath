// Record the actual sealed product at explicit 1/60-second clock times.
// Usage: node capture_film.mjs --out /durable/path/outside/the/repository
// --probe checks the complete pipeline on 120 frames without publishing files.
// --verify /path/to/film-receipt.json repeats every 60th raw frame independently.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {spawn,execFileSync} from 'node:child_process';
import {gunzipSync} from 'node:zlib';

const root=path.resolve(import.meta.dirname,'../..');
const require=createRequire(root+'/casepath-qa/package.json'),{chromium}=require('playwright');
const args=process.argv.slice(2),value=flag=>args.includes(flag)?args[args.indexOf(flag)+1]:null;
const probe=args.includes('--probe'),verifyPath=value('--verify');
const out=path.resolve(value('--out')||path.dirname(verifyPath||''));
assert.ok(value('--out')||verifyPath,'Pass an explicit durable output directory.');
assert.ok(out!==root&&!out.startsWith(root+path.sep),'The master stays outside Git.');
assert.equal(fs.existsSync(out+(verifyPath?'/repeat-receipt.json':'/film-receipt.json')),false,'Preserve previous receipts; use a fresh output directory.');
if(!verifyPath)assert.equal(fs.existsSync(out+'/frame-index.jsonl'),false,'Preserve previous captured frames; use a fresh output directory.');
const origin=process.env.CASEPATH_CAPTURE_ORIGIN||'http://127.0.0.1:4180';
assert.ok(['127.0.0.1','localhost'].includes(new URL(origin).hostname),'Capture is local only.');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const git=(...argv)=>execFileSync('git',argv,{cwd:root,encoding:'utf8'}).trim();
const sourceCommit=git('rev-parse','HEAD');
assert.equal(git('diff','--name-only','HEAD','--','casepath','casepath-api','casepath-qa','docs','examples'),'','Seal product changes before capture.');
assert.equal(git('status','--porcelain','--untracked-files=all','--','casepath','casepath-api','casepath-qa','docs','examples'),'','Include all product source in the seal.');
assert.equal(fs.readFileSync(import.meta.filename,'utf8'),execFileSync('git',['show',sourceCommit+':design-plans/w9-20261021/capture_film.mjs'],{cwd:root,encoding:'utf8'}),'Commit the recorder before capture.');
const deployment=await(await fetch(origin+'/deployment.json')).json();
assert.equal(deployment.source_commit,sourceCommit,'Serve the exact capture commit.');
const wirePath=root+'/casepath-qa/fixtures/presentation-v1.json.gz';
const tracePath=root+'/casepath-qa/fixtures/desk-v3.json.gz';
const wire=JSON.parse(gunzipSync(fs.readFileSync(wirePath))).responses;
const recorded=JSON.parse(gunzipSync(fs.readFileSync(tracePath)));
const assets={};
for(const name of ['autonomous-workspace-v1.js','autonomous-workspace-v1.css','autonomous-presentation-v1.js','autonomous-language-v1.js','fonts/Mulish.ttf']){
  const response=await fetch(origin+'/assets/'+name);assert.equal(response.status,200);
  const bytes=Buffer.from(await response.arrayBuffer());assert.deepEqual(bytes,fs.readFileSync(root+'/casepath/assets/'+name));assets[name]=sha(bytes);
}
const report={sourceCommit,deployment,assets,sourceManifestSha256:sha(fs.readFileSync(root+'/casepath/source-manifest.json')),fixtures:{responses:sha(fs.readFileSync(wirePath)),operations:sha(fs.readFileSync(tracePath))},viewport:{width:1440,height:900},deviceScaleFactor:2,fps:60,probe,errors:[],writes:[],missingReads:[],checksums:[],cleanup:[]};
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const context=await browser.newContext({viewport:report.viewport,deviceScaleFactor:2,serviceWorkers:'block',reducedMotion:'no-preference',timezoneId:'UTC',locale:'en-GB'});
const page=await context.newPage();report.browserVersion=browser.version();
page.on('pageerror',e=>report.errors.push(e.message));
page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());});
await page.route('**/*',route=>{
  const request=route.request(),url=new URL(request.url()),key=url.pathname+url.search;
  if(!['GET','HEAD'].includes(request.method())){report.writes.push(request.method()+' '+key);return route.abort();}
  if(url.origin!==origin){report.missingReads.push(url.origin+key);return route.abort();}
  if(url.pathname.startsWith('/api/')){
    const id=url.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1],record=id&&recorded.cases.find(row=>row.id===id);
    if(record)return route.fulfill({contentType:'application/x-ndjson',body:record.trace});
    if(wire[key])return route.fulfill({contentType:'application/json',body:JSON.stringify(wire[key])});
    report.missingReads.push(key);return route.abort();
  }
  return route.continue();
});
async function open(){
  await page.goto(origin+'/?present=1#autonomous/demonstration');
  await page.waitForFunction(()=>window.CasepathPresentation?.active,{},{timeout:90000});
  await page.evaluate(()=>document.fonts.ready);
  await page.evaluate(()=>CasepathPresentation.active.advanceTo(0));
}
async function sample(n){
  const state=await page.evaluate(n=>{
    const active=CasepathPresentation.active,time=n*1000/60;active.advanceTo(time);
    const host=document.querySelector('[data-au-view]'),beat=active.manifest.beats[Number(host.dataset.auPresentationBeat)];
    const visible=selector=>[...document.querySelectorAll(selector)].filter(el=>!el.closest('.au-executive-transition')&&el.getClientRects().length&&getComputedStyle(el).visibility!=='hidden');
    return {n,time,renderedTime:Number(host.dataset.auPresentationTime),act:beat.act,phase:beat.phase,view:beat.view||null,animations:document.getAnimations().length,pause:visible('[data-au-demo-stop]').map(el=>el.textContent),resume:visible('[data-au-demo-resume]').length,watch:visible('[data-au-desk-watch]').length,skip:visible('[data-au-operation-skip]').length,speed:document.querySelector('[data-au-film-speed]')?.textContent};
  },n);
  assert.equal(state.renderedTime,state.time);assert.equal(state.animations,0,'native animation at '+n);
  assert.deepEqual(state.pause,['Pause'],'playing transport at '+n);assert.equal(state.resume,0);assert.equal(state.watch,0);
  assert.equal(state.speed,state.act==='process'?'4×':'');
  if(['answer','cases'].includes(state.view))assert.equal(state.skip,0);
  return state;
}
async function command(executable,argv,log){
  fs.writeFileSync(log,JSON.stringify({executable,argv})+'\n');
  await new Promise((resolve,reject)=>{
    const fd=fs.openSync(log,'a'),child=spawn(executable,argv,{cwd:root,stdio:['ignore',fd,fd]});
    child.on('error',error=>{fs.closeSync(fd);reject(error);});
    child.on('exit',code=>{fs.closeSync(fd);code===0?resolve():reject(new Error(path.basename(executable)+' exited '+code+'; '+log));});
  });
}
let indexFd;
try{
  await open();report.timeline=await page.evaluate(()=>CasepathPresentation.active.manifest);
  const total=report.timeline.duration*60/1000;assert.ok(Number.isInteger(total));
  if(verifyPath){
    const original=JSON.parse(fs.readFileSync(verifyPath,'utf8'));assert.equal(original.sourceCommit,sourceCommit);assert.deepEqual(original.assets,assets);assert.deepEqual(original.fixtures,report.fixtures);
    for(const expected of original.checksums){await sample(expected.n);const actual=sha(await page.screenshot({type:'png'}));assert.equal(actual,expected.sha256,'independent repeat at frame '+expected.n);report.checksums.push({n:expected.n,time:expected.time,sha256:actual});}
    report.verifiedSamples=report.checksums.length;report.passed=true;
  }else{
    fs.mkdirSync(out,{recursive:true});assert.equal(fs.existsSync(out+'/frame-index.jsonl'),false,'Use a fresh output directory; preserve prior capture receipts.');
    fs.mkdirSync(out+'/frames');indexFd=fs.openSync(out+'/frame-index.jsonl','wx');
    report.frameCount=probe?Math.min(120,total):total;report.duration=report.frameCount/60;report.framesDirectory=out+'/frames';
    report.startedAt=new Date().toISOString();
    for(let n=0;n<report.frameCount;n++){
      const state=await sample(n),filename=`${out}/frames/frame-${String(n).padStart(6,'0')}.png`;
      const bytes=await page.screenshot({type:'png',path:filename}),hash=sha(bytes);
      const row={n:state.n,time:state.time,act:state.act,phase:state.phase,sha256:hash,animations:state.animations,transport:state.pause[0]};
      fs.writeSync(indexFd,JSON.stringify(row)+'\n');
      if(n%60===0)report.checksums.push({n,time:state.time,sha256:hash});
      if(n%300===0)console.log(JSON.stringify({captured:n+1,total:report.frameCount,clockMilliseconds:state.time}));
    }
    fs.closeSync(indexFd);indexFd=null;report.capturedAt=new Date().toISOString();
    const index=fs.readFileSync(out+'/frame-index.jsonl'),rows=index.toString().trim().split('\n').map(JSON.parse);
    assert.equal(rows.length,report.frameCount);for(const [n,row]of rows.entries()){assert.equal(row.n,n);assert.equal(row.time,n*1000/60);}
    report.frameIndexSha256=sha(index);report.droppedIndices=0;report.duplicateIndices=0;
    assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);assert.deepEqual(report.missingReads,[]);
    const ffmpeg=process.env.CASEPATH_FFMPEG||path.join(os.homedir(),'.local/bin/ffmpeg'),ffprobe=process.env.CASEPATH_FFPROBE||path.join(os.homedir(),'.local/bin/ffprobe');
    // These two half-second fades are the only edits. No frames are inserted,
    // removed, retimed, composited, captioned or narrated.
    const fade=`fade=t=in:st=0:d=0.5:color=white,fade=t=out:st=${report.duration-.5}:d=0.5:color=white`;
    const variants=[['master-2880x1800.mp4','scale=2880:1800',2880,1800],['casepath-executive-1920x1200.mp4','scale=1920:1200:flags=lanczos',1920,1200],['casepath-executive-1920x1080.mp4','scale=1728:1080:flags=lanczos,pad=1920:1080:96:0:color=white',1920,1080]];
    report.encodes=[];
    for(const [name,scale,width,height]of variants){
      const filename=out+'/'+name,argv=['-nostdin','-hide_banner','-loglevel','warning','-framerate','60','-start_number','0','-i',out+'/frames/frame-%06d.png','-frames:v',String(report.frameCount),'-vf',scale+','+fade,'-c:v','libx264','-preset','medium','-profile:v','high','-crf','16','-pix_fmt','yuv420p','-r','60','-an','-movflags','+faststart',filename];
      console.log(JSON.stringify({encoding:name}));await command(ffmpeg,argv,out+'/'+name+'.log');
      const info=JSON.parse(execFileSync(ffprobe,['-v','error','-show_streams','-show_format','-of','json',filename],{encoding:'utf8'}));
      assert.equal(info.streams.length,1);const stream=info.streams[0];assert.equal(stream.codec_name,'h264');assert.equal(stream.profile,'High');assert.equal(stream.pix_fmt,'yuv420p');assert.equal(stream.avg_frame_rate,'60/1');assert.equal(Number(stream.nb_frames),report.frameCount);assert.equal(stream.width,width);assert.equal(stream.height,height);assert.equal(Number(stream.duration)*60,report.frameCount);
      const bytes=fs.statSync(filename).size;if(name==='casepath-executive-1920x1200.mp4')assert.ok(bytes<=60000000,'16:10 film exceeds 60 MB');
      report.encodes.push({name,width,height,bytes,sha256:sha(fs.readFileSync(filename)),ffprobe:info});
    }
    if(!probe){
      const chosen=Array.from({length:24},(_,i)=>Math.round(i*(report.frameCount-1)/23));report.contactFrames=chosen.map(n=>({n,time:n/60,act:rows[n].act}));
      fs.mkdirSync(out+'/contact');const select=chosen.map(n=>`eq(n,${n})`).join('+');
      await command(ffmpeg,['-nostdin','-hide_banner','-loglevel','warning','-i',out+'/casepath-executive-1920x1200.mp4','-vf',`select='${select}'`,'-fps_mode','vfr',out+'/contact/frame-%02d.png'],out+'/contact.log');
      fs.writeFileSync(out+'/contact-frames.json',JSON.stringify({frames:report.contactFrames,acts:report.timeline.acts},null,2));
      await command(root+'/.runtime/casepath-dev-v2/venv/bin/python',[root+'/design-plans/w9-20261021/make_contact_sheet.py',out],out+'/contact-sheet.log');
    }
    report.passed=true;
  }
}catch(error){report.failure=String(error.stack||error);console.error(report.failure);}
finally{
  if(indexFd!==undefined&&indexFd!==null)fs.closeSync(indexFd);
  for(const [name,close]of [['page',()=>page.close()],['context',()=>context.close()],['browser',()=>browser.close()]]){
    let timer;const status=await Promise.race([close().then(()=> 'closed',e=>'error: '+e.message),new Promise(resolve=>{timer=setTimeout(()=>resolve('timedOut'),10000);})]);clearTimeout(timer);report.cleanup.push({name,status});
  }
  fs.mkdirSync(out,{recursive:true});fs.writeFileSync(out+(verifyPath?'/repeat-receipt.json':'/film-receipt.json'),JSON.stringify(report,null,2)+'\n');
}
console.log(JSON.stringify({passed:report.passed,sourceCommit,frameCount:report.frameCount,verifiedSamples:report.verifiedSamples,out,failure:report.failure}));
process.exit(report.passed?0:1);
