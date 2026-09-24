import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright';

const base=(process.env.BASE_URL||'http://127.0.0.1:4173').replace(/\/$/,'');
const out=path.resolve(process.env.CASEPATH_QA_OUT||'/tmp/casepath-phase4-shots');
const executablePath=process.env.PLAYWRIGHT_EXECUTABLE_PATH||'/Applications/ego lite.app/Contents/MacOS/ego lite';
const claims={flagship:'clm_f69b1747447bc221',mould:'clm_7ac806bd30792cfb',rent:'clm_6f04d0907ecb96bb'};
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath});
const context=await browser.newContext({viewport:{width:1440,height:900}});
const queue=await context.newPage(),page=await context.newPage(),errors=[];
for(const tab of [queue,page])tab.on('pageerror',error=>errors.push(error.message));
const timing={},outputs={};
const started=performance.now();
await queue.goto(base+'/');
await queue.locator('#cwTable tr[data-claim-id]').first().waitFor({timeout:30000});
timing.queue_first_paint_ms=Math.round(performance.now()-started);
await queue.locator('#cpFirstRun').waitFor();
if(!(await queue.locator('#cpFirstRun').isVisible()))throw Error('First-run card is not visible');
await queue.screenshot({path:path.join(out,'first-run-1440.png')});
const flagshipOpen=performance.now();
await queue.locator('[data-start-tour]').click();
await queue.locator('#cpGuidedWalk').waitFor({timeout:30000});
timing.flagship_claim_open_ms=Math.round(performance.now()-flagshipOpen);
if(!(await queue.locator('#cpGuidedWalk').innerText()).includes('Step 1 of 5'))throw Error('Walk did not start at sources');
await queue.locator('[data-guide-next]').click();
let flagshipReviewStart=null;
if(await queue.locator('#cwStart').count()){
  const review=flagshipReviewStart=performance.now();
  await queue.locator('#cwStart').click();
  await queue.locator('.aw-narrative-lines li button').first().waitFor({timeout:30000});
  timing.flagship_first_line_ms=Math.round(performance.now()-review);
}
await queue.locator('.cp-a-review-ready[data-status="completed"]').waitFor({state:'visible',timeout:45000});
if(flagshipReviewStart!==null)timing.flagship_review_complete_ms=Math.round(performance.now()-flagshipReviewStart);
await queue.locator('[data-guide-next]').click();
await queue.locator('#cpGuidedWalk').getByText('See what is needed').waitFor();
for(const [flag,verdict] of [['termination_received','true'],['family_home','true'],['arrears','unresolved'],['retaliation_screen','unresolved'],['extension_relevant','true']]){
  if(await queue.locator(`.cp-a-condition-overview [data-condition-flag="${flag}"][data-condition-verdict="${verdict}"]`).count()!==1)throw Error(`Flagship condition ${flag} is missing`);
}
await queue.locator('[data-guide-next]').click();
await queue.locator('[data-what-if="family_home"]').first().click();
await queue.locator('[data-what-if-value="false"]').click();
await queue.locator('.cp-a-what-if-diff').waitFor({timeout:15000});
await queue.locator('[data-guide-next]').click();
await queue.locator('#cwDraftOpen').click();
await queue.locator('#cpDraftPanel').waitFor({timeout:20000});
await queue.locator('[data-guide-finish]').click();
if(await queue.locator('#cpGuidedWalk').count())throw Error('Walk did not finish');
await queue.locator('#cpClaimMenu summary').click();
await queue.locator('#cpClaimMenu [data-reviewer-toggle]').click();
await queue.locator('#cpReviewerPanel').waitFor();
for(const selector of ['.cp-source-rail','.cp-a-review','.cp-a-condition-overview li','.cp-a-path li[data-path-state]','.cp-a-needs li','.cp-a-why li','.cp-a-draft']){
  const item=queue.locator(selector).first();if(!await item.getAttribute('data-provenance'))throw Error(`Reviewer label missing on ${selector}`);
}
if(!(await queue.locator('#cpReviewerPanel').innerText()).includes('Study A · paired V5'))throw Error('Study correspondence is missing');
await queue.evaluate(()=>{document.querySelector('.cp-work-column').scrollTop=0;document.querySelector('#cwDetailPanel').scrollTop=0;window.scrollTo(0,0);});
await queue.screenshot({path:path.join(out,'reviewer-1440.png')});
await queue.locator('#cpClaimMenu summary').click();
await queue.locator('#cpClaimMenu [data-reviewer-toggle]').click();
await page.goto(base+'/method.html');
if(!(await page.getByRole('heading',{name:'Try the family-home claim'}).count()))throw Error('About page still uses the invented case');
await page.screenshot({path:path.join(out,'about-1440.png')});
await page.getByRole('link',{name:/Open the claim's What if/}).click();
await page.locator('#cpWhatIfPanel').waitFor({timeout:30000});
for(const [name,claimId] of Object.entries(claims)){
  await page.goto('about:blank');
  const opened=performance.now();
  await page.goto(`${base}/#claim=${claimId}`);
  await page.locator('#cpReviewCard').waitFor({timeout:30000});
  timing[`${name}_claim_open_ms`]=Math.round(performance.now()-opened);
  if(await page.locator('#cwStart').count()){
    const review=performance.now();await page.locator('#cwStart').click();
    await page.locator('.aw-narrative-lines li button').first().waitFor({timeout:30000});
    timing[`${name}_first_line_ms`]=Math.round(performance.now()-review);
    await page.locator('.cp-a-review-ready[data-status="completed"]').waitFor({state:'visible',timeout:45000});
    timing[`${name}_review_complete_ms`]=Math.round(performance.now()-review);
  }
  if(name==='mould')for(const [flag,verdict] of [['health_effects','true'],['mold','true'],['heating','unresolved'],['specialist_needed','unresolved'],['deposit_considered','unresolved']]){
    if(await page.locator(`.cp-a-condition-overview [data-condition-flag="${flag}"][data-condition-verdict="${verdict}"]`).count()!==1)throw Error(`Mould condition ${flag} is missing`);
  }
  outputs[name]=await page.evaluate(()=>({
    noticed:[...document.querySelectorAll('.cp-a-noticed li')].map(row=>row.textContent.trim()),
    conditions:[...document.querySelectorAll('.cp-a-condition-overview li')].map(row=>({flag:row.dataset.conditionFlag,verdict:row.dataset.conditionVerdict,text:row.textContent.trim()})),
    path:[...document.querySelectorAll('.cp-a-path li[data-path-state]')].map(row=>({state:row.dataset.pathState,text:row.querySelector('strong')?.textContent.trim()})),
    needs:[...document.querySelectorAll('.cp-a-needs li')].map(row=>row.textContent.trim()),
    deadline:document.querySelector('.cp-a-deadline')?.textContent.trim()||null,
    next_step:document.querySelector('.cp-a-next h2')?.textContent.trim()||null,
  }));
  if(name==='mould'&&!await page.locator('.cp-claim-title h1[lang="de"]').count())throw Error('German subject has no language mark');
  await page.evaluate(()=>{document.querySelector('#cwDetailPanel').scrollTop=0;window.scrollTo(0,0);});
  for(const width of [1440,1024,390,320]){
    await page.setViewportSize({width,height:900});
    await page.screenshot({path:path.join(out,`${name}-${width}.png`)});
    const layout=await page.evaluate(()=>{
      const source=document.querySelector('.cp-source-rail')?.getBoundingClientRect(),main=document.querySelector('.cp-a-main')?.getBoundingClientRect();
      return {overflow:document.documentElement.scrollWidth>innerWidth+1,sourceLeft:source?.left,sourceTop:source?.top,mainLeft:main?.left,mainBottom:main?.bottom};
    });
    if(layout.overflow||width>=901&&layout.sourceLeft>=layout.mainLeft||width<=900&&layout.sourceTop<layout.mainBottom-2)throw Error(`${name} ${width}px source layout: ${JSON.stringify(layout)}`);
  }
  await page.setViewportSize({width:1440,height:900});
  await page.reload();
  await page.locator('.cp-a-condition-overview li').first().waitFor({timeout:30000});
  const restored=await page.locator('.cp-a-condition-overview li').count();
  if(restored!==outputs[name].conditions.length)throw Error(`${name} review changed after reload`);
}
const cached=await queue.evaluate(async()=>{const start=performance.now();const response=await fetch('/api/claim-loops/v1/workspace/claims?limit=100');await response.arrayBuffer();return {status:response.status,elapsed:performance.now()-start};});
timing.cached_queue_api_ms=Math.round(cached.elapsed);
if(cached.status!==200)throw Error(`Queue API ${cached.status}`);
await fs.writeFile(path.join(out,'phase4-browser-results.json'),JSON.stringify({base,timing,outputs,errors},null,2)+'\n');
await browser.close();
if(errors.length)throw Error(`Browser errors: ${errors.join('; ')}`);
console.log(JSON.stringify({out,timing,errors}));
