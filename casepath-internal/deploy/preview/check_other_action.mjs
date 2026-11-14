// Browser check on the local preview (make preview): "andere Handlung" on case C (the handler workflow) is "ändern" beside
// the headline, one pick and one reason, and changes the draft and the follow-up date. Replace CASE_ID with case C.
const t = await taskSpace(0); const p = await t.newPage(); const sleep=ms=>new Promise(r=>setTimeout(r,ms));
await p.goto("http://127.0.0.1:8790/?lang=de#/case/CASE_ID/overview"); await sleep(3500);
const read = () => p.evaluate(() => ({ title: (document.querySelector(".cp-prepared h2") || {}).textContent,
  letter: [...document.querySelectorAll("[data-item='letter:0'] [data-seg]")].map((e) => e.innerText).join("\n").slice(0, 400),
  due: (document.querySelector("#followup-date") || {}).value }));
const at = (sel) => p.evaluate((s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }, sel);
const before = await read();
let actions = 0;
const change = await at("#change-action");
if (!change) { console.log("no 'ändern' on the screen; before: " + JSON.stringify(before)); process.exit(0); }
await p.mouse.click(change.x, change.y); actions++; await sleep(800);
const kinds = await p.evaluate(() => [...document.querySelectorAll("[data-pick-action]")].map((b) => b.dataset.pickAction));
const pick = await at(`[data-pick-action='${kinds.includes("A5") ? "A5" : kinds[0]}']`);
await p.mouse.click(pick.x, pick.y); actions++; await sleep(800);
const chip = await at("[data-action-reason]");
await p.mouse.click(chip.x, chip.y); actions++; await sleep(3000);
const after = await read();
console.log("options " + kinds.join(",") + " | actions " + actions + " (ändern, the action, its reason)");
console.log("before: " + before.title + " | due " + before.due);
console.log("after:  " + after.title + " | due " + after.due);
console.log("draft changed " + (after.letter !== before.letter) + " | date changed " + (after.due !== before.due));
await p.close();
