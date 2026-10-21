// Desktop-only W2.5 interaction/layout check against the isolated reference preview.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const {chromium}=createRequire(new URL('../../casepath-qa/package.json',import.meta.url))('playwright');
const [,,out,...pairs]=process.argv,overrides=Object.fromEntries(pairs.map(p=>p.split('=')));
fs.mkdirSync(out,{recursive:true});fs.rmSync(`${out}/story.json`,{force:true});
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM});
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[],writes=[];
page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{const q=r.request(),name=new URL(q.url()).pathname.split('/').pop();if(!['GET','HEAD'].includes(q.method())){writes.push(q.url());return r.abort();}return overrides[name]?r.fulfill({path:overrides[name],contentType:name.endsWith('.css')?'text/css':'text/javascript'}):r.continue();});
try {
 await page.goto((process.env.BASE||'http://127.0.0.1:4180')+'/#autonomous/demonstration');
 await page.waitForSelector('[data-au-story=work] [data-au-operation-span]',{timeout:60000});
 const work=await page.evaluate(()=>{
  const el=s=>document.querySelector(s),rect=s=>{const r=el(s).getBoundingClientRect();return {left:r.left,top:r.top,bottom:r.bottom,width:r.width}};
  const style=s=>getComputedStyle(el(s));
  return {heading:rect('[data-au-claim-title]'),source:rect('.au-stage-source'),map:rect('.au-stage-process'),headingSize:style('[data-au-claim-title]').fontSize,askSize:style('[data-au-case-asks]').fontSize,modeTag:el('.au-demo-mode').tagName,modeSize:style('.au-demo-mode').fontSize,roleBackground:style('.au-now .au-role-badge').backgroundColor,stepMarkers:document.querySelectorAll('.au-step-role').length,askBorder:style('[data-au-case-asks]').borderBottomWidth};
 });
 assert.equal(work.heading.left,36);assert.equal(work.source.left,36);assert.equal(work.source.width,1200);assert.ok(work.map.top-work.source.bottom>=16,JSON.stringify(work));
 assert.equal(work.headingSize,'22px');assert.equal(work.askSize,'16px');assert.equal(work.modeSize,'15px');assert.equal(work.modeTag,'SPAN');assert.equal(work.stepMarkers,0);assert.equal(work.askBorder,'0px');assert.equal(work.roleBackground,'rgba(0, 0, 0, 0)');
 assert.equal(await page.locator('.au-stage-fact[data-au-fact-state=observed]').first().evaluate(el=>getComputedStyle(el).borderLeftStyle),'solid');
 await page.screenshot({path:`${out}/work.png`});
 await page.waitForSelector('[data-au-story=answer]',{timeout:120000});
 const answer=await page.locator('[data-au-stage-outcome]').innerText();
 assert.ok(await page.locator('.au-stage-layout').isVisible());
 const result=await page.evaluate(()=>{const a=document.querySelector('[data-au-stage-outcome]').getBoundingClientRect(),m=document.querySelector('.au-stage-layout').getBoundingClientRect();return {left:a.left,width:a.width,top:a.top,bottom:a.bottom,mapTop:m.top,mapOpacity:getComputedStyle(document.querySelector('.au-stage-layout')).opacity};});
 assert.equal(result.left,36);assert.equal(result.width,1200);assert.ok(result.bottom<=900);assert.ok(result.mapTop-result.bottom>=16,JSON.stringify(result));assert.equal(result.mapOpacity,'0.75');
 await page.screenshot({path:`${out}/answer.png`});
 await page.waitForSelector('[data-au-story=handoff]',{timeout:15000});
 assert.ok((await page.locator('[data-au-stage-outcome]').innerText()).startsWith(answer));
 assert.ok(await page.locator('[data-au-stage-outcome] [data-au-story-handoff]').isVisible());
 assert.equal(await page.locator('[data-au-story-handoff]').evaluate(el=>getComputedStyle(el).fontSize),'15px');
 assert.ok(await page.locator('.au-stage-layout').isVisible());
 await page.screenshot({path:`${out}/handoff.png`});
 assert.equal(await page.locator('[data-au-inspect=notice]').count(),0);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth),0);
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
 fs.writeFileSync(`${out}/story.json`,JSON.stringify({status:'passed',viewport:{width:1440,height:900},work,result,errors,writes},null,2)+'\n');
 console.log('Desktop story and layout passed');
}finally{await browser.close();}
