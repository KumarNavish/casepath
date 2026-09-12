import fs from 'node:fs/promises';
import path from 'node:path';

const BASE_URL = (process.env.BASE_URL || 'https://casepath-v1203-preview.onrender.com').replace(/\/$/, '');
const API_URL = (process.env.API_URL || 'https://casepath-agentic-api.onrender.com').replace(/\/$/, '');
const TIMEOUT_MS = Number(process.env.TIMEOUT_MS || 90000);
const OUT = path.resolve('qa-out');

const checks = [];
const details = {};

function record(name, passed, detail = '') {
  checks.push({ name, passed: Boolean(passed), detail });
  if (!passed) throw new Error(`${name}: ${detail || 'failed'}`);
}

async function request(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    return await fetch(url, {
      redirect: 'follow',
      cache: 'no-store',
      ...options,
      signal: controller.signal,
      headers: {
        'user-agent': 'CasePath-public-release-gate/direct-static',
        ...(options.headers || {}),
      },
    });
  } finally {
    clearTimeout(timer);
  }
}

async function getText(url, recordCheck = true) {
  const response = await request(url);
  const text = await response.text();
  if (recordCheck) record(`HTTP 200 ${url}`, response.status === 200, `status=${response.status}`);
  else if (response.status !== 200) throw new Error(`${url} returned HTTP ${response.status}`);
  return { response, text };
}

async function getJson(url, options = {}, recordCheck = true) {
  const response = await request(url, options);
  const text = await response.text();
  if (recordCheck) record(`${options.method || 'GET'} ${url}`, response.ok, `status=${response.status}; body=${text.slice(0, 240)}`);
  else if (!response.ok) throw new Error(`${options.method || 'GET'} ${url} returned ${response.status}: ${text.slice(0, 240)}`);
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`Invalid JSON from ${url}: ${error.message}; body=${text.slice(0, 240)}`);
  }
}

async function warm(url) {
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await request(`${url}${url.includes('?') ? '&' : '?'}warm=${Date.now()}-${attempt}`);
      if (response.ok) return response;
      lastError = new Error(`${url} returned HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise(resolve => setTimeout(resolve, 2500));
  }
  throw lastError;
}

async function waitForRun(runId) {
  const deadline = Date.now() + 120000;
  let last;
  while (Date.now() < deadline) {
    last = await getJson(`${API_URL}/api/runs/${runId}`, {}, false);
    if (last.status === 'complete' || last.status === 'failed') return last;
    await new Promise(resolve => setTimeout(resolve, 700));
  }
  throw new Error(`Run ${runId} did not finish; last=${JSON.stringify(last).slice(0, 500)}`);
}

async function main() {
  await fs.rm(OUT, { recursive: true, force: true });
  await fs.mkdir(OUT, { recursive: true });

  await warm(`${BASE_URL}/`);
  await warm(`${API_URL}/healthz`);

  const rootUrl = `${BASE_URL}/?qa=${Date.now()}`;
  const { response: rootResponse, text: html } = await getText(rootUrl);
  details.finalUrl = rootResponse.url;
  record('Canonical document does not redirect away', rootResponse.url.startsWith(`${BASE_URL}/`), rootResponse.url);
  record('Direct CasePath document is served', /^\s*<!doctype html>/i.test(html) && html.includes('<title>CasePath'));
  record('Flagship claim is visible in source HTML', html.includes('Recurring mould. The landlord blames ventilation.'));
  record('Customer submission section is present', html.includes('What the customer sent'));
  record('Analysis section is present', html.includes('CasePath is working through the claim'));
  record('Process and evidence section is present', html.includes('Handling process') && html.includes('evidence-column'));
  record('Expert review section is present', html.includes('Review the one decision that changes the work'));
  record('Learning proof section is present', html.includes('The next claim benefits'));
  record('Broken bootstrap loader is absent', !html.includes('casepath-payload') && !html.includes("Failed to execute 'atob'") && !html.includes('bundle-v12-000.txt'));
  record('No external unified-service redirect exists', !html.includes('casepath-v12-unified.onrender.com'));

  const linked = [...html.matchAll(/(?:src|href)=["']([^"']+)["']/g)].map(match => match[1]);
  const localAssets = [...new Set(linked.filter(value => !/^(?:https?:|data:|#|mailto:)/.test(value)))];
  details.localAssets = localAssets;
  record('Direct document links runtime assets', localAssets.length >= 4, JSON.stringify(localAssets));
  for (const asset of localAssets) {
    const clean = asset.split(/[?#]/, 1)[0].replace(/^\//, '');
    if (!clean) continue;
    const response = await request(`${BASE_URL}/${clean}?qa=${Date.now()}`);
    record(`Asset ${clean}`, response.status === 200, `status=${response.status}; type=${response.headers.get('content-type')}`);
  }

  const health = await getJson(`${API_URL}/healthz`);
  record('API health is ok', health.status === 'ok', JSON.stringify(health));
  const ready = await getJson(`${API_URL}/readyz`);
  record('API is ready', ready.status === 'ready', JSON.stringify(ready));
  const demo = await getJson(`${API_URL}/api/demo`);
  record('Demo claim is available', Boolean(demo.demo_claim_id && demo.claim), JSON.stringify(demo).slice(0, 240));
  const sourceFiles = Array.isArray(demo.claim.artifacts)
    ? demo.claim.artifacts
    : (Array.isArray(demo.claim.attachments) ? demo.claim.attachments : []);
  record('Demo claim contains source attachments', sourceFiles.length > 0, `source_files=${sourceFiles.length}`);

  for (const attachment of sourceFiles.slice(0, 3)) {
    const artifactId = attachment.artifact_id || attachment.id;
    record('Source attachment has an artifact id', Boolean(artifactId), JSON.stringify(attachment));
    const artifactResponse = await request(`${API_URL}/api/artifacts/${artifactId}`);
    record(`Source attachment ${artifactId} opens`, artifactResponse.status === 200, `status=${artifactResponse.status}; type=${artifactResponse.headers.get('content-type')}`);
    const extraction = await getJson(`${API_URL}/api/artifacts/${artifactId}/extraction`);
    record(`Extraction ${artifactId} is separate`, extraction.artifact_id === artifactId || extraction.id === artifactId, JSON.stringify(extraction).slice(0, 180));
  }

  await getJson(`${API_URL}/api/demo/reset`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' });
  const created = await getJson(`${API_URL}/api/runs`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ claim_id: demo.demo_claim_id }),
  });
  record('Analysis run was created', Boolean(created.run_id), JSON.stringify(created));
  const run = await waitForRun(created.run_id);
  record('Analysis run completed', run.status === 'complete', JSON.stringify(run).slice(0, 400));
  record('Analysis emitted pipeline events', Array.isArray(run.events) && run.events.length >= 6, `events=${run.events?.length}`);
  record('Analysis produced process reasoning', Boolean(run.result?.process || run.result?.current_blocker), JSON.stringify(run.result).slice(0, 320));
  record('Analysis produced evidence requirements', Boolean(run.result?.checklist || run.result?.documents), JSON.stringify(run.result).slice(0, 320));
  record('Analysis returned three precedents', Array.isArray(run.result?.precedents) && run.result.precedents.length === 3, `precedents=${run.result?.precedents?.length}`);

  const review = await getJson(`${API_URL}/api/runs/${created.run_id}/review`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      decision: 'approve_with_edit',
      building_envelope_mode: 'conditional',
      confidence: 0.91,
      justification: 'Public release gate: keep broader testing conditional on the neutral inspection.',
    }),
  });
  record('Expert review was accepted', Boolean(review), JSON.stringify(review).slice(0, 320));
  const knowledge = await getJson(`${API_URL}/api/knowledge`);
  record('Reviewed knowledge is readable', Boolean(knowledge), JSON.stringify(knowledge).slice(0, 320));
  const proof = await getJson(`${API_URL}/api/learning-proof`);
  record('Later-claim learning proof is available', Boolean(proof), JSON.stringify(proof).slice(0, 320));

  const report = {
    status: 'passed',
    checkedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    apiUrl: API_URL,
    passed: checks.filter(check => check.passed).length,
    failed: checks.filter(check => !check.passed).length,
    checks,
    details,
    runId: created.run_id,
    demoClaimId: demo.demo_claim_id,
  };
  await fs.writeFile(path.join(OUT, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
  await fs.writeFile(path.join(OUT, 'index.html'), `<!doctype html><meta charset="utf-8"><title>CasePath public release gate</title><style>body{font:16px system-ui;max-width:900px;margin:40px auto;padding:0 20px;color:#142033}li{margin:8px 0}.ok{color:#087443}code{background:#f3f5f8;padding:2px 5px;border-radius:4px}</style><h1>CasePath public release gate: passed</h1><p><strong>${report.passed}</strong> checks passed against <code>${BASE_URL}</code> and <code>${API_URL}</code>.</p><ul>${checks.map(check => `<li class="ok">✓ ${check.name}</li>`).join('')}</ul>`);
  console.log(JSON.stringify(report, null, 2));
}

main().catch(async error => {
  await fs.mkdir(OUT, { recursive: true });
  const report = {
    status: 'failed',
    checkedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    apiUrl: API_URL,
    passed: checks.filter(check => check.passed).length,
    failed: checks.filter(check => !check.passed).length + 1,
    checks,
    error: error instanceof Error ? error.stack : String(error),
    details,
  };
  await fs.writeFile(path.join(OUT, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
  console.error(report.error);
  process.exitCode = 1;
});
