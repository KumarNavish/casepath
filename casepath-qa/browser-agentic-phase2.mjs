import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright';

const base=(process.env.BASE_URL||'http://127.0.0.1:4173').replace(/\/$/,'');
const out=path.resolve(process.env.CASEPATH_QA_OUT||'/tmp/casepath-phase2-shots');
const executablePath=process.env.PLAYWRIGHT_EXECUTABLE_PATH||'/Applications/ego lite.app/Contents/MacOS/ego lite';
const claims={flagship:'clm_f69b1747447bc221',mould:'clm_7ac806bd30792cfb',rent:'clm_6f04d0907ecb96bb'};
const widths=[1440,1024,390,320];
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath});
const context=await browser.newContext({viewport:{width:1440,height:900}});
const queue=await context.newPage();
const page=await context.newPage();
const errors=[];
for(const tab of [queue,page])tab.on('pageerror',error=>errors.push(error.message));
const timing={};
const queueStart=performance.now();
await queue.goto(base+'/');
await queue.locator('#cwTable tr[data-claim-id]').first().waitFor({timeout:30000});
timing.queue_first_paint_ms=Math.round(performance.now()-queueStart);
const outputs={};
for(const [name,claimId] of Object.entries(claims)){
  const openStart=performance.now();
  await page.goto(`${base}/#claim=${claimId}`);
  await page.locator('#cwDetailPanel').waitFor({timeout:30000});
  await page.locator('#cpReviewCard').waitFor({timeout:30000});
  timing[`${name}_claim_open_ms`]=Math.round(performance.now()-openStart);
  if(await page.locator('#cwStart').count()){
    const reviewStart=performance.now();
    await page.locator('#cwStart').click();
    await page.locator('.aw-narrative-lines li button').first().waitFor({timeout:30000});
    timing[`${name}_first_line_ms`]=Math.round(performance.now()-reviewStart);
    await page.locator('.cp-a-review-ready[data-status="completed"]').waitFor({state:'visible',timeout:45000});
    await page.locator('.cp-a-path').waitFor({timeout:45000});
    timing[`${name}_review_complete_ms`]=Math.round(performance.now()-reviewStart);
  }
  await page.locator('.cp-a-path').waitFor({timeout:30000});
  outputs[name]=await page.evaluate(()=>({
    noticed:[...document.querySelectorAll('.cp-a-noticed li')].map(row=>row.textContent.trim()),
    conditions:[...document.querySelectorAll('.cp-a-condition')].map(row=>row.textContent.trim()),
    path:[...document.querySelectorAll('.cp-a-path li[data-path-state]')].map(row=>({state:row.dataset.pathState,text:row.querySelector('strong')?.textContent.trim()})),
    needs:[...document.querySelectorAll('.cp-a-needs li')].map(row=>row.textContent.trim()),
    deadline:document.querySelector('.cp-a-deadline')?.textContent.trim()||null,
    next_step:document.querySelector('.cp-a-next h2')?.textContent.trim()||null,
  }));
  for(const width of widths){
    await page.setViewportSize({width,height:900});
    await page.screenshot({path:path.join(out,`${name}-${width}.png`)});
    const layout=await page.evaluate(()=>{
      const rail=document.querySelector('.cp-source-rail')?.getBoundingClientRect();
      const main=document.querySelector('.cp-a-main')?.getBoundingClientRect();
      return {overflow:document.documentElement.scrollWidth>innerWidth+1,railLeft:rail?.left,railTop:rail?.top,mainLeft:main?.left,mainBottom:main?.bottom};
    });
    if(layout.overflow||width>=901&&layout.railLeft>=layout.mainLeft||width<=900&&layout.railTop<layout.mainBottom-2)throw Error(`${name} ${width}px layout moved the source rail: ${JSON.stringify(layout)}`);
  }
  await page.setViewportSize({width:1440,height:900});
}
await page.goto(`${base}/#claim=${claims.flagship}`);
await page.locator('[data-what-if="family_home"]').first().click();
for(const verdict of ['false','true']){
  const started=performance.now();
  await page.locator(`[data-what-if-value="${verdict}"]`).click();
  await page.locator(`#cpWhatIfPanel [data-what-if-value="${verdict}"][aria-pressed="true"]`).waitFor();
  await page.locator('.cp-a-what-if-diff').waitFor({timeout:15000});
  timing[`what_if_${verdict}_ms`]=Math.round(performance.now()-started);
  const spouse=await page.locator('.cp-a-needs').innerText();
  if(verdict==='false'&&spouse.includes('Spouse notice copy')&&!spouse.includes('Not requested because'))throw Error('False family-home condition still requests spouse copy');
  if(verdict==='true'&&!spouse.includes('Spouse notice copy'))throw Error('True family-home condition omits spouse copy');
  if(verdict==='true'&&!(await page.locator('#cpWhatIfPanel').innerText()).includes('Art. 266n'))throw Error('Family-home diff omits Art. 266n');
}
await page.locator('[data-what-if-close]').click();
if(await page.locator('[data-evidence-choice]').count()){
  const date=page.locator('[data-evidence-choice]').filter({hasText:'30. Juni'}).first();
  const verdictStart=performance.now();
  await date.click();
  await page.locator('.cp-evidence-selected').waitFor({timeout:5000});
  timing.evidence_verdict_ms=Math.round(performance.now()-verdictStart);
  const started=performance.now();
  await page.locator('#cwLoopCommit').click();
  await page.locator('#cwReplanDelta').waitFor({timeout:45000});
  timing.evidence_receipt_ms=Math.round(performance.now()-started);
  await page.locator('#cwReplanDelta[data-accepted="true"]').waitFor({timeout:45000});
  timing.evidence_update_ms=Math.round(performance.now()-started);
  timing.evidence_requests=await page.evaluate(()=>performance.getEntriesByType('resource').filter(row=>row.name.includes('/loop/evidence')||row.name.includes('/loop/advance')||row.name.includes('/workspace/claims/clm_f69b1747447bc221')).slice(-20).map(row=>({path:new URL(row.name).pathname,duration_ms:Math.round(row.duration)})));
  if(!(await page.locator('#cwReplanDelta').innerText()).includes('30. Juni'))throw Error('Accepted PDF date is absent from the path update');
}
const queueAgain=performance.now();
await queue.reload();
await queue.locator('#cwTable tr[data-claim-id]').first().waitFor({timeout:30000});
timing.queue_after_write_ms=Math.round(performance.now()-queueAgain);
await fs.writeFile(path.join(out,'phase2-browser-results.json'),JSON.stringify({base,timing,outputs,errors},null,2)+'\n');
await browser.close();
if(errors.length)throw Error(`Browser errors: ${errors.join('; ')}`);
console.log(JSON.stringify({out,timing,errors}));
