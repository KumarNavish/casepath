// Browser check on the local preview (make preview): "Unterlage hinzufügen" takes at most two actions and the line is ticked
// at once. Run with the ego-browser runtime against a prepared synthetic case; replace CASE_ID with its id.
const t = await taskSpace(0); const p = await t.newPage(); const sleep=ms=>new Promise(r=>setTimeout(r,ms));
await p.goto("http://127.0.0.1:8790/?lang=de#/case/${process.argv[2] || "CASE_ID"}/overview"); await sleep(3500);
const box = async (sel) => p.evaluate((s) => { const e = document.querySelector(s); if (!e) return null; e.scrollIntoView({block: "center"}); const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }, sel);
let actions = 0;
const field = await box("#add-doc"); if (!field) { console.log("no add-doc field"); process.exit(0); }
await p.mouse.click(field.x, field.y); await p.keyboard.type("Wohnungsabnahmeprotokoll"); await p.keyboard.press("Enter"); actions++; await sleep(1500);
const chip = await box("[data-add-doc-reason]"); await p.mouse.click(chip.x, chip.y); actions++; await sleep(2500);
const ticked = await p.evaluate(() => [...document.querySelectorAll(".cp-checklist li")].some((li) => li.textContent.includes("Wohnungsabnahmeprotokoll") && (li.querySelector("input[type=checkbox]") || {}).checked));
const inLetter = await p.evaluate(() => (document.querySelector("pre[data-item='letter:0']") || {}).innerText?.includes("Wohnungsabnahmeprotokoll") || false);
console.log("actions " + actions + " · ticked in the checklist " + ticked + " · in the letter " + inLetter);
await p.close();
