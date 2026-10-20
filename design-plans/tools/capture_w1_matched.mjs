// Match the recorded checker/document/quote in the supplied baseline frame.
import {createRequire} from 'node:module';
const {chromium}=createRequire(new URL('../../casepath-qa/package.json',import.meta.url))('playwright');
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH});
try {
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 await page.route('**/*',r=>['GET','HEAD'].includes(r.request().method())?r.continue():r.abort());
 await page.goto((process.env.BASE||'http://127.0.0.1:4180')+'/#autonomous/demonstration');
 await page.waitForFunction(()=>{
  const passage=document.querySelector('.au-operation-passage'),now=document.querySelector('.au-stage-source .au-now');
  return passage?.closest('.au-stage-source')?.innerText.includes('Heating service report') && passage.querySelector('[data-au-operation-span]')?.textContent==='15.8C' && now?.innerText.includes('checks this document');
 },{},{timeout:60000});
 await page.screenshot({path:process.argv[2]});
} finally {await browser.close();}
