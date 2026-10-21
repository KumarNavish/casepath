// Desktop calm-layout audit: captures frames and reports overlapping visible boxes/text. GET-only.
// Usage: BASE=... node overlaps.mjs <outdir> [asset=path ...]
import {createRequire} from 'node:module';
const {chromium}=createRequire(new URL('../../casepath-qa/package.json',import.meta.url))('playwright');
import fs from 'node:fs';
const [,, out, ...pairs] = process.argv; fs.mkdirSync(out,{recursive:true});
const ov = Object.fromEntries(pairs.map(p => p.split('=')));
const BASE = process.env.BASE || 'http://127.0.0.1:4180';
const b = await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM || undefined});
const audit = () => {
  const els = [...document.querySelectorAll('main *, .au-workspace *')].filter(e => {
    const s = getComputedStyle(e); if (s.visibility === 'hidden' || s.display === 'none' || +s.opacity === 0) return false;
    const r = e.getBoundingClientRect(); if (r.width < 4 || r.height < 4 || r.bottom < 0 || r.top > innerHeight) return false;
    const boxed = s.borderTopStyle !== 'none' && parseFloat(s.borderTopWidth) > 0 || (s.backgroundColor !== 'rgba(0, 0, 0, 0)' && s.backgroundColor !== 'transparent');
    const leafText = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    return boxed || leafText; });
  const name = e => (e.className && typeof e.className === 'string' ? '.'+e.className.trim().split(/\s+/)[0] : e.tagName.toLowerCase()) + ' "' + (e.textContent||'').trim().replace(/\s+/g,' ').slice(0,28) + '"';
  const hits = [];
  for (let i=0;i<els.length;i++) for (let j=i+1;j<els.length;j++) {
    const a=els[i], c=els[j]; if (a.contains(c) || c.contains(a)) continue;
    const r=a.getBoundingClientRect(), q=c.getBoundingClientRect();
    const x=Math.min(r.right,q.right)-Math.max(r.left,q.left), y=Math.min(r.bottom,q.bottom)-Math.max(r.top,q.top);
    if (x>2 && y>2) hits.push(`${name(a)}  ×  ${name(c)}  (${Math.round(x)}×${Math.round(y)})`); }
  return [...new Set(hits)].slice(0,25); };
const p = await b.newPage({viewport:{width:1440,height:900}});
await p.route('**/*', async r => { const q=r.request(), u=new URL(q.url()); if (q.method()!=='GET'&&q.method()!=='HEAD') return r.abort();
  const n=u.pathname.split('/').pop();
  if (q.isNavigationRequest() && (u.pathname==='/'||u.pathname==='/index.html') && ov['index.html']) return r.fulfill({path:ov['index.html'],contentType:'text/html; charset=utf-8'});
  if (u.pathname.startsWith('/assets/') && ov[n]) return r.fulfill({path:ov[n],contentType:n.endsWith('.css')?'text/css':'text/javascript'});
  return r.continue(); });
const report = {};
await p.goto(BASE+'/#autonomous/demonstration',{waitUntil:'networkidle'});
let t0 = 0;
for (const t of [3,7,11,15,19,24,30]) { await p.waitForTimeout((t-t0)*1000); t0=t; await p.screenshot({path:`${out}/demo-${String(t).padStart(2,'0')}s.png`}); report[`demo-${t}s`] = await p.evaluate(audit); }
for (const [n,r] of [['claim-rent','#autonomous/claim/clm_543f08f2415b2a33'],['claim-heating','#autonomous/claim/clm_314f2d309fea25e6'],['claim-docs','#autonomous/claim/clm_543f08f2415b2a33?detail=documents'],['knowledge','#autonomous/knowledge'],['cases','#autonomous/collection']]) {
  await p.goto(BASE+'/'+r,{waitUntil:'networkidle'}); await p.waitForTimeout(4000); await p.screenshot({path:`${out}/${n}.png`}); report[n] = await p.evaluate(audit); }
fs.writeFileSync(`${out}/overlaps.json`, JSON.stringify(report,null,1));
for (const [k,v] of Object.entries(report)) console.log(k, v.length);
await b.close();
