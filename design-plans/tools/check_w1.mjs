// W1 regression against the isolated seeded preview. No API writes are allowed.
// BASE=http://127.0.0.1:4180 PLAYWRIGHT_EXECUTABLE_PATH=/path/to/chrome node design-plans/tools/check_w1.mjs <output-directory>
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const {chromium} = createRequire(new URL('../../casepath-qa/package.json',import.meta.url))('playwright');
const out = process.argv[2]; assert.ok(out); fs.mkdirSync(out,{recursive:true});
fs.rmSync(`${out}/checks.json`,{force:true});
const browser = await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined});
const results=[];
try {
  for (const width of [1440,390]) {
    const page=await browser.newPage({viewport:{width,height:width===390?844:900}}), errors=[],writes=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',route=>{
      if (!['GET','HEAD'].includes(route.request().method())) { writes.push(route.request().url()); return route.abort(); }
      const asset=new URL(route.request().url()).pathname.split('/').pop();
      if(process.env.W1_ASSET_ROOT && ['autonomous-workspace-v1.js','autonomous-workspace-v1.css','autonomous-language-v1.js'].includes(asset)) return route.fulfill({path:process.env.W1_ASSET_ROOT+'/'+asset,contentType:asset.endsWith('.css')?'text/css':'text/javascript'});
      return route.continue();
    });
    await page.addInitScript(()=>{
      window.w1={samples:0,tokens:0,maxTokenWidth:0,maxTokenHeight:0,maxChipHeight:0,minHeadingClearance:Infinity,overflow:0,maxAnimations:0,duplicateControls:0,upcomingContent:0};
      setInterval(()=>{
        const stage=document.querySelector('.au-operation-stage'), title=document.querySelector('[data-au-claim-title]');
        if (!stage || !title || stage.dataset.auStagePhase!=='source') return;
        const m=window.w1; m.samples++;
        const header=document.querySelector('.au-identity-header')?.getBoundingClientRect();
        m.minHeadingClearance=Math.min(m.minHeadingClearance,title.getBoundingClientRect().top-Math.max(0,header?.bottom||0));
        m.maxAnimations=Math.max(m.maxAnimations,document.getAnimations().filter(a=>a.playState==='running' && a.effect?.target?.closest('[data-au-canvas]')).length);
        const visible=e=>e.getClientRects().length>0;
        for(const selector of ['[data-au-demo-stop]','[data-au-demo-skip]','[data-au-inspect=demo]','[data-au-detail=activity]']) m.duplicateControls=Math.max(m.duplicateControls,Math.max(0,[...document.querySelectorAll(selector)].filter(visible).length-1));
        m.upcomingContent=Math.max(m.upcomingContent,[...document.querySelectorAll('.au-stage-step:not([data-au-stage-active=true]):not([data-au-stage-complete=true]) .au-stage-fact,.au-stage-step:not([data-au-stage-active=true]):not([data-au-stage-complete=true]) .au-stage-documents')].filter(visible).length);
        m.overflow=Math.max(m.overflow,document.documentElement.scrollWidth-innerWidth);
        for(const chip of document.querySelectorAll('.au-stage-fact'))m.maxChipHeight=Math.max(m.maxChipHeight,chip.getBoundingClientRect().height);
        for(const token of document.querySelectorAll('.au-operation-fact-token')) {
          m.tokens++; m.maxTokenWidth=Math.max(m.maxTokenWidth,token.offsetWidth);m.maxTokenHeight=Math.max(m.maxTokenHeight,token.offsetHeight);
        }
      },50);
    });
    await page.goto((process.env.BASE||'http://127.0.0.1:4180')+'/#autonomous/demonstration');
    await page.waitForSelector('.au-operation-stage[data-au-stage-phase="map"]',{timeout:120000});
    const metrics=await page.evaluate(()=>window.w1);
    const why=page.locator('.au-stage-outcome > details.au-outcome-why');await why.waitFor();
    assert.equal(await why.getAttribute('open'),null,'supporting answer detail starts closed');
    assert.equal(await page.locator('.au-stage-outcome > p').count(),3,'exactly three primary answer rows');
    await why.locator('summary').click();assert.ok(await why.locator('[data-au-outcome-recorded]').isVisible(),'the full recorded answer remains one click away');
    await why.locator('summary').click();
    await page.screenshot({path:`${out}/w1-${width}-result.png`});
    fs.writeFileSync(`${out}/metrics-${width}.json`,JSON.stringify({width,metrics,errors,writes},null,2)+'\n');
    assert.ok(metrics.samples>0);assert.ok(metrics.tokens>0,'recorded source-to-fact transfers were exercised');
    assert.ok(metrics.maxTokenWidth<=16 && metrics.maxTokenHeight<=2,JSON.stringify(metrics));
    assert.ok(metrics.maxChipHeight<=45,'fact chips stay compact');
    if(width===1440) assert.ok(metrics.minHeadingClearance>=-1,`case title remains visible: ${JSON.stringify(metrics)}`);
    assert.equal(metrics.maxAnimations,1,'the passage and transfer never animate concurrently');assert.equal(metrics.duplicateControls,0);assert.equal(metrics.upcomingContent,0);assert.equal(metrics.overflow,0);assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
    results.push({width,metrics,errors,writes});await page.close();
  }
  fs.writeFileSync(`${out}/checks.json`,JSON.stringify({status:'passed',results},null,2)+'\n');
  console.log(JSON.stringify(results));
} finally { await browser.close(); }
