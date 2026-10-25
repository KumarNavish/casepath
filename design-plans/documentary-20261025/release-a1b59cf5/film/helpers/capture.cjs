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
    // Diagnose the rendered documentary, not just its timeline or CSS strings.
    // All probes use the product's clock and return it to the opening afterward.
    // They initiate no product action, model request, or application write.
    {
      const diagnosticDir=path.join(out,'documentary-diagnostics');fs.mkdirSync(diagnosticDir);
      const diagnostic={contract:'casepath.documentary-motion-focus/1',status:'running',
        source_commit:sourceCommit,ring_samples:[],guidance:[],failed_predicates:[],
        subjective_motion_or_audio_review:false};
      report.documentary_diagnostics=diagnostic;
      const ringBeat=report.timeline.beats.find(b=>b.act==='reading'&&b.phase==='passage-rest'&&b.duration>=1800);
      assert(ringBeat,'A settled active-ring beat must be present.');
      const t1=ringBeat.start+500,t2=t1+600;
      assert(t2<ringBeat.end-300,'Quarter-cycle probes must stay inside one settled beat.');
      const rounded=n=>Math.round(n*1e6)/1e6;
      const expectedTransform=at=>`rotate(${rounded((at%2400)*.15)}deg)`;
      async function ringState(){
        return page.evaluate(()=>{
          const a=CasepathPresentation.active,rings=[...document.querySelectorAll('.au-ns-building-ring')];
          const ring=rings.find(el=>el.getClientRects().length),circle=ring?.closest('.au-ns-circle'),number=circle?.querySelector('.au-ns-current-number');
          const rect=circle?.getBoundingClientRect(),style=ring&&getComputedStyle(ring);
          return {time:a.time,paused:a.paused,visible_rings:rings.filter(el=>el.getClientRects().length).length,
            transform:ring?.style.transform,computed_transform:style?.transform,
            stroke_dasharray:ring?.querySelector('circle')?getComputedStyle(ring.querySelector('circle')).strokeDasharray:null,
            number:number?.textContent,number_transform:number&&getComputedStyle(number).transform,
            circle_transform:circle&&getComputedStyle(circle).transform,
            viewport:{width:innerWidth,height:innerHeight},
            circle:rect?{x:rect.x,y:rect.y,width:rect.width,height:rect.height}:null,
            animations:document.getAnimations().length};
        });
      }
      async function ringImage(label){
        const state=await ringState();assert.equal(state.visible_rings,1,label+': exactly one visible active ring');
        assert(state.circle&&state.circle.width>10&&state.circle.height>10,label+': ring has visible geometry');
        assert.equal(state.animations,0,label+': no independent browser animation clock');
        assert.equal(state.number_transform,'none',label+': step number remains upright');
        assert.equal(state.circle_transform,'none',label+': the enclosing circle does not rotate');
        const x=Math.max(0,Math.floor(state.circle.x)-4),y=Math.max(0,Math.floor(state.circle.y)-4);
        const right=Math.min(state.viewport.width,Math.ceil(state.circle.x+state.circle.width)+4),bottom=Math.min(state.viewport.height,Math.ceil(state.circle.y+state.circle.height)+4);
        const clip={x,y,width:right-x,height:bottom-y},name='documentary-diagnostics/'+label+'.png';
        const bytes=await page.screenshot({type:'png',clip,path:out+'/'+name});
        const row={label,...state,clip,file:name,sha256:hash(bytes),bytes:bytes.length};
        diagnostic.ring_samples.push(row);return row;
      }
      await sample(t1);const first=await ringImage('ring-quarter-a');
      await sample(t2);const second=await ringImage('ring-quarter-b');
      assert.equal(first.transform,expectedTransform(t1));assert.equal(second.transform,expectedTransform(t2));
      assert.deepEqual(first.clip,second.clip,'Motion probes must compare the same visible crop.');
      assert.equal(first.number,second.number,'The step number is semantic content, not moving decoration.');
      assert.notEqual(first.sha256,second.sha256,'Actual rendered ring pixels must move over a quarter-cycle.');

      await page.evaluate(at=>CasepathPresentation.active.seek(at),t2);
      const pauseBefore=await ringImage('ring-paused-before');await page.waitForTimeout(120);
      const pauseAfter=await ringImage('ring-paused-after');
      assert(pauseBefore.paused&&pauseAfter.paused,'The real product pause must be active.');
      assert.equal(pauseBefore.time,t2);assert.equal(pauseAfter.time,t2);
      assert.equal(pauseBefore.sha256,pauseAfter.sha256,'Rendered ring pixels must stay fixed on pause.');

      await page.evaluate(()=>CasepathPresentation.active.resume());await page.waitForTimeout(120);
      await page.evaluate(()=>CasepathPresentation.active.pause());
      const resumed=await ringImage('ring-resumed');
      assert(resumed.time>t2&&resumed.time<ringBeat.end,'The real live clock must advance within the same beat.');
      assert.notEqual(resumed.sha256,pauseAfter.sha256,'Live playback must visibly advance the ring.');

      await sample(report.timeline.duration-1);await sample(t2);
      const reseek=await ringImage('ring-reseek');
      assert.equal(reseek.sha256,second.sha256,'Seeking away and back must reproduce the same visible ring phase.');
      await page.emulateMedia({reducedMotion:'reduce'});
      await sample(t1);const reducedFirst=await ringImage('ring-reduced-a');
      await sample(t2);const reducedSecond=await ringImage('ring-reduced-b');
      assert.equal(reducedFirst.transform,'rotate(0deg)');assert.equal(reducedSecond.transform,'rotate(0deg)');
      assert.equal(reducedFirst.sha256,reducedSecond.sha256,'Reduced motion must not rotate the rendered ring.');
      await page.emulateMedia({reducedMotion:'no-preference'});
      diagnostic.motion={period_ms:2400,quarter_cycle_ms:600,rendered_pixels_changed:true,
        live_resume_pixels_changed:true,pause_pixels_unchanged:true,reseek_pixels_identical:true,
        reduced_motion_pixels_unchanged:true,step_number_unchanged:true};

      for(const beat of report.timeline.beats.filter(b=>!b.phase.endsWith('transition'))){
        await sample(beat.end-1);
        const row=await page.evaluate(()=>{
          const guide=document.querySelector('.au-documentary-guide'),rail=guide?.querySelector('.au-doc-narration'),headline=guide?.querySelector('[data-au-guide-headline]'),focus=guide?.querySelector('.au-doc-focus'),layer=guide?.querySelector('.au-doc-focus-layer'),label=guide?.querySelector('[data-au-guide-target-label]');
          const rect=el=>{const r=el?.getBoundingClientRect();return r?{left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height}:null;};
          const footer=document.querySelector('.au-executive-transport');
          return {guide_count:document.querySelectorAll('.au-documentary-guide').length,
            cue:guide?.dataset.auGuideCue,target:guide?.dataset.auGuideTarget,target_id:guide?.dataset.auGuideTargetId,
            spotlight:guide?.dataset.auGuideSpotlight==='true',resolved:guide?.dataset.auGuideResolved==='true',
            headline:headline?.textContent,headline_rect:rect(headline),headline_overflow:headline?headline.scrollWidth>headline.clientWidth+1:true,
            rail:rect(rail),focus:rect(focus),focus_opacity:layer?Number(getComputedStyle(layer).opacity):0,
            target_label:label?.textContent,footer_top:footer?.getBoundingClientRect().top??innerHeight-36,
            viewport:{width:innerWidth,height:innerHeight},time:CasepathPresentation.active.time};
        });
        row.beat=beat.index;row.act=beat.act;row.phase=beat.phase;diagnostic.guidance.push(row);
        assert.equal(row.guide_count,1,'Only one documentary guide is present.');
        assert(row.headline&&!row.headline_overflow&&row.headline_rect.bottom<=row.rail.bottom+1,'The complete guiding sentence must fit in its reserved rail.');
        if(row.spotlight){
          assert(row.resolved,'Every settled requested spotlight must resolve to product content: '+beat.index);
          assert(row.focus_opacity>.01&&row.focus.width>4&&row.focus.height>4,'A resolved target must also have a visible focus window: '+beat.index);
          assert(row.focus.top>=row.rail.bottom-1&&row.focus.bottom<=row.footer_top+1,'Focus remains inside the visible scene: '+beat.index);
        }
      }
      const failed=report.timeline.beats.filter(b=>b.phase==='legal-test-rest'&&b.predicate_status==='failed');
      assert(failed.length>0,'The recorded unmet-requirement hold must exist.');
      for(const beat of failed){
        await sample(beat.end-1);
        const row=await page.evaluate(id=>{
          const rows=[...document.querySelectorAll('[data-au-desk-answer] > .au-desk-tests > li')],matches=rows.filter(el=>el.dataset.auDeskPredicate===id),current=matches[0],guide=document.querySelector('.au-documentary-guide');
          return {predicate:id,matches:matches.length,text:current?.textContent?.trim(),opacity:current?Number(getComputedStyle(current).opacity):0,
            target:guide?.dataset.auGuideTarget,target_id:guide?.dataset.auGuideTargetId,target_label:guide?.querySelector('[data-au-guide-target-label]')?.textContent,
            visible_predicate_ids:rows.filter(el=>getComputedStyle(el).opacity==='1').map(el=>el.dataset.auDeskPredicate)};
        },beat.predicate);
        row.beat=beat.index;row.duration_ms=beat.duration;diagnostic.failed_predicates.push(row);
        assert.equal(row.matches,1);assert.equal(row.opacity,1);assert.equal(row.target,'predicate');
        assert.equal(row.target_id,beat.predicate);assert.equal(row.target_label,'Unmet requirement');assert.equal(beat.duration,2000);
      }
      await sample(0);diagnostic.status='passed';
      fs.writeFileSync(path.join(diagnosticDir,'receipt.json'),JSON.stringify(diagnostic,null,2)+'\n');
    }

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
