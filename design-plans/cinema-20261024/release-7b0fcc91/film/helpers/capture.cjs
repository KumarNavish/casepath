'use strict';
(async function captureCinema(){
  const fs=require('node:fs'),path=require('node:path'),{createHash}=require('node:crypto'),{gunzipSync}=require('node:zlib'),{spawn,execFileSync}=require('node:child_process'),{once}=require('node:events'),assert=require('node:assert/strict');
  const args=process.argv.slice(2),arg=k=>args.includes(k)?args[args.indexOf(k)+1]:null,root=path.resolve(arg('--root')||process.cwd()),out=arg('--out'),url=arg('--url'),film=args.includes('--film'),fps=30;
  assert(out&&path.isAbsolute(out)&&!fs.existsSync(out),'Use a new absolute output directory.');
  const {chromium}=require(process.env.CASEPATH_PLAYWRIGHT_MODULE||'/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-sites-hosting-20261009/casepath-qa/node_modules/playwright');
  const ffmpeg='/Users/kumar0002/.local/bin/ffmpeg',ffprobe='/Users/kumar0002/.local/bin/ffprobe',hash=b=>createHash('sha256').update(b).digest('hex');
  const files=['autonomous-language-v1.js','autonomous-presentation-v1.js','autonomous-workspace-v1.js','autonomous-workspace-v1.css'],assets=Object.fromEntries(files.map(n=>[n,fs.readFileSync(path.join(root,'casepath/assets',n))]));
  const sourceCommit=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();
  fs.mkdirSync(out,{recursive:true});fs.mkdirSync(out+'/contact');fs.mkdirSync(out+'/scenes');
  const report={contract:'casepath.cinema-capture/1',started_at:new Date().toISOString(),source_commit:sourceCommit,asset_sha256:Object.fromEntries(Object.entries(assets).map(([n,b])=>[n,hash(b)])),mode:url?'deployed_read_only_replay':'recorded_fixture_replay',url:url||null,new_inference:false,writes:[],edge_beacons:[],unexpected_destinations:[],browser_errors:[],viewport:{width:1600,height:900},device_scale:1.2,output:{width:1920,height:1080},fps,frames:[],scenes:[]};
  let browser,context,page,encoder,encoderLog,frameIndex;
  try{
    browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
    context=await browser.newContext({viewport:report.viewport,deviceScaleFactor:1.2,serviceWorkers:'block',reducedMotion:'no-preference',locale:'en-GB',timezoneId:'UTC'});page=await context.newPage();
    page.on('pageerror',e=>report.browser_errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error')report.browser_errors.push(m.text());});
    if(url){
      const siteOrigin=new URL(url).origin,allowed=new Set([siteOrigin,'https://casepath-agent.fastapicloud.dev']);
      const edgeChallengePrefix='/cdn-cgi/challenge-platform/h/b/jsd/oneshot/';
      report.request_policy={application_methods:['GET','HEAD'],edge_exception:{origin:siteOrigin,method:'POST',pathname_prefix:edgeChallengePrefix}};
      await page.route('**/*',route=>{
        const r=route.request(),u=new URL(r.url()),method=r.method();
        // The prior actual public run recorded this same-origin hosting challenge.
        // Keep an explicit record without opaque challenge tokens, bodies or headers.
        if(method==='POST'&&u.origin===siteOrigin&&u.pathname.startsWith(edgeChallengePrefix)){
          report.edge_beacons.push({method,origin:u.origin,pathname_prefix:edgeChallengePrefix,pathname_sha256:hash(Buffer.from(u.pathname)),classification:'same_origin_edge_challenge',action:'continued'});
          return route.continue();
        }
        if(!['GET','HEAD'].includes(method)){report.writes.push(method+' '+u.pathname);return route.abort();}
        if(!allowed.has(u.origin)){report.unexpected_destinations.push(u.origin+u.pathname);return route.abort();}
        return route.continue();
      });
      const health=await context.request.get('https://casepath-agent.fastapicloud.dev/healthz');assert(health.ok());report.health=await health.json();
      const expected=arg('--expected-source');assert(expected&&report.health.source_commit===expected&&report.health.read_only===true&&report.health.writable===false,'Expected read-only deployment identity required.');
      const deployment=await context.request.get(new URL('/deployment.json',url).href);assert(deployment.ok());report.deployment=await deployment.json();assert.equal(report.deployment.source_commit,expected);assert.equal(sourceCommit,expected);
    }else{
      const fixtureNames=['presentation-v1','desk-v3'],fixture=Object.fromEntries(fixtureNames.map(n=>[n,fs.readFileSync(path.join(root,'casepath-qa/fixtures',n+'.json.gz'))]));
      report.fixture_sha256=Object.fromEntries(Object.entries(fixture).map(([n,b])=>[n,hash(b)]));
      const wire=JSON.parse(gunzipSync(fixture['presentation-v1'])).responses,records=JSON.parse(gunzipSync(fixture['desk-v3'])).cases;
      await page.route('**/*',route=>{
        const r=route.request(),u=new URL(r.url()),key=u.pathname+u.search;
        if(!['GET','HEAD'].includes(r.method())){report.writes.push(r.method()+' '+key);return route.abort();}
        if(r.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0"><main id="workspace"></main></body></html>'});
        if(/\/fonts\/[^/]+\.ttf$/.test(u.pathname)){const n=path.basename(u.pathname),b=fs.readFileSync(path.join(root,'casepath/assets/fonts',n));report.font_sha256={...report.font_sha256,[n]:hash(b)};return route.fulfill({contentType:'font/ttf',body:b});}
        const id=u.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1],record=id&&records.find(c=>c.id===id);
        if(record)return route.fulfill({contentType:'application/x-ndjson',body:record.trace});
        if(wire[key])return route.fulfill({contentType:'application/json',body:JSON.stringify(wire[key])});
        report.unexpected_destinations.push(key);return route.fulfill({status:404,contentType:'application/json',body:'{"detail":"No recorded fixture"}'});
      });
    }
    const opening=Date.now();await page.goto(url||'http://localhost:41999/?present=1#autonomous/demonstration',{waitUntil:'domcontentloaded',timeout:60000});
    if(!url){
      await page.addStyleTag({content:assets['autonomous-workspace-v1.css'].toString('utf8')});
      for(const n of files.filter(n=>n.endsWith('.js')))await page.addScriptTag({content:assets[n].toString('utf8')});
      await page.evaluate(()=>{window.product=CasePathAutonomous.mount(document.querySelector('#workspace'),{fetch:window.fetch.bind(window)});});
    }
    await page.waitForFunction(()=>window.CasepathPresentation?.active,null,{timeout:90000});await page.evaluate(()=>document.fonts.ready);report.admission_ms=Date.now()-opening;
    if(url){for(const n of files){const response=await context.request.get(new URL('/assets/'+n,url).href);assert(response.ok());assert.equal(hash(await response.body()),report.asset_sha256[n],'Deployed asset differs from sealed source: '+n);}}
    const sample=async at=>{const state=await page.evaluate(at=>{const a=CasepathPresentation.active;a.advanceTo(at);const h=document.querySelector('[data-au-view]');return {time:a.time,act:h.dataset.auPresentationAct,phase:h.dataset.auPresentationPhase,animations:document.getAnimations().length};},at);assert.equal(state.time,at);assert.equal(state.animations,0);return state;};
    await sample(0);report.timeline=await page.evaluate(()=>CasepathPresentation.active.manifest);fs.writeFileSync(out+'/timeline.json',JSON.stringify(report.timeline,null,2));
    const count=Math.ceil(report.timeline.duration*fps/1000);report.frame_count=count;report.duration=count/fps;
    const contacts=new Map(Array.from({length:24},(_,i)=>[Math.round(i*(count-1)/23),i+1]));
    const phases=new Set(['ready','customer-passage-rest','fact-rest','node-rest','overview','source-check-rest','law-rest','documents-rest','answer-rest','draft-rest','memory-overview','memory-notice-rest','case-list-rest','wordmark-rest']);
    for(const b of report.timeline.beats.filter(b=>phases.has(b.phase))){const at=b.end-1;await sample(at);const name=`scenes/${String(b.index).padStart(3,'0')}-${b.act}-${b.phase}.png`,bytes=await page.screenshot({type:'png',path:out+'/'+name});report.scenes.push({name,time:at,sha256:hash(bytes)});}
    let finished;
    if(film){
      encoderLog=fs.openSync(out+'/encode.log','wx');frameIndex=fs.openSync(out+'/frame-index.jsonl','wx');
      encoder=spawn(ffmpeg,['-nostdin','-hide_banner','-loglevel','warning','-f','image2pipe','-vcodec','png','-framerate',String(fps),'-i','pipe:0','-frames:v',String(count),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-an','-movflags','+faststart',out+'/CasePath_Cinematic_Demo_Silent.mp4'],{stdio:['pipe',encoderLog,encoderLog]});
      finished=once(encoder,'exit');encoder.stdin.on('error',()=>{});
    }
    for(const n of film?Array.from({length:count},(_,n)=>n):[...contacts.keys()]){
      const time=n*1000/fps,state=await sample(time),bytes=await page.screenshot({type:'png'});assert.equal(bytes.readUInt32BE(16),1920);assert.equal(bytes.readUInt32BE(20),1080);
      const row={n,time,act:state.act,phase:state.phase,sha256:hash(bytes)};
      if(film){fs.writeSync(frameIndex,JSON.stringify(row)+'\n');assert.equal(encoder.exitCode,null);if(!encoder.stdin.write(bytes))await once(encoder.stdin,'drain');}
      if(contacts.has(n)){const stem='contact/frame-'+String(contacts.get(n)).padStart(2,'0');fs.writeFileSync(out+'/'+stem+'.png',bytes);await page.screenshot({type:'jpeg',quality:78,path:out+'/'+stem+'.jpg'});report.frames.push({...row,file:stem+'.png',review_file:stem+'.jpg'});}
      if(film&&n%150===0)console.log(JSON.stringify({captured:n+1,total:count,seconds:time/1000}));
    }
    if(film){
      encoder.stdin.end();const [code]=await finished;assert.equal(code,0);fs.closeSync(frameIndex);frameIndex=null;fs.closeSync(encoderLog);encoderLog=null;
      const file=out+'/CasePath_Cinematic_Demo_Silent.mp4',probe=JSON.parse(execFileSync(ffprobe,['-v','error','-show_streams','-show_format','-of','json',file],{encoding:'utf8'})),v=probe.streams.find(s=>s.codec_type==='video');
      assert.equal(v.width,1920);assert.equal(v.height,1080);assert.equal(v.avg_frame_rate,'30/1');assert.equal(Number(v.nb_frames),count);
      report.video={file:path.basename(file),bytes:fs.statSync(file).size,sha256:hash(fs.readFileSync(file)),probe};report.frame_index_sha256=hash(fs.readFileSync(out+'/frame-index.jsonl'));
    }
    execFileSync(ffmpeg,['-nostdin','-hide_banner','-loglevel','warning','-framerate','1','-start_number','1','-i',out+'/contact/frame-%02d.png','-vf','scale=480:270,tile=4x6:padding=12:margin=12:color=0xF4F4F5','-frames:v','1',out+'/contact-sheet.png'],{stdio:['ignore','ignore','pipe']});
    for(const[n,b]of Object.entries(assets))assert.equal(hash(fs.readFileSync(path.join(root,'casepath/assets',n))),hash(b),'Source changed during capture');
    assert.deepEqual(report.writes,[]);assert.deepEqual(report.browser_errors,[]);assert.deepEqual(report.unexpected_destinations,[]);report.status='passed';
  }catch(error){report.status='failed';report.failure=String(error.stack||error);console.error(report.failure);}
  finally{
    if(encoder&&encoder.exitCode===null)encoder.kill('SIGTERM');if(frameIndex)fs.closeSync(frameIndex);if(encoderLog)fs.closeSync(encoderLog);
    if(browser)await browser.close();report.finished_at=new Date().toISOString();fs.writeFileSync(out+'/capture-receipt.json',JSON.stringify(report,null,2)+'\n');
  }
  console.log(JSON.stringify({status:report.status,out,duration:report.duration,frames:report.frame_count,admission_ms:report.admission_ms,failure:report.failure}));process.exit(report.status==='passed'?0:1);
})().catch(error=>{console.error(error.stack);process.exit(1);});
