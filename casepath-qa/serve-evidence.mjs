import { createReadStream, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { extname, resolve, sep } from 'node:path';

const root = resolve('casepath-qa/guided-v13-smoke-out');
const port = Number(process.env.PORT || 10000);
const allowedOrigins = new Set([
  'https://casepath.onrender.com',
  'https://casepath-swiss-claim-lab.onrender.com',
  'https://casepath.kumarnavish.chatgpt.site',
]);
const mediaTypes = Object.freeze({
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.webm': 'video/webm',
});

function responseHeaders(origin, path) {
  const headers = {
    'Cache-Control': 'no-store',
    Pragma: 'no-cache',
    Expires: '0',
    'Content-Type': mediaTypes[extname(path)] || 'application/octet-stream',
    'X-Content-Type-Options': 'nosniff',
  };
  if (allowedOrigins.has(origin)) {
    headers['Access-Control-Allow-Origin'] = origin;
    headers.Vary = 'Origin';
  }
  return headers;
}

createServer((request, response) => {
  const origin = request.headers.origin || '';
  if (request.method === 'OPTIONS') {
    response.writeHead(204, responseHeaders(origin, 'response.json'));
    response.end();
    return;
  }
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    response.writeHead(405, { Allow: 'GET, HEAD, OPTIONS' });
    response.end();
    return;
  }
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
  } catch (_) {
    response.writeHead(400);
    response.end();
    return;
  }
  const relative = pathname === '/' ? 'report.json' : pathname.replace(/^\/+/, '');
  const target = resolve(root, relative);
  if (!target.startsWith(`${root}${sep}`) || !Object.hasOwn(mediaTypes, extname(target))) {
    response.writeHead(404);
    response.end();
    return;
  }
  try {
    if (!statSync(target).isFile()) throw new Error('not-file');
  } catch (_) {
    response.writeHead(404);
    response.end();
    return;
  }
  response.writeHead(200, responseHeaders(origin, target));
  if (request.method === 'HEAD') response.end();
  else createReadStream(target).pipe(response);
}).listen(port, '0.0.0.0');
