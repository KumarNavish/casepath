'use strict';
// Runtime-only, read-only fixture capture. Does not start a server or modify the app.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const {createHash} = require('node:crypto'), {gunzipSync} = require('node:zlib');
const {chromium} = require('playwright');
const root = process.env.CASEPATH_SOURCE_ROOT || '/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024';
const out = process.env.CASEPATH_OPENING_EVIDENCE_DIR;
if (!out || !path.isAbsolute(out)) throw new Error('CASEPATH_OPENING_EVIDENCE_DIR must name a fresh absolute directory.');
fs.mkdirSync(path.dirname(out), {recursive:true});
fs.mkdirSync(out); // Refuse to overwrite an earlier evidence directory.
const hash = file => createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex');
const files = ['casepath/assets/autonomous-language-v1.js','casepath/assets/autonomous-presentation-v1.js','casepath/assets/autonomous-workspace-v1.js','casepath/assets/autonomous-workspace-v1.css','casepath-qa/autonomous-workspace-v1.test.cjs','casepath-qa/autonomous-presentation-browser-v1.test.cjs'];
const fixtureFiles = ['casepath-qa/fixtures/presentation-v1.json.gz','casepath-qa/fixtures/desk-v3.json.gz'];
const receipt = {startedAt:new Date().toISOString(),sourceRoot:root,sourceHashes:{},fixtureHashes:{},requests:[],writes:[],pageErrors:[],consoleErrors:[],missingFixtures:[],frames:[],scenarios:[],completed:false};
let browser;

async function capture(page, scenario, name) {
  await page.evaluate(async()=>{await document.fonts.ready;await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
  const frame = await page.evaluate(()=>{
    function visibility(element) {
      if (!element) return null;
      const rect = element.getBoundingClientRect(), clip = {left:0,top:0,right:innerWidth,bottom:innerHeight};
      for(let ancestor=element;ancestor;ancestor=ancestor.parentElement){
        const style=getComputedStyle(ancestor),bounds=ancestor.getBoundingClientRect();
        if(/hidden|clip|scroll|auto/.test(style.overflowX)){clip.left=Math.max(clip.left,bounds.left);clip.right=Math.min(clip.right,bounds.right);}
        if(/hidden|clip|scroll|auto/.test(style.overflowY)){clip.top=Math.max(clip.top,bounds.top);clip.bottom=Math.min(clip.bottom,bounds.bottom);}
      }
      const walker=document.createTreeWalker(element,NodeFilter.SHOW_TEXT),fragments=[];
      for(let node=walker.nextNode();node;node=walker.nextNode())if(node.textContent.trim()){
        const range=document.createRange();range.selectNodeContents(node);
        for(const box of range.getClientRects())if(box.width&&box.height)fragments.push({text:node.textContent.trim(),left:box.left,top:box.top,right:box.right,bottom:box.bottom});
      }
      const clipped=fragments.filter(box=>box.left<clip.left-1||box.right>clip.right+1||box.top<clip.top-1||box.bottom>clip.bottom+1);
      return {text:element.textContent.trim(),bounds:rect.toJSON(),clip,boundsFullyVisible:rect.width>0&&rect.height>0&&rect.left>=clip.left-1&&rect.right<=clip.right+1&&rect.top>=clip.top-1&&rect.bottom<=clip.bottom+1,textFragments:fragments.length,clippedFragments:clipped,fullyVisible:fragments.length>0&&!clipped.length};
    }
    const host=document.querySelector('[data-au-view]'),width=Math.max(document.documentElement.scrollWidth,document.body.scrollWidth);
    return {viewport:{width:innerWidth,height:innerHeight},documentWidth:width,horizontalOverflow:Math.max(0,width-innerWidth),title:document.title,preparing:!!host.querySelector('[data-au-presentation-preparing]'),unavailable:!!host.querySelector('[data-au-presentation-unavailable]'),busy:!!host.querySelector('[aria-busy="true"]'),headings:[...host.querySelectorAll('h1,h2')].map(visibility),purpose:visibility(host.querySelector('[data-au-ns-purpose]')),preparationStatus:visibility(host.querySelector('.au-ns-preparation-status')),retry:visibility(host.querySelector('[data-au-presentation-unavailable] [data-au-nav="demonstration"]')),completedExampleLink:visibility(host.querySelector('[data-au-ns-purpose] button')),status:document.querySelector('.au-global-status').textContent,caseTitle:host.querySelector('[data-au-claim-title]')?.textContent||null,clock:window.CasepathPresentation?.active?{time:CasepathPresentation.active.time,paused:CasepathPresentation.active.paused}:null};
  });
  const file=name+'.png';await page.screenshot({path:path.join(out,file),fullPage:false});
  receipt.frames.push({scenario,file,...frame});
}

async function scenario(kind, wire, recorded) {
  const context=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:'block'}),page=await context.newPage();
  page.on('pageerror',error=>receipt.pageErrors.push({scenario:kind,message:error.message}));
  page.on('console',message=>{if(message.type()==='error')receipt.consoleErrors.push({scenario:kind,message:message.text()});});
  await page.route('**/*',async route=>{
    const request=route.request(),url=new URL(request.url()),key=url.pathname+url.search;
    const entry={scenario:kind,method:request.method(),path:key,type:request.resourceType()};receipt.requests.push(entry);
    if(!['GET','HEAD'].includes(request.method())){receipt.writes.push(entry);return route.abort();}
    if(request.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0"><main id="workspace"></main></body></html>'});
    if(/\/fonts\/[^/]+\.ttf$/.test(url.pathname))return route.fulfill({contentType:'font/ttf',path:path.join(root,'casepath/assets/fonts',path.basename(url.pathname))});
    const id=url.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1],record=id&&recorded.cases.find(row=>row.id===id);
    if(record)return route.fulfill({contentType:'application/x-ndjson',body:record.trace});
    if(wire[key])return route.fulfill({contentType:'application/json',body:JSON.stringify(wire[key])});
    receipt.missingFixtures.push(entry);return route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'No recorded fixture for '+key})});
  });
  try {
    // Manual playback keeps the admitted introduction at exactly time zero.
    // The separate frozen regressions verify present=1 autoplay.
    await page.goto('http://localhost:41999/?present=0');
    await page.addStyleTag({path:path.join(root,'casepath/assets/autonomous-workspace-v1.css')});
    for(const asset of ['autonomous-language-v1.js','autonomous-presentation-v1.js','autonomous-workspace-v1.js'])await page.addScriptTag({path:path.join(root,'casepath/assets',asset)});
    await page.evaluate(()=>{
      window.CASEPATH_PUBLIC_READ_ONLY=true;window.heldStates=[];
      window.product=CasePathAutonomous.mount(document.querySelector('#workspace'),{fetch:async(url,init)=>{
        const response=await window.fetch(url,init),id=new URL(url,location.href).pathname.match(/\/claims\/([^/]+)$/)?.[1];
        return id?new Promise(resolve=>window.heldStates.push({id,response,resolve})):response;
      }});
    });
    await page.waitForFunction(count=>window.heldStates.length===count,recorded.cases.length-1,{timeout:45000});
    const heldIds=await page.evaluate(()=>window.heldStates.map(row=>row.id));
    assert.deepEqual([...heldIds].sort(),recorded.cases.slice(1).map(row=>row.id).sort());
    assert.equal(await page.locator('[data-au-presentation-preparing]').count(),1);
    assert.equal(await page.evaluate(()=>Boolean(CasepathPresentation.active)),false);
    if(kind==='ready'){
      await capture(page,kind,'preparing-desktop');
      await page.setViewportSize({width:375,height:812});await capture(page,kind,'preparing-mobile');
      await page.setViewportSize({width:1440,height:900});
    }
    await page.evaluate(async kind=>{
      const rows=[...window.heldStates].reverse();
      if(kind==='invalid'){
        const row=rows.shift(),data=await row.response.json();(data.state||data).claim_id='unrelated-claim';
        row.resolve(new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}}));
      }
      for(const row of rows){row.resolve(row.response);await Promise.resolve();}
    },kind);
    if(kind==='ready'){
      await page.waitForFunction(()=>window.CasepathPresentation?.active,{},{timeout:45000});
      const admission=await page.evaluate(()=>({claims:CasepathPresentation.active.manifest.claims,stateHashes:CasepathPresentation.active.manifest.stateHashes,time:CasepathPresentation.active.time,paused:CasepathPresentation.active.paused}));
      assert.deepEqual(admission.claims,recorded.cases.slice(7).map(row=>row.id));assert.equal(admission.time,0);assert.equal(admission.paused,true);
      await capture(page,kind,'admitted-intro-desktop');receipt.scenarios.push({kind,heldIds,admission});
    }else{
      await page.waitForFunction(()=>document.querySelector('[data-au-presentation-unavailable]'),{},{timeout:45000});
      assert.equal(await page.evaluate(()=>Boolean(CasepathPresentation.active)),false);
      assert.equal(await page.locator('[data-au-claim-title],.au-ns-spine li,[data-au-source],[aria-busy="true"]').count(),0);
      await capture(page,kind,'invalid-state-desktop');
      await page.setViewportSize({width:375,height:812});await capture(page,kind,'invalid-state-mobile');receipt.scenarios.push({kind,heldIds});
    }
  } finally {
    await page.evaluate(()=>{for(const row of window.heldStates||[])row.resolve(row.response);window.product?.destroy();}).catch(()=>{});
    await context.close();
  }
}

(async()=>{
  try {
    receipt.sourceHashes=Object.fromEntries(files.map(file=>[file,hash(file)]));
    receipt.fixtureHashes=Object.fromEntries(fixtureFiles.map(file=>[file,hash(file)]));
    receipt.fontSha256=hash('casepath/assets/fonts/Mulish.ttf');
    const load=file=>JSON.parse(gunzipSync(fs.readFileSync(path.join(root,file))));
    const wire=load(fixtureFiles[0]).responses,recorded=load(fixtureFiles[1]);
    browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
    for(const kind of ['ready','invalid'])await scenario(kind,wire,recorded);
    assert.deepEqual(receipt.writes,[]);assert.deepEqual(receipt.pageErrors,[]);assert.deepEqual(receipt.missingFixtures,[]);
    receipt.completed=true;
  } catch(error) {receipt.failure={message:error.message,stack:error.stack};process.exitCode=1;}
  finally {
    if(browser)await browser.close().catch(error=>{receipt.closeError=error.message;});
    receipt.finishedAt=new Date().toISOString();
    receipt.visualChecks=receipt.frames.map(frame=>({file:frame.file,noHorizontalOverflow:frame.horizontalOverflow<=1,headingsFullyVisible:frame.headings.every(row=>row.fullyVisible),purposeFullyVisible:frame.purpose?.fullyVisible===true,preparationStatusFullyVisible:frame.preparationStatus?frame.preparationStatus.fullyVisible&&frame.preparationStatus.boundsFullyVisible:null,retryWhollyVisible:frame.retry?frame.retry.fullyVisible&&frame.retry.boundsFullyVisible:null,completedExampleLinkFullyVisible:frame.completedExampleLink?.fullyVisible??null}));
    fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify(receipt,null,2)+'\n');
    console.log(JSON.stringify({completed:receipt.completed,receipt:path.join(out,'receipt.json'),frames:receipt.frames.map(row=>row.file),failure:receipt.failure?.message}));
  }
})();
