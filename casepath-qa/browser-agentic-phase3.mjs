import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright';

const base=(process.env.BASE_URL||'http://127.0.0.1:4173').replace(/\/$/,'');
const out=path.resolve(process.env.CASEPATH_QA_OUT||'/tmp/casepath-phase3-shots');
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
const timing={},outputs={};
const queueStarted=performance.now();
await queue.goto(base+'/');
await queue.locator('#cwTable tr[data-claim-id]').first().waitFor({timeout:30000});
timing.queue_first_paint_ms=Math.round(performance.now()-queueStarted);
if(!(await queue.locator('.cp-triage-group').count()))throw Error('Queue has no waiting-on groups');
if(!(await queue.locator('#cwSimilar').count()))throw Error('Condition-profile facet is missing');
for(const [name,claimId] of Object.entries(claims)){
  await page.goto(`${base}/#claim=${claimId}`);
  await page.locator('#cpReviewCard').waitFor({timeout:30000});
  if(await page.locator('#cwStart').count()){
    const started=performance.now();
    await page.locator('#cwStart').click();
    await page.locator('.aw-narrative-lines li button').first().waitFor({timeout:30000});
    timing[`${name}_first_line_ms`]=Math.round(performance.now()-started);
    await page.locator('.cp-a-review-ready[data-status="completed"]').waitFor({state:'visible',timeout:45000});
    timing[`${name}_review_complete_ms`]=Math.round(performance.now()-started);
  }
  await page.locator('.cp-a-path').waitFor({timeout:30000});
  const draftStarted=performance.now();
  await page.locator('#cwDraftOpen').click();
  await page.locator('#cpDraftPanel').waitFor({timeout:20000});
  timing[`${name}_draft_ms`]=Math.round(performance.now()-draftStarted);
  const draft=await page.locator('#cwDraftBody').inputValue();
  if(!draft.trim())throw Error(`${name} draft is empty`);
  if(name==='mould'&&!draft.includes('Mein Sohn hustet mehr'))throw Error('German handoff lost the customer quote');
  outputs[name]=await page.evaluate(()=>({
    noticed:[...document.querySelectorAll('.cp-a-noticed li')].map(row=>row.textContent.trim()),
    conditions:[...document.querySelectorAll('.cp-a-condition')].map(row=>row.textContent.trim()),
    path:[...document.querySelectorAll('.cp-a-path li[data-path-state]')].map(row=>({state:row.dataset.pathState,text:row.querySelector('strong')?.textContent.trim()})),
    needs:[...document.querySelectorAll('.cp-a-needs li')].map(row=>row.textContent.trim()),
    deadline:document.querySelector('.cp-a-deadline')?.textContent.trim()||null,
    next_step:document.querySelector('.cp-a-next h2')?.textContent.trim()||null,
    draft:document.querySelector('#cwDraftBody')?.value||null,
  }));
  for(const width of widths){
    await page.setViewportSize({width,height:900});
    await page.evaluate(()=>{scrollTo(0,0);const column=document.querySelector('.cp-work-column');if(column)column.scrollTop=0;});
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
await queue.reload();
await queue.locator('#cwTable tr[data-claim-id]').first().waitFor({timeout:30000});
const flagshipRow=queue.locator(`tr[data-claim-id="${claims.flagship}"]`);
if(!(await flagshipRow.innerText()).includes('Draft, not sent'))throw Error('Queue omits the saved draft');
await queue.locator('.cp-filter-popover summary').click();
const profiles=await queue.locator('#cwSimilar option').count();
if(profiles<3)throw Error('Queue has no claim-specific condition profiles');
await queue.locator('.cp-filter-popover summary').click();
await page.goto(`${base}/#claim=${claims.flagship}`);
await page.locator('[data-what-if="family_home"]').first().click();
await page.locator('[data-what-if-value="true"]').click();
await page.locator('.cp-a-what-if-diff').waitFor({timeout:15000});
await page.locator('#cwHandlerConditionForm textarea').fill('I checked the spouse notice and the quoted statement.');
await page.locator('#cwHandlerConditionForm button[type="submit"]').click();
await page.locator('[data-keep-memory]').waitFor({timeout:20000});
await page.locator('[data-keep-memory] input[name="handler"]').fill('Navish');
const keptAt=performance.now();
await page.locator('[data-keep-memory] button[type="submit"]').click();
await page.getByText('Reviewed memory saved for matching claims.').waitFor({timeout:20000});
timing.memory_keep_ms=Math.round(performance.now()-keptAt);
await page.goto(`${base}/#claim=clm_478488eeea2665d7`);
await page.locator('#cpReviewCard').waitFor({timeout:30000});
if(await page.locator('#cwStart').count()){
  await page.locator('#cwStart').click();
  await page.locator('.cp-a-review-ready[data-status="completed"]').waitFor({state:'visible',timeout:45000});
}
const memoryStarted=performance.now();
await page.locator('.cp-reviewed-memory [data-apply-memory]').waitFor({timeout:20000});
timing.memory_match_ms=Math.round(performance.now()-memoryStarted);
await page.screenshot({path:path.join(out,'reviewed-memory-1440.png')});
await page.locator('[data-apply-memory] textarea').fill('I verified this claim against the separate spouse notice.');
await page.locator('[data-apply-memory] button[type="submit"]').click();
await page.getByText('Handler assessment recorded from this memory.').waitFor({timeout:20000});
await queue.reload();
await queue.locator('#cwTable tr[data-claim-id]').first().waitFor({timeout:30000});
const afterWrite=performance.now();
const response=await queue.evaluate(async()=>{const start=performance.now();const result=await fetch('/api/claim-loops/v1/workspace/claims?limit=100');return {status:result.status,elapsed:performance.now()-start};});
timing.cached_queue_api_ms=Math.round(response.elapsed);
if(response.status!==200)throw Error(`Queue API returned ${response.status}`);
timing.queue_probe_wall_ms=Math.round(performance.now()-afterWrite);
await fs.writeFile(path.join(out,'phase3-browser-results.json'),JSON.stringify({base,timing,outputs,errors},null,2)+'\n');
await browser.close();
if(errors.length)throw Error(`Browser errors: ${errors.join('; ')}`);
console.log(JSON.stringify({out,timing,errors}));
