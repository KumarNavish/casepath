'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process'),{once}=require('node:events');
const {chromium}=require('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-sites-hosting-20261009/casepath-qa/node_modules/playwright');
const ROOT='/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024';
const OUT=ROOT+'/.runtime/guided-film-20261025/clean-source-02';
const SOURCE='a1b59cf5d78662b35790a11cfd2d46851310482d';
const URL='https://casepath-autonomous.kumarnavish.chatgpt.site/?present=1#autonomous/demonstration';
const FFMPEG='/Users/kumar0002/.local/bin/ffmpeg', FFPROBE='/Users/kumar0002/.local/bin/ffprobe';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const anchors=[
['opening',0],['customer',6100],['workspace',7500],['notice-before',12000],['notice-quote',15000],
['fact',18000],['later-email',21500],['process',28200],['chain',33400],
['source-check',37100],['law',42800],['documents',46800],['checks-start',48200],['failed',51600],
['assessment',57400],['open-questions',60300],['draft',65000],['draft-status',67600],
['later-case',69500],['reuse-before',71700],['reuse-one',73900],['reuse-two',76500],['reuse-three',79100],
['reuse-notice',81100],['later-result',85500],['case-list',92400],['closing',96000]
];
(async()=>{
let browser,enc,logfd;
const report={contract:'casepath.guided-film-clean-source/1',started_at:new Date().toISOString(),source_commit:SOURCE,
purpose:'Editorial source plates and actual recorded UI motion for a standalone silent-capable film',
source_url:URL,request_policy:'GET/HEAD only; same-origin hosting challenge allowed and recorded',writes:[],unexpected_destinations:[],edge_beacons:[],browser_errors:[],anchors:[],
editorial_override:'.au-documentary-guide { visibility: hidden !important; }',
product_source_modified:false,recorded_replay:true,new_inference:false,fps:30,width:3840,height:2160};
try{
assert(!fs.existsSync(OUT),'Fresh capture directory required');
assert.equal(execFileSync('git',['rev-parse','HEAD'],{cwd:ROOT,encoding:'utf8'}).trim(),SOURCE);
assert.equal(execFileSync('git',['status','--porcelain=v1'],{cwd:ROOT,encoding:'utf8'}).trim(),'');
fs.mkdirSync(OUT,{recursive:true});fs.mkdirSync(OUT+'/plates');
browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const context=await browser.newContext({viewport:{width:1600,height:900},deviceScaleFactor:2.4,serviceWorkers:'block',locale:'en-GB',timezoneId:'UTC',reducedMotion:'no-preference'});
const page=await context.newPage(),allowed=new Set(['https://casepath-autonomous.kumarnavish.chatgpt.site','https://casepath-agent.fastapicloud.dev']);
page.on('pageerror',e=>report.browser_errors.push(e.message));
page.on('console',m=>{if(m.type()==='error')report.browser_errors.push(m.text());});
await page.route('**/*',route=>{
const r=route.request(),u=new global.URL(r.url()),m=r.method();
if(m==='POST'&&u.origin==='https://casepath-autonomous.kumarnavish.chatgpt.site'&&u.pathname.startsWith('/cdn-cgi/challenge-platform/h/b/jsd/oneshot/')){
report.edge_beacons.push({method:m,origin:u.origin,pathname_prefix:'/cdn-cgi/challenge-platform/h/b/jsd/oneshot/',path_sha256:sha(u.pathname)});return route.continue();}
if(!['GET','HEAD'].includes(m)){report.writes.push(m+' '+u.pathname);return route.abort();}
if(!allowed.has(u.origin)){report.unexpected_destinations.push(u.origin+u.pathname);return route.abort();}
return route.continue();
});
const health=await context.request.get('https://casepath-agent.fastapicloud.dev/healthz');assert(health.ok());const h=await health.json();
assert.equal(h.source_commit,SOURCE);assert.equal(h.read_only,true);assert.equal(h.writable,false);
report.api_identity={source_commit:h.source_commit,read_only:h.read_only,writable:h.writable};
const deployment=await context.request.get('https://casepath-autonomous.kumarnavish.chatgpt.site/deployment.json');assert(deployment.ok());const d=await deployment.json();assert.equal(d.source_commit,SOURCE);report.frontend_source_commit=d.source_commit;
report.assets={};
for(const n of ['autonomous-language-v1.js','autonomous-presentation-v1.js','autonomous-workspace-v1.js','autonomous-workspace-v1.css']){
const response=await context.request.get('https://casepath-autonomous.kumarnavish.chatgpt.site/assets/'+n);assert(response.ok());
const local=fs.readFileSync(ROOT+'/casepath/assets/'+n),remote=await response.body();assert.equal(sha(remote),sha(local));report.assets[n]=sha(local);
}
await page.goto(URL,{waitUntil:'domcontentloaded',timeout:60000});
await page.waitForFunction(()=>window.CasepathPresentation?.active,null,{timeout:90000});
await page.evaluate(()=>document.fonts.ready);
await page.addStyleTag({content:report.editorial_override});
const sample=async at=>{await page.evaluate(at=>{const a=CasepathPresentation.active;a.advanceTo(at);if(a.time!==at)throw Error('Timeline did not seek');if(document.getAnimations().length)throw Error('Uncontrolled animation clock');},at);};
report.timeline=await page.evaluate(()=>CasepathPresentation.active.manifest);
assert.equal(report.timeline.duration,98550);fs.writeFileSync(OUT+'/timeline.json',JSON.stringify(report.timeline,null,2)+'\n');
for(const [name,time] of anchors){
await sample(time);
const b=await page.screenshot({type:'png',path:OUT+'/plates/'+name+'.png'});
const info=await page.evaluate(()=>{
const selectorList=['.au-ns-spine','.au-ns-source','.au-ns-plan','.au-ns-facts','.au-desk-tests','[data-au-desk-answer]','.au-ns-memory','.au-sources','.au-documentary-guide'];
const nodes={};
for(const selector of selectorList){const els=[...document.querySelectorAll(selector)];nodes[selector]=els.filter(e=>e.getClientRects().length).map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,text:e.textContent.trim().slice(0,2500)};});}
const g=document.querySelector('.au-documentary-guide');return {nodes,guide_hidden:getComputedStyle(g).visibility==='hidden',body:document.body.innerText.slice(0,14000)};
});
assert(info.guide_hidden);
report.anchors.push({name,time,path:'plates/'+name+'.png',sha256:sha(b),bytes:b.length,...info});
}
console.log(JSON.stringify({stage:'plates_complete',anchors:report.anchors.length,out:OUT}));
fs.writeFileSync(OUT+'/plates-receipt.json',JSON.stringify(report,null,2)+'\n');
await sample(0);
const count=Math.ceil(report.timeline.duration*30/1000);
logfd=fs.openSync(OUT+'/encode.log','wx');
enc=spawn(FFMPEG,['-nostdin','-hide_banner','-loglevel','warning','-f','image2pipe','-vcodec','png','-framerate','30','-i','pipe:0','-frames:v',String(count),'-c:v','libx264','-preset','fast','-crf','15','-pix_fmt','yuv420p','-an','-movflags','+faststart',OUT+'/CasePath_Clean_Source.mp4'],{stdio:['pipe',logfd,logfd]});
const finished=once(enc,'exit');enc.stdin.on('error',()=>{});
const index=fs.openSync(OUT+'/frame-index.jsonl','wx');
for(let n=0;n<count;n++){
const time=n*1000/30;await sample(time);
const b=await page.screenshot({type:'png'});assert.equal(b.readUInt32BE(16),3840);assert.equal(b.readUInt32BE(20),2160);
fs.writeSync(index,JSON.stringify({frame:n,source_ms:time,sha256:sha(b)})+'\n');
assert.equal(enc.exitCode,null);if(!enc.stdin.write(b))await once(enc.stdin,'drain');
if(n%300===0)console.log(JSON.stringify({stage:'capture',frame:n,total:count}));
}
enc.stdin.end();const [exit]=await finished;assert.equal(exit,0);fs.closeSync(index);fs.closeSync(logfd);logfd=null;
const p=JSON.parse(execFileSync(FFPROBE,['-v','error','-show_streams','-show_format','-of','json',OUT+'/CasePath_Clean_Source.mp4'],{encoding:'utf8'}));
const v=p.streams.find(s=>s.codec_type==='video');assert.equal(v.width,3840);assert.equal(v.height,2160);assert.equal(Number(v.nb_frames),count);assert.equal(v.avg_frame_rate,'30/1');
assert.equal(report.writes.length,0);assert.equal(report.unexpected_destinations.length,0);assert.equal(report.browser_errors.length,0);
report.video={path:'CasePath_Clean_Source.mp4',bytes:fs.statSync(OUT+'/CasePath_Clean_Source.mp4').size,sha256:sha(fs.readFileSync(OUT+'/CasePath_Clean_Source.mp4')),probe:p};
report.frame_index_sha256=sha(fs.readFileSync(OUT+'/frame-index.jsonl'));
report.status='passed';report.finished_at=new Date().toISOString();fs.writeFileSync(OUT+'/capture-receipt.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({status:report.status,video:report.video.path,sha256:report.video.sha256,frames:count,out:OUT}));
}catch(e){report.status='failed';report.error=String(e.stack||e);if(fs.existsSync(OUT))fs.writeFileSync(OUT+'/capture-failure.json',JSON.stringify(report,null,2)+'\n');if(enc&&!enc.killed)enc.kill('SIGTERM');console.error(e.stack||e);process.exitCode=1;}
finally{if(logfd)fs.closeSync(logfd);if(browser)await browser.close();}
})();
