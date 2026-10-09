'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const {pathToFileURL} = require('node:url');
const index = readFileSync(resolve(__dirname, '../casepath/index.html'), 'utf8');
const configuration = '<script>window.CASEPATH_API = window.location.origin;window.CASEPATH_HOSTED_AUTONOMOUS = true;</script>';
const entry = '<script src="assets/autonomous-entry-v1.js';

for (const preconfigured of [false, true]) {
  test(`Sites serves the autonomous entry with one preceding same-origin configuration (configured=${preconfigured})`, async () => {
    const worker = (await import(pathToFileURL(resolve(__dirname, '../casepath/tools/sites_worker.mjs')).href)).default;
    const html = preconfigured ? index.replace(entry, configuration + entry) : index;
    const response = await worker.fetch(new Request('https://casepath.invalid/'), {
      ASSETS: {fetch: async request => {
        assert.equal(new URL(request.url).pathname, '/index.html');
        return new Response(html);
      }},
    });
    assert.equal(response.status, 200);
    const served = await response.text();
    assert.equal(served.split(configuration).length - 1, 1);
    assert.ok(served.indexOf(configuration) < served.indexOf(entry));
    assert.match(response.headers.get('content-type'), /text\/html/);
    assert.equal(response.headers.get('cache-control'), 'no-cache');
  });
}

test('Sites rejects an index without its executable workspace entry', async () => {
  const worker = (await import(pathToFileURL(resolve(__dirname, '../casepath/tools/sites_worker.mjs')).href)).default;
  const response = await worker.fetch(new Request('https://casepath.invalid/'), {
    ASSETS: {fetch: async () => new Response('<html><body>No workspace entry</body></html>')},
  });
  assert.equal(response.status, 500);
});
