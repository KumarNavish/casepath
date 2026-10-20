import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const {chromium}=createRequire(new URL('../../casepath-qa/package.json',import.meta.url))('playwright');
const out=process.argv[2],base=process.env.BASE||'http://127.0.0.1:4173';
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH});
const errors=[],writes=[];
try {
 const page=await browser.newPage({viewport:{width:1440,height:900}});page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>{if(!['GET','HEAD'].includes(r.request().method())){writes.push(r.request().url());return r.abort();}return r.continue();});
 await page.goto(base+'/#autonomous/cases');
 await page.waitForFunction(()=>document.body.innerText.includes('Not started')&&document.body.innerText.includes('150'),{},{timeout:60000});
 const response=await page.request.get(base+'/api/claim-loops/v1/autonomous/claims');assert.ok(response.ok());
 const catalog=await response.json();assert.equal(catalog.total,150);assert.ok(catalog.claims.length>0);assert.ok(catalog.claims.every(c=>c.revision===0&&c.status==='not_started'));
 await page.screenshot({path:`${out}/empty-main.png`});assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
 fs.writeFileSync(`${out}/checks/empty-main.json`,JSON.stringify({status:'passed',total:catalog.total,returned:catalog.claims.length,allReturnedUnrun:true,errors,writes},null,2)+'\n');
} finally {await browser.close();}
