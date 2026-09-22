import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const out=process.argv[2], base='http://127.0.0.1:4173';
const claim='clm_731b214dde882f89';
await fs.mkdir(path.join(out,'screenshots'),{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
const errors=[],steps=[];
page.on('pageerror',e=>errors.push(e.message));
async function shot(name){await page.screenshot({path:path.join(out,'screenshots',name+'.png'),fullPage:false});}
async function save(name,url){const r=await page.request.get(base+url); const value=await r.json();await fs.writeFile(path.join(out,name+'.json'),JSON.stringify({status:r.status(),value},null,2));return value;}
try{
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.locator('#cwTable [data-claim-id]').first().waitFor({timeout:90000});
  assert.match(await page.title(),/CasePath/);steps.push('Real queue rendered');
  await shot('01-queue');
  await save('queue','/api/claim-loops/v1/workspace/claims?limit=200');
  await page.goto(base+'/#claim='+claim,{waitUntil:'domcontentloaded'});
  await page.locator('#cwStart').waitFor({timeout:90000});
  await shot('02-customer-packet');
  await save('detail-before','/api/claim-loops/v1/workspace/claims/'+claim);
  const attachment=page.locator('.cp-source-rail [data-source-artifact]').first();
  if(await attachment.count()){
    await attachment.click();
    await page.locator('.cp-preview-page').waitFor({timeout:30000});
    await shot('03-original-attachment');steps.push('Original image opened through verified preview');
  }
  await page.locator('#cwStart').click();
  await page.waitForFunction(()=>document.querySelector('#awClaimWork')?.dataset.status==='completed',{},{timeout:120000});
  steps.push('Real deterministic agent review completed');
  await shot('04-agent-review-complete');
  await save('detail-after','/api/claim-loops/v1/workspace/claims/'+claim);
  await save('loop','/api/claim-loops/v1/workspace/claims/'+claim+'/loop');
  const runs=await save('runs','/api/agent-work/v1/claims/'+claim+'/runs');
  await page.locator('#cpTab-process').click();await shot('05-process');
  await page.locator('#cpTab-evidence').click();await shot('06-evidence');
  const why=page.locator('[data-evidence-source]').filter({visible:true}).first();
  if(await why.count()){await why.click();await shot('07-why-this-evidence');steps.push('Evidence rationale opened');}
  await page.locator('#cpTab-activity').click();await shot('08-recorded-work');
  await page.reload({waitUntil:'domcontentloaded'});
  await page.locator('#cpTab-overview').waitFor({timeout:60000});
  await page.locator('#cpTab-overview').click();steps.push('Saved claim survived reload');
  await page.setViewportSize({width:390,height:844});await shot('09-mobile');
  await fs.writeFile(path.join(out,'dom.html'),await page.content());
  await fs.writeFile(path.join(out,'browser-result.json'),JSON.stringify({steps,errors,runs,viewport:[1440,1000],mobile:[390,844],scope:'Actual deterministic product on a disposable GitHub runner; no model or benchmark execution'},null,2));
  assert.equal(errors.length,0,'Browser runtime errors');
} catch(e){await shot('failure');await fs.writeFile(path.join(out,'browser-result.json'),JSON.stringify({steps,errors,failure:e.stack},null,2));throw e;}
finally{await browser.close();}
