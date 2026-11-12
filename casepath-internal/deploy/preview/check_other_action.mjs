// Browser check on the local preview (make preview): "andere Handlung" on case C (the handler workflow) takes two actions
// and changes the draft and the follow-up date. Replace CASE_ID with case C from the preview line.
const t = await taskSpace(0); const p = await t.newPage(); const sleep=ms=>new Promise(r=>setTimeout(r,ms));
await p.goto("http://127.0.0.1:8790/?lang=de#/case/CASE_ID/overview"); await sleep(3500);
const read = () => p.evaluate(() => ({ title: (document.querySelector(".cp-prepared h2") || {}).textContent, letter: ((document.querySelector("pre[data-item='letter:0']") || {}).innerText || "").slice(0, 400),
  due: (document.querySelector("#followup-date") || {}).value, greeting: ((document.querySelector("pre[data-item='letter:0']") || {}).innerText || "").split("\n").find((l) => l.startsWith("Sehr geehrte")) }));
const before = await read();
let actions = 0;
const sel = await p.evaluate(() => { const e = document.querySelector("#other-action"); if (!e) return null; e.scrollIntoView({block: "center"}); return [...e.options].map((o) => o.value).filter(Boolean); });
if (!sel) { console.log("no chooser on the screen; before: " + JSON.stringify(before)); process.exit(0); }
await p.evaluate((v) => { const e = document.querySelector("#other-action"); e.value = v; e.dispatchEvent(new Event("change")); }, sel.includes("A5") ? "A5" : sel[0]); actions++;
await sleep(1200);
const chip = await p.evaluate(() => { const e = document.querySelector("[data-action-reason]"); e.scrollIntoView({block: "center"}); const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; });
await p.mouse.click(chip.x, chip.y); actions++; await sleep(3000);
const after = await read();
console.log("options " + sel.join(",") + " | actions " + actions);
console.log("before: " + before.title + " | due " + before.due + " | " + before.greeting);
console.log("after:  " + after.title + " | due " + after.due);
console.log("draft changed " + (after.letter !== before.letter) + " | date changed " + (after.due !== before.due));
await p.close();
