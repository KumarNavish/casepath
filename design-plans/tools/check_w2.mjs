// Read-only story and roster checks on the isolated nine-reference preview.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../../casepath-qa/package.json',import.meta.url));
const {chromium}=require('playwright'),ui=require('../casepath/assets/autonomous-workspace-v1.js');
const out=process.argv[2];fs.mkdirSync(out,{recursive:true});fs.rmSync(`${out}/checks.json`,{force:true});
const base=process.env.BASE||'http://127.0.0.1:4180';
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH});
const results=[];
try {
 for(const width of [1440,390]) {
  const page=await browser.newPage({viewport:{width,height:width===390?844:900}}),errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',r=>{if(!['GET','HEAD'].includes(r.request().method())){writes.push(r.request().url());return r.abort();}return r.continue();});
  await page.addInitScript(()=>{
   window.storyFrames=[];
   new MutationObserver(()=>{
    const section=document.querySelector('[data-au-story]');if(!section)return;
    const phase=section.dataset.auStory,caseId=location.hash.split('/')[2]?.split('?')[0];
    const last=window.storyFrames.at(-1);
    if(!last||phase!==last.phase||caseId!==last.caseId)window.storyFrames.push({phase,caseId,at:performance.now(),title:document.querySelector('[data-au-claim-title]')?.textContent});
   }).observe(document,{childList:true,subtree:true});
  });
  await page.goto(base+'/#autonomous/demonstration');
  await page.waitForSelector('[data-au-story=opening]',{timeout:60000});
  assert.match(await page.locator('[data-au-claim-title]').innerText(),/^Case 1 of 9 · Defects and repairs$/);
  assert.ok(await page.locator('[data-au-case-asks]').isVisible());
  assert.equal(await page.locator('.au-evidence-canvas').isVisible(),false);
  await page.screenshot({path:`${out}/${width}-opening.png`});
  await page.waitForSelector('[data-au-story=work] .au-operation-passage [data-au-operation-span]',{timeout:60000});
  await page.screenshot({path:`${out}/${width}-work.png`});
  await page.waitForSelector('[data-au-story=answer]',{timeout:120000});
  assert.equal(await page.locator('.au-stage-outcome > .au-outcome-next').count(),0,'no invented action for a reference result');
  assert.equal(await page.locator('.au-stage-outcome > .au-outcome-why').getAttribute('open'),null);
  await page.waitForFunction(()=>{const answer=document.querySelector('[data-au-outcome-plain]')?.getBoundingClientRect();return answer&&answer.top>=0&&answer.bottom<=innerHeight;});
  assert.equal(await page.locator('.au-stage-layout').isVisible(),false,'the answer is the reading focus during its hold');
  if(width===390) {
   await page.locator('[data-au-demo-stop]').click();
   assert.equal(await page.locator('.au-stage-layout').isVisible(),true,'pausing restores the completed steps');
   await page.locator('[data-au-demo-resume]').click();
   assert.equal(await page.locator('.au-stage-layout').isVisible(),false);
  }
  await page.screenshot({path:`${out}/${width}-answer.png`});
  await page.waitForSelector('[data-au-story=handoff]',{timeout:15000});
  assert.equal(await page.locator('[data-au-story-handoff]').innerText(),`Next case: ${ui.caseLabel(ui.REFERENCE_DEMO_CASES[1].claim_id).primary}`);
  await page.screenshot({path:`${out}/${width}-handoff.png`});
  await page.waitForSelector('[data-au-story=opening]',{timeout:60000});
  assert.match(await page.locator('[data-au-claim-title]').innerText(),/^Case 2 of 9 · Defects and repairs$/);
  await page.waitForSelector('[data-au-story=work]',{timeout:10000});
  const frames=await page.evaluate(()=>window.storyFrames),first=frames.filter(f=>f.caseId==='clm_314f2d309fea25e6');
  const opening=first.find(f=>f.phase==='opening'),work=first.find(f=>f.phase==='work'&&f.at>opening?.at),answer=first.find(f=>f.phase==='answer'),handoff=first.find(f=>f.phase==='handoff');
  assert.ok(opening&&work&&answer&&handoff,JSON.stringify(frames));
  const durations={opening:work.at-opening.at,answer:handoff.at-answer.at,handoff:frames.find(f=>f.caseId===ui.REFERENCE_DEMO_CASES[1].claim_id)?.at-handoff.at};
  assert.ok(durations.opening>=1450&&durations.opening<3000,JSON.stringify(durations));
  assert.ok(durations.answer>=7900&&durations.answer<10000,JSON.stringify(durations));
  assert.ok(durations.handoff>=550,JSON.stringify(durations));
  await page.locator('[data-au-demo-stop]').click();
  await page.locator('[data-au-inspect=demo]').click();
  assert.equal(await page.locator('.au-record-dialog[open] [data-au-demo-roster]').first().getAttribute('data-au-demo-roster'),'reference');
  await page.keyboard.press('Escape');
  await page.locator('.au-identity-header [data-au-nav=work]').click();
  await page.waitForSelector('[data-au-claim-row]');
  await page.locator('[data-au-filter=investigation_complete]').click();
  await page.waitForFunction(()=>document.querySelectorAll('[data-au-claim-row]').length===9);
  const marked=await page.locator('[data-au-claim-row]').evaluateAll(rows=>rows.filter(r=>r.innerText.includes('In demonstration')).map(r=>r.dataset.auClaimRow));
  assert.deepEqual(marked.sort(),ui.REFERENCE_DEMO_CASES.map(r=>r.claim_id).sort());
  await page.locator('.au-identity-header [data-au-nav=demonstration]').click();
  await page.waitForSelector('[data-au-story=opening]',{timeout:60000});
  assert.ok(page.url().includes(ui.REFERENCE_DEMO_CASES[0].claim_id));
  assert.equal(await page.locator('[data-au-inspect=notice]').count(),0,'no replay fallback');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth),0);
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  results.push({width,durations,frames,marked,errors,writes});await page.close();
 }
 fs.writeFileSync(`${out}/checks.json`,JSON.stringify({status:'passed',results},null,2)+'\n');
 console.log(JSON.stringify(results.map(({width,durations,errors,writes})=>({width,durations,errors,writes}))));
} finally {await browser.close();}
