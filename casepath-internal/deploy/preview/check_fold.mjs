// Browser check on the local preview (make preview); replace CASE_ID with a prepared synthetic case.
// The prepared action is the first card in the main area and its title is above the fold.
const t = await taskSpace(0); const p = await t.newPage(); const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const out = [];
for (const [w, h] of [[1440, 900], [1280, 720]]) {
  if (p.setViewportSize) await p.setViewportSize({ width: w, height: h });
  await p.goto("http://127.0.0.1:8790/?lang=de#/case/CASE_ID/overview"); await sleep(3500);
  const r = await p.evaluate(() => { const main = document.querySelector("main"); const first = main.querySelector(".cp-prepared, section, .cp-card");
    const b = first.getBoundingClientRect(); const head = first.querySelector("h2"); const hb = head ? head.getBoundingClientRect() : b;
    return { vw: innerWidth, vh: innerHeight, isPrepared: first.classList.contains("cp-prepared"), headTop: Math.round(hb.top), headBottom: Math.round(hb.bottom) }; });
  out.push(`${w}x${h} (inner ${r.vw}x${r.vh}): first is the prepared action ${r.isPrepared}, its title at ${r.headTop}-${r.headBottom}px, above the fold ${r.headBottom <= r.vh}`);
}
console.log(out.join("\n")); await p.close();
