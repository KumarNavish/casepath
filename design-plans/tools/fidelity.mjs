// Compare a product frame with its north star concept at 1440x900.
// Usage: node design-plans/tools/fidelity.mjs <concept.png> <frame.png> <out-prefix>
// Writes <out>-side.png (concept | frame), <out>-overlay.png (frame at 50% over the concept)
// and <out>-diff.png (per-pixel difference), and prints the mean difference in percent.
import fs from 'node:fs';

let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch {
  ({ chromium } = await import(process.env.PLAYWRIGHT_MODULE || '/opt/node22/lib/node_modules/playwright/index.mjs'));
}

const [concept, frame, out] = process.argv.slice(2);
if (!concept || !frame || !out) {
  console.error('usage: node fidelity.mjs <concept.png> <frame.png> <out-prefix>');
  process.exit(2);
}
const dataUrl = (p) => 'data:image/png;base64,' + fs.readFileSync(p).toString('base64');

const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM || undefined });
const page = await browser.newPage();
const result = await page.evaluate(async ({ c, f }) => {
  const load = (src) => new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
  const [ci, fi] = await Promise.all([load(c), load(f)]);
  const W = 1440, H = 900, GAP = 24;
  const canvas = (w, h) => Object.assign(document.createElement('canvas'), { width: w, height: h });

  const side = canvas(W * 2 + GAP, H);
  let g = side.getContext('2d');
  g.fillStyle = '#fff';
  g.fillRect(0, 0, side.width, H);
  g.drawImage(ci, 0, 0, W, H);
  g.drawImage(fi, W + GAP, 0, W, H);

  const overlay = canvas(W, H);
  g = overlay.getContext('2d');
  g.drawImage(ci, 0, 0, W, H);
  g.globalAlpha = 0.5;
  g.drawImage(fi, 0, 0, W, H);

  const diff = canvas(W, H);
  g = diff.getContext('2d');
  g.drawImage(ci, 0, 0, W, H);
  g.globalCompositeOperation = 'difference';
  g.drawImage(fi, 0, 0, W, H);
  const px = g.getImageData(0, 0, W, H).data;
  let sum = 0;
  for (let i = 0; i < px.length; i += 4) sum += (px[i] + px[i + 1] + px[i + 2]) / 3;
  const meanPct = (sum / (W * H) / 255) * 100;

  return { side: side.toDataURL(), overlay: overlay.toDataURL(), diff: diff.toDataURL(), meanPct };
}, { c: dataUrl(concept), f: dataUrl(frame) });
await browser.close();

for (const key of ['side', 'overlay', 'diff']) {
  fs.writeFileSync(`${out}-${key}.png`, Buffer.from(result[key].split(',')[1], 'base64'));
}
console.log(JSON.stringify({ concept, frame, mean_difference_pct: Number(result.meanPct.toFixed(2)) }));
