import assert from 'node:assert/strict';
export async function verifySupplement(browser,SITE,out){
 const r={errors:[],nativeViewerDiagnostics:[],writes:[],edge_beacons:[],contrast:[]};
 async function context(reducedMotion){
  const c=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:'block',reducedMotion});
  const p=await c.newPage();
  p.on('pageerror',e=>{const item={kind:'pageerror',message:e.message,stack:e.stack};if(String(e.stack).includes('chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/'))r.nativeViewerDiagnostics.push(item);else r.errors.push(item);});p.on('console',m=>{if(m.type()==='error'){const item={message:m.text(),location:m.location()};if(item.location.url.startsWith('chrome-extension://'))r.nativeViewerDiagnostics.push(item);else r.errors.push(item);}});
  await p.route('**/*',q=>{const req=q.request(),u=new URL(req.url());if(['GET','HEAD'].includes(req.method()))return q.continue();if(u.origin===SITE&&u.pathname.startsWith('/cdn-cgi/')){r.edge_beacons.push(req.method()+' '+u.pathname);return q.continue();}r.writes.push(req.method()+' '+u.origin+u.pathname);return q.abort();});
  return [c,p];
 }
 async function contrast(p,selector,label){
  const rows=await p.locator(selector).evaluateAll(es=>{
   const rgba=s=>{const n=s.match(/[\d.]+/g)?.map(Number);return n?[n[0],n[1],n[2],n[3]??1]:[0,0,0,0];};
   const blend=(a,b)=>a.slice(0,3).map((n,i)=>n*a[3]+b[i]*(1-a[3]));
   const lum=c=>c.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
   return es.filter(e=>e.getClientRects().length&&e.textContent.trim()).map(e=>{let bg=[255,255,255],opacity=1;const chain=[];for(let x=e;x;x=x.parentElement)chain.unshift(x);for(const x of chain){bg=blend(rgba(getComputedStyle(x).backgroundColor),bg);opacity*=Number(getComputedStyle(x).opacity);}const s=getComputedStyle(e),fg=rgba(s.color);fg[3]*=opacity;const a=lum(blend(fg,bg)),b=lum(bg);return {text:e.textContent.trim().slice(0,100),ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),opacity,color:s.color,fontSize:s.fontSize};});
  });
  assert.ok(rows.length,label+' has visible text');r.contrast.push({label,rows});assert.ok(rows.every(x=>x.ratio>=4.5),label+' text contrast');
 }
 let c,p;
 try{
  [c,p]=await context('no-preference');
  const url=SITE+'/#autonomous/claim/clm_543f08f2415b2a33';
  await p.goto(url,{waitUntil:'domcontentloaded'});await p.locator('[data-au-ns-completed]').waitFor({timeout:90000});
  const role=n=>p.locator('.au-ns-tabs [data-au-ns-role="'+n+'"]');
  await role('reader').click();const fact=p.locator('[data-au-ns-reader-fact]').first();await fact.waitFor();
  const citation=JSON.parse(await fact.getAttribute('data-au-citation'));assert.ok(citation.quote);
  await fact.focus();await p.keyboard.press('Tab');await p.keyboard.press('Shift+Tab');assert.ok(await fact.evaluate(e=>e===document.activeElement));
  r.focus=await fact.evaluate(e=>{const s=getComputedStyle(e);return {width:s.outlineWidth,style:s.outlineStyle,color:s.outlineColor};});assert.ok(parseFloat(r.focus.width)>=2&&r.focus.style!=='none');
  await contrast(p,'.au-ns-tabs [data-au-ns-role]','role controls');await contrast(p,'[data-au-ns-reader-fact]','reader facts');
  await p.keyboard.press('Enter');await p.locator('.au-source-dialog[open] .au-source-body mark').waitFor();
  r.source={quote:await p.locator('.au-source-body mark').first().textContent(),metadata:await p.locator('.au-source-dialog').innerText()};assert.equal(r.source.quote,citation.quote);assert.match(r.source.metadata,/exact cited span verified/i);
  r.nativeTabTrace=[];for(let i=0;i<12;i++){await p.keyboard.press('Tab');r.nativeTabTrace.push(await p.evaluate(()=>({tag:document.activeElement?.tagName,inDialog:!!document.activeElement?.closest('.au-source-dialog[open]'),documentFocused:document.hasFocus(),text:document.activeElement?.tagName==='BODY'?'':document.activeElement?.textContent?.trim().slice(0,80)})));}assert.ok(r.nativeTabTrace.every(x=>x.inDialog||!x.documentFocused||x.tag==='BODY'),'no background application control receives focus');
  await p.screenshot({path:out+'/source-keyboard.png'});r.sourceBeforeEscape=await p.evaluate(()=>({open:!!document.querySelector('.au-source-dialog[open]'),active:document.activeElement?.outerHTML.slice(0,600)}));r.nativePdfKeyboard={wasFocused:r.sourceBeforeEscape.active.startsWith('<iframe'),tabsToAppControl:0};
  if(r.nativePdfKeyboard.wasFocused||await p.evaluate(()=>!document.hasFocus()||document.activeElement?.tagName==='BODY')){
    for(let i=0;i<30;i++){
      const inNative=await p.evaluate(()=>!document.hasFocus()||document.activeElement?.tagName==='IFRAME'||document.activeElement?.tagName==='BODY');if(!inNative)break;
      await p.keyboard.press('Tab');r.nativePdfKeyboard.tabsToAppControl++;
    }
    r.nativePdfKeyboard.returnTarget=await p.evaluate(()=>({tag:document.activeElement?.tagName,text:document.activeElement?.textContent?.trim().slice(0,100),inDialog:!!document.activeElement?.closest('.au-source-dialog[open]')}));
    assert.ok(r.nativePdfKeyboard.returnTarget.inDialog&&r.nativePdfKeyboard.returnTarget.tag!=='IFRAME','Tab returns from native PDF to application dialog');
  }
  await p.keyboard.press('Escape');await p.waitForFunction(()=>!document.querySelector('.au-source-dialog[open]')&&document.activeElement===document.querySelector('[data-au-ns-reader-fact]'),undefined,{timeout:3000});r.keyboard={tabShiftTab:true,enterSource:true,backgroundControlsUnreachable:true,escapeReturnsFocus:true};
  await role('builder').click();await p.locator('[data-au-desk-select="ri_form"]').click();const law=p.locator('[data-au-ns-chain="law"]');await law.focus();await p.keyboard.press('Enter');
  await p.locator('.au-record-dialog[open] [data-au-ns-law-source]').waitFor();
  r.law={text:await p.locator('[data-au-ns-law-source]').innerText(),articles:await p.locator('[data-au-ns-law-source] article pre').allTextContents(),links:await p.locator('[data-au-ns-law-source] [data-au-law-article]').evaluateAll(es=>es.map(e=>e.getAttribute('href')))};
  assert.ok(r.law.articles.length&&r.law.articles.every(x=>x.trim()));assert.ok(r.law.links.length&&r.law.links.every(x=>x.includes('fedlex.admin.ch')));assert.match(r.law.text,/Qualified legal review is still required/);r.law.dialog=await p.locator('.au-record-dialog[open]').innerText();assert.match(r.law.dialog,/failed/i);assert.ok((await p.url()).includes('ri_form'));
  await contrast(p,'[data-au-ns-law-source] article pre','legal article');await p.screenshot({path:out+'/law.png'});await p.keyboard.press('Escape');await p.waitForFunction(()=>!document.querySelector('.au-record-dialog[open]')&&document.activeElement===document.querySelector('[data-au-ns-chain=law]'),undefined,{timeout:3000});
  await role('result').click();await p.locator('[data-au-desk-draft]').click();await p.locator('.au-desk-draft').waitFor();const original=await p.locator('.au-record-dialog[open] .au-desk-draft .au-record-body').innerText();assert.match(await p.locator('.au-desk-draft').innerText(),/Not sent/);
  await p.locator('[data-au-draft-edit]').click();await p.locator('[data-au-draft-subject]').fill('Release verification local copy');await p.locator('[data-au-draft-body]').fill('Saved only in this disposable browser context.');await p.locator('[data-au-draft-save]').click();
  assert.match(await p.locator('[data-au-draft-status]').innerText(),/saved on this device/i);await contrast(p,'[data-au-draft-status]','draft status');await p.keyboard.press('Escape');await p.reload({waitUntil:'domcontentloaded'});await p.locator('[data-au-desk-draft]').waitFor({timeout:90000});await p.locator('[data-au-desk-draft]').click();await p.locator('.au-desk-draft').waitFor();assert.match(await p.locator('.au-desk-draft').innerText(),/Release verification local copy/);assert.equal(await p.locator('.au-record-dialog[open] .au-desk-draft .au-record-body').innerText(),'Saved only in this disposable browser context.');
  await p.locator('[data-au-draft-original]').click();assert.equal(await p.locator('.au-record-dialog[open] .au-desk-draft .au-record-body').innerText(),original);r.draft={savedLocally:true,reloadPersistence:true,originalUnchanged:true,disposableContext:true};await p.screenshot({path:out+'/draft-original.png'});await p.keyboard.press('Escape');await c.close();c=null;
  [c,p]=await context('reduce');await p.goto(SITE+'/#autonomous/demonstration',{waitUntil:'domcontentloaded'});await p.locator('[data-au-ns-start]').waitFor({timeout:90000});await p.locator('[data-au-ns-start]').click();await p.locator('[data-au-ns-completed]').waitFor({timeout:90000});await p.locator('.au-ns-tabs [data-au-ns-role="result"]').click();await p.locator('[data-au-desk-answer]').waitFor();
  r.reduced=await p.evaluate(()=>({runningAnimations:document.getAnimations().filter(a=>a.playState==='running').length,cursors:document.querySelectorAll('.au-ns-cursor').length,role:document.querySelector('.au-ns-tabs [aria-current]')?.dataset.auNsRole}));assert.deepEqual(r.reduced,{runningAnimations:0,cursors:0,role:'result'});await p.screenshot({path:out+'/reduced-motion.png'});assert.deepEqual(r.errors,[]);assert.deepEqual(r.writes,[]);r.passed=true;
 }catch(e){r.failure=String(e);if(p)r.failureFocus=await p.evaluate(()=>({sourceOpen:!!document.querySelector('.au-source-dialog[open]'),recordOpen:!!document.querySelector('.au-record-dialog[open]'),active:document.activeElement?.outerHTML.slice(0,700)}));if(p)await p.screenshot({path:out+'/supplement-failure.png'}).catch(()=>{});throw Object.assign(e,{supplement:r});}finally{if(c)await c.close();r.cleanup={contextsClosed:true};}
 return r;
}

