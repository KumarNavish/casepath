// Browser check on the local preview (make preview); replace CASE_ID with a prepared synthetic case.
// Every checklist line and every "weil" fact opens its source (page and sentence) or its rule in one click.
const t = await taskSpace(0); const p = await t.newPage(); const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const url = "http://127.0.0.1:8790/?lang=de#/case/CASE_ID/overview";
await p.goto(url); await sleep(3500);
const targets = await p.evaluate(() => {
  const L = [...document.querySelectorAll(".cp-checklist li.cp-line")].map((li, n) => ({ what: "line " + n, sel: li.querySelector("[data-cite-file]") ? "cite" : li.querySelector("[data-step-link]") ? "rule" : null, n }));
  const weil = [...document.querySelectorAll(".cp-prepared p")].find((x) => x.textContent.startsWith("Weil"));
  const W = weil ? [...weil.querySelectorAll("button, a")].map((a, n) => ({ what: "weil " + a.textContent.trim().slice(0, 30), n })) : [];
  return { lines: L, weil: W };
});
const results = [];
for (const l of targets.lines) {
  await p.goto(url); await sleep(2500);
  const b = await p.evaluate((n) => { const li = document.querySelectorAll(".cp-checklist li.cp-line")[n]; const el = li.querySelector("[data-cite-file], [data-step-link]"); if (!el) return null; el.scrollIntoView({block: "center"}); const r = el.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }, l.n);
  if (!b) { results.push(l.what + ": FAIL no link"); continue; }
  await p.mouse.click(b.x, b.y); await sleep(2000);
  const ok = await p.evaluate(() => location.hash.includes("process_builder") || !!document.querySelector("#overview-source .cp-doc-body, .cp-card .cp-doc-body"));
  results.push(l.what + " (" + l.sel + "): " + (ok ? "opens" : "FAIL"));
}
for (const w of targets.weil) {
  await p.goto(url); await sleep(2500);
  const b = await p.evaluate((n) => { const weil = [...document.querySelectorAll(".cp-prepared p")].find((x) => x.textContent.startsWith("Weil")); const el = weil.querySelectorAll("button, a")[n]; el.scrollIntoView({block: "center"}); const r = el.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }, w.n);
  const before = await p.evaluate(() => location.hash);
  await p.mouse.click(b.x, b.y); await sleep(2000);
  const ok = await p.evaluate((h) => location.hash !== h || !!document.querySelector("#overview-source .cp-doc-body"), before);
  results.push(w.what + ": " + (ok ? "opens" : "FAIL"));
}
console.log(results.join("\n")); await p.close();
