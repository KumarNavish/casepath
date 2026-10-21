import {chromium} from '/opt/node22/lib/node_modules/playwright/index.mjs';
const [,, out='/tmp/claude-0/desk/shots', query='', ...times] = process.argv;
import fs from 'node:fs'; fs.mkdirSync(out,{recursive:true});
const b = await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome'});
const p = await b.newPage({viewport:{width:1440,height:900}}); const errs=[]; p.on('pageerror',e=>errs.push(e.message));
await p.route('**/desk.html*', r => r.fulfill({path:'/tmp/claude-0/desk/desk.html',contentType:'text/html; charset=utf-8'}));
await p.goto('http://127.0.0.1:4180/desk.html'+query); let t0=0;
for (const t of (times.length?times:['4','9','14','20','26','34']).map(Number)) { await p.waitForTimeout((t-t0)*1000); t0=t; await p.screenshot({path:`${out}/t${String(t).padStart(2,'0')}.png`}); }
console.log('errors', errs.slice(0,3)); await b.close();
