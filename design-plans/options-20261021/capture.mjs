import {createRequire} from 'node:module';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=createRequire(new URL('../../casepath-qa/package.json',import.meta.url))('playwright');
const root=path.dirname(fileURLToPath(import.meta.url)),base=process.env.BASE||'http://127.0.0.1:4180';
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const audit=()=>{
 const all=[...document.querySelectorAll('main *,header *,section.case *,footer *')];
 const els=all.filter(e=>{if(e.closest('svg,dialog,[hidden]')||e.closest('details:not([open])')&&!e.closest('summary'))return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();if(s.visibility==='hidden'||s.display==='none'||+s.opacity===0||r.width<4||r.height<4||r.bottom<0||r.top>innerHeight)return false;const clip=e.closest('.scroll');if(clip){const q=clip.getBoundingClientRect();if(r.bottom<=q.top||r.top>=q.bottom)return false;}return s.borderTopStyle!=='none'&&parseFloat(s.borderTopWidth)>0||(s.backgroundColor!=='rgba(0, 0, 0, 0)'&&s.backgroundColor!=='transparent')||[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim());});
 const hits=[];for(let i=0;i<els.length;i++)for(let j=i+1;j<els.length;j++){const a=els[i],b=els[j];if(a.contains(b)||b.contains(a))continue;const rect=e=>{const r=e.getBoundingClientRect(),clip=e.closest('.scroll');if(!clip)return r;const c=clip.getBoundingClientRect();return {left:Math.max(r.left,c.left),right:Math.min(r.right,c.right),top:Math.max(r.top,c.top),bottom:Math.min(r.bottom,c.bottom)};},r=rect(a),q=rect(b),x=Math.min(r.right,q.right)-Math.max(r.left,q.left),y=Math.min(r.bottom,q.bottom)-Math.max(r.top,q.top);if(x>2&&y>2)hits.push([a.className,b.className,Math.round(x),Math.round(y)]);}return hits;
};
const report={sourceSha256:Object.fromEntries(['A','B','C'].map(letter=>[letter,createHash('sha256').update(fs.readFileSync(path.join(root,letter,'desk.html'))).digest('hex')])),viewport:{width:1440,height:900},frames:{},errors:[],writes:[]};
for(const letter of ['A','B','C']){
 const page=await browser.newPage({viewport:report.viewport});page.on('pageerror',e=>report.errors.push(`${letter}: ${e.message}`));
 await page.route('**/*',r=>{const req=r.request();if(!['GET','HEAD'].includes(req.method())){report.writes.push(req.method()+' '+req.url());return r.abort();}if(new URL(req.url()).pathname==='/design-desk.html')return r.fulfill({path:path.join(root,letter,'desk.html'),contentType:'text/html; charset=utf-8'});return r.continue();});
 for(const [frame,idx,mode] of [['work',1,'work'],['case1-result',1,'result'],['case4-result',4,'result']]){
  await page.goto(`${base}/design-desk.html?case=${idx}&frame=${mode}`,{waitUntil:'networkidle'});await page.waitForFunction(()=>document.body.dataset.ready==='true');await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(100);
  const name=`${letter}-${frame}`;await page.screenshot({path:path.join(root,letter,name+'.png')});report.frames[name]={snapshot:await page.evaluate(()=>window.designStudy.snapshot()),overlaps:await page.evaluate(audit),horizontalOverflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),thread:await page.locator('#thread path').count(),resultBottom:await page.locator('.result').count()?await page.locator('.result').evaluate(e=>e.getBoundingClientRect().bottom):null};console.log(name,JSON.stringify(report.frames[name]));
 }
 await page.close();
}
fs.writeFileSync(path.join(root,'capture-receipt.json'),JSON.stringify(report,null,2));await browser.close();
