// Compare live mid-motion frames with the corresponding raw film frames at DPR 2.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {gunzipSync} from 'node:zlib';
const root=path.resolve(import.meta.dirname,'../..'),require=createRequire(root+'/casepath-qa/package.json');
const {chromium}=require('playwright'),args=process.argv.slice(2),value=flag=>args[args.indexOf(flag)+1];
assert.ok(args.includes('--receipt')&&args.includes('--out'),'Pass --receipt and --out.');
const film=JSON.parse(fs.readFileSync(value('--receipt'),'utf8')),out=path.resolve(value('--out'));
assert.equal(film.passed,true);assert.equal(film.probe,false);fs.mkdirSync(out,{recursive:false});
const head=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();assert.equal(head,film.sourceCommit);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex'),origin='http://127.0.0.1:4180';
const wireBytes=fs.readFileSync(root+'/casepath-qa/fixtures/presentation-v1.json.gz'),traceBytes=fs.readFileSync(root+'/casepath-qa/fixtures/desk-v3.json.gz');
assert.equal(sha(wireBytes),film.fixtures.responses);assert.equal(sha(traceBytes),film.fixtures.operations);
const wire=JSON.parse(gunzipSync(wireBytes)).responses,recorded=JSON.parse(gunzipSync(traceBytes));
const report={sourceCommit:head,viewport:film.viewport,deviceScaleFactor:2,comparisons:[],errors:[],writes:[],missingReads:[],cleanup:[]};
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const context=await browser.newContext({viewport:film.viewport,deviceScaleFactor:2,serviceWorkers:'block',reducedMotion:'no-preference',timezoneId:'UTC',locale:'en-GB'}),page=await context.newPage();
page.on('pageerror',e=>report.errors.push(e.message));
page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());});
await page.route('**/*',route=>{
  const q=route.request(),u=new URL(q.url()),key=u.pathname+u.search;
  if(!['GET','HEAD'].includes(q.method())){report.writes.push(q.method()+' '+key);return route.abort();}
  if(u.origin!==origin){report.missingReads.push(u.origin+key);return route.abort();}
  if(u.pathname.startsWith('/api/')){
    const id=u.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1],record=id&&recorded.cases.find(row=>row.id===id);
    if(record)return route.fulfill({contentType:'application/x-ndjson',body:record.trace});
    if(wire[key])return route.fulfill({contentType:'application/json',body:JSON.stringify(wire[key])});
    report.missingReads.push(key);return route.abort();
  }
  return route.continue();
});
async function open(){await page.goto(origin+'/?present=1#autonomous/demonstration');await page.waitForFunction(()=>window.CasepathPresentation?.active,{},{timeout:90000});await page.evaluate(()=>document.fonts.ready);await page.evaluate(()=>CasepathPresentation.active.advanceTo(0));}
try{
  assert.equal(browser.version(),film.browserVersion);report.browserVersion=browser.version();
  const deployment=await(await fetch(origin+'/deployment.json')).json();assert.equal(deployment.source_commit,head);report.deployment=deployment;
  for(const [name,hash]of Object.entries(film.assets)){const bytes=Buffer.from(await(await fetch(origin+'/assets/'+name)).arrayBuffer());assert.equal(sha(bytes),hash,name);}
  await open();
  for(const act of film.timeline.acts){
    const beat=film.timeline.beats.find(b=>b.act===act.id&&b.motion&&b.phase!=='act-transition');
    const n=Math.round((beat.start+beat.duration/2)*60/1000),time=n*1000/60;
    await page.evaluate(({start,time})=>{CasepathPresentation.active.advanceTo(start);CasepathPresentation.active.freezeAt(time);},{start:beat.start,time});
    await page.waitForFunction(time=>CasepathPresentation.active.externallyDriven&&CasepathPresentation.active.time===time,time);
    assert.equal(await page.evaluate(()=>document.getAnimations().length),0);
    assert.equal(await page.locator('[data-au-demo-stop]').textContent(),'Pause');
    const live=await page.screenshot({type:'png',path:out+'/live-'+act.id+'.png'}),captured=fs.readFileSync(film.framesDirectory+`/frame-${String(n).padStart(6,'0')}.png`);
    const metrics=JSON.parse(execFileSync(root+'/.runtime/casepath-dev-v2/venv/bin/python',['-c',`from PIL import Image,ImageChops
import json,sys
x=Image.open(sys.argv[1]).convert('RGB');y=Image.open(sys.argv[2]).convert('RGB')
assert x.size==y.size
h=ImageChops.difference(x,y).histogram()
s=sum((i%256)*v for i,v in enumerate(h));m=max(i%256 for i,v in enumerate(h) if v)
print(json.dumps({'meanPixelDifference':s/(x.width*x.height*3),'maxChannelDifference':m}))`,out+'/live-'+act.id+'.png',film.framesDirectory+`/frame-${String(n).padStart(6,'0')}.png`],{encoding:'utf8'}));
    const comparison={act:act.id,n,time,liveSha256:sha(live),filmFrameSha256:sha(captured),byteIdentical:sha(live)===sha(captured),...metrics};report.comparisons.push(comparison);console.log(JSON.stringify(comparison));
    // Quantify renderer rounding separately from the exact clock/state checks.
    // At most one 8-bit channel value is allowed; all measured differences are
    // retained for the planner's review, never described as pixel-identical.
    assert.ok(metrics.maxChannelDifference<=1,'live / raw film differs beyond one channel value: '+act.id);
  }
  await open();
  await page.evaluate(()=>{const active=CasepathPresentation.active;active.seek(0);window.__filmLive={frames:0,animations:0,deltas:[],last:null};const sample=now=>{const r=window.__filmLive;r.frames++;r.animations=Math.max(r.animations,document.getAnimations().length);if(r.last!==null)r.deltas.push(now-r.last);r.last=now;if(active.time<active.manifest.duration)requestAnimationFrame(sample);};requestAnimationFrame(sample);active.resume();});
  await page.waitForFunction(()=>CasepathPresentation.active.time>=CasepathPresentation.active.manifest.duration,{},{timeout:120000});
  report.live=await page.evaluate(()=>{const r=window.__filmLive,s=r.deltas.toSorted((a,b)=>a-b);return {observedFrames:r.frames,maxNativeAnimations:r.animations,p50:s[Math.floor(s.length*.5)],p95:s[Math.floor(s.length*.95)],p99:s[Math.floor(s.length*.99)],max:s.at(-1),intervalsOver34ms:r.deltas.filter(ms=>ms>34).length};});
  assert.equal(report.live.maxNativeAnimations,0);assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);assert.deepEqual(report.missingReads,[]);report.passed=true;
}catch(error){report.failure=String(error.stack||error);console.error(report.failure);}
finally{for(const [name,close]of [['page',()=>page.close()],['context',()=>context.close()],['browser',()=>browser.close()]]){let timer;const status=await Promise.race([close().then(()=> 'closed',e=>'error: '+e.message),new Promise(resolve=>{timer=setTimeout(()=>resolve('timedOut'),10000);})]);clearTimeout(timer);report.cleanup.push({name,status});}fs.writeFileSync(out+'/live-film-receipt.json',JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify({passed:report.passed,comparisons:report.comparisons.length,live:report.live,failure:report.failure}));process.exit(report.passed?0:1);
