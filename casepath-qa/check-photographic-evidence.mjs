import fs from 'node:fs/promises';
import crypto from 'node:crypto';

const API_URL = (process.env.API_URL || 'https://casepath-agentic-api.onrender.com').replace(/\/$/, '');
const EXPECTED_PRIMARY_SHA1 = '2f2b0db8db9b16b2509f802f87dca6f2761f95db';
const EXPECTED_LATER_SHA1 = 'd65830510a5f556f5d1f993ef6af4e30fd2efb07';
const OUT = 'photo-qa-out';

async function main() {
  await fs.rm(OUT, { recursive: true, force: true });
  await fs.mkdir(OUT, { recursive: true });

  const demoResponse = await fetch(`${API_URL}/api/demo?photoqa=${Date.now()}`, { cache: 'no-store' });
  if (!demoResponse.ok) throw new Error(`Demo request returned ${demoResponse.status}`);
  const demo = await demoResponse.json();
  const artifacts = demo.claim?.artifacts || demo.claim?.attachments || [];
  const primary = artifacts.find(item => item.artifact_id === 'art_photo');

  const laterDemo = await fetch(`${API_URL}/api/claims/DEMO-MOULD-002?photoqa=${Date.now()}`, { cache: 'no-store' });
  if (!laterDemo.ok) throw new Error(`Later-claim request returned ${laterDemo.status}`);
  const laterPayload = await laterDemo.json();
  const laterArtifacts = laterPayload?.claim?.artifacts || laterPayload?.artifacts || [];
  const later = laterArtifacts.find(item => item.artifact_id === 'art_later_photo');

  if (!primary) throw new Error(`art_photo was not present in the demo claim: ${JSON.stringify(artifacts)}`);
  if (!later) throw new Error(`art_later_photo was not present in the later claim: ${JSON.stringify(laterArtifacts)}`);

  async function inspect(item) {
    const response = await fetch(`${API_URL}/api/artifacts/${item.artifact_id}?photoqa=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${item.artifact_id} returned ${response.status}`);
    const bytes = Buffer.from(await response.arrayBuffer());
    return {
      artifact_id: item.artifact_id,
      filename: item.filename,
      content_type: response.headers.get('content-type'),
      size_bytes: bytes.length,
      sha1: crypto.createHash('sha1').update(bytes).digest('hex'),
      sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
      jpeg_signature: bytes[0] === 0xff && bytes[1] === 0xd8 && bytes.at(-2) === 0xff && bytes.at(-1) === 0xd9,
    };
  }

  const primaryResult = await inspect(primary);
  const laterResult = await inspect(later);

  if (primaryResult.sha1 !== EXPECTED_PRIMARY_SHA1) {
    throw new Error(`The deployed flagship photograph is not the approved source. expected=${EXPECTED_PRIMARY_SHA1} actual=${primaryResult.sha1}`);
  }
  if (laterResult.sha1 !== EXPECTED_LATER_SHA1) {
    throw new Error(`The deployed later-claim photograph is not the approved source. expected=${EXPECTED_LATER_SHA1} actual=${laterResult.sha1}`);
  }
  for (const result of [primaryResult, laterResult]) {
    if (!result.jpeg_signature || result.size_bytes < 100000) {
      throw new Error(`The deployed evidence is not a substantial JPEG: ${JSON.stringify(result)}`);
    }
  }
  if (laterResult.sha256 === primaryResult.sha256) {
    throw new Error('The two deployed evidence photographs are byte-identical.');
  }

  const report = {
    status: 'passed',
    checked_at: new Date().toISOString(),
    api_url: API_URL,
    primary: primaryResult,
    later: laterResult,
  };
  await fs.writeFile(`${OUT}/report.json`, `${JSON.stringify(report, null, 2)}\n`);
  await fs.writeFile(`${OUT}/index.html`, `<!doctype html><meta charset="utf-8"><title>CasePath photographic evidence gate</title><style>body{font:16px system-ui;max-width:760px;margin:48px auto;padding:0 24px;color:#142033}code{background:#f3f5f8;padding:2px 5px;border-radius:4px}</style><h1>Photographic evidence gate: passed</h1><p>Both deployed evidence images match the approved licensed source photographs.</p><pre>${JSON.stringify(report, null, 2)}</pre>`);
  console.log(JSON.stringify(report, null, 2));
}

main().catch(async error => {
  await fs.mkdir(OUT, { recursive: true });
  const report = { status: 'failed', checked_at: new Date().toISOString(), api_url: API_URL, error: error.stack || String(error) };
  await fs.writeFile(`${OUT}/report.json`, `${JSON.stringify(report, null, 2)}\n`);
  console.error(report.error);
  process.exitCode = 1;
});
