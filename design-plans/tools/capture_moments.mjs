// Captures fixed moments of the Demonstration and two claims (GET-only). Usage: BASE=http://127.0.0.1:4180 node capture_moments.mjs <outdir> [asset=path ...]; set PLAYWRIGHT_CHROMIUM to your Chromium path.
// Usage: node moments.mjs <outdir> [asset=path ...]  (BASE env, default :4180). Captures fixed moments; GET-only.
import {createRequire} from 'node:module';
const {chromium} = createRequire(new URL('../../casepath-qa/package.json',import.meta.url))('playwright');
import fs from 'node:fs';
const [,, out, ...pairs] = process.argv; fs.mkdirSync(out,{recursive:true});
const ov = Object.fromEntries(pairs.map(p => p.split('=')));
const BASE = process.env.BASE || 'http://127.0.0.1:4180';
const b = await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM || undefined});
async function page(w,h){ const p = await b.newPage({viewport:{width:w,height:h}}); const errs=[];
  p.on('pageerror',e=>errs.push(e.message));
  await p.route('**/*', async r => { const q=r.request(), u=new URL(q.url());
    if (q.method()!=='GET'&&q.method()!=='HEAD') return r.abort('blockedbyclient');
    const n=u.pathname.split('/').pop();
    if (q.isNavigationRequest() && (u.pathname==='/'||u.pathname==='/index.html') && ov['index.html']) return r.fulfill({path:ov['index.html'],contentType:'text/html; charset=utf-8'});
    if (u.pathname.startsWith('/assets/') && ov[n]) return r.fulfill({path:ov[n],contentType:n.endsWith('.css')?'text/css':'text/javascript'});
    return r.continue(); });
  p.errs=errs; return p; }
const shots = [];
{ const p = await page(1440,900); await p.goto(BASE+'/#autonomous/demonstration',{waitUntil:'networkidle'});
  for (const [t,n] of [[6000,'demo-06s'],[10000,'demo-10s'],[12000,'demo-12s'],[18000,'demo-18s'],[24000,'demo-24s']]) { await p.waitForTimeout(t - (shots.length? +shots[shots.length-1].t:0)); await p.screenshot({path:`${out}/${n}.png`}); shots.push({t,n}); }
  console.log('demo errors', p.errs.slice(0,3)); await p.close(); }
for (const [n,r,w,h] of [['claim','#autonomous/claim/clm_543f08f2415b2a33',1440,900],['claim-docs','#autonomous/claim/clm_543f08f2415b2a33?detail=documents',1440,900],['claim-heating','#autonomous/claim/clm_314f2d309fea25e6',1440,900]]) {
  const p = await page(w,h); await p.goto(BASE+'/'+r,{waitUntil:'networkidle'}); await p.waitForTimeout(5000); await p.screenshot({path:`${out}/${n}.png`}); console.log(n, p.errs.slice(0,2)); await p.close(); }
{ const p = await page(390,844); await p.goto(BASE+'/#autonomous/demonstration',{waitUntil:'networkidle'}); await p.waitForTimeout(12000); await p.screenshot({path:`${out}/mobile-demo-12s.png`}); console.log('phone',p.errs); await p.close(); }
await b.close();
