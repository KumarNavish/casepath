const API_ROOT_PATHS = new Set([
  "/deployment-health",
  "/healthz",
  "/readyz",
]);

function isApiRequest(pathname) {
  return pathname.startsWith("/api/") || API_ROOT_PATHS.has(pathname);
}

function staticHeaders(response) {
  const headers = new Headers(response.headers);
  headers.set("Cache-Control", "no-cache");
  headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  headers.set("Referrer-Policy", "no-referrer");
  headers.set("X-Content-Type-Options", "nosniff");
  return headers;
}

function unavailable() {
  return Response.json({detail: "CasePath is temporarily unavailable. Your saved work is preserved."},
    {status: 503, headers: {"Cache-Control": "no-store"}});
}

async function proxyApi(request, env, url) {
  const mutation = !["GET", "HEAD"].includes(request.method);
  const agentWork = url.pathname.startsWith("/api/claim-loops/v1/autonomous") ||
    url.pathname.startsWith("/api/agent-work/v1");
  if (mutation && (request.headers.get("origin") !== url.origin ||
      (agentWork && request.headers.get("X-CasePath-Agent-Work") !== "1"))) {
    return Response.json({detail: "Explicit same-origin work request required."}, {status: 403});
  }
  let upstream;
  try {
    upstream = new URL(env.CASEPATH_API_ORIGIN);
    if (upstream.protocol !== "https:" || upstream.username || upstream.password ||
        upstream.pathname !== "/" || upstream.search || upstream.hash ||
        typeof env.CASEPATH_PROXY_TOKEN !== "string" || env.CASEPATH_PROXY_TOKEN.length < 32) return unavailable();
  } catch { return unavailable(); }
  // Forward only application headers. Browser cookies and Sites credentials
  // belong to the hosting boundary, never to the upstream claim service.
  const headers = new Headers();
  for (const name of ["accept", "content-type", "origin", "x-casepath-agent-work", "last-event-id",
    "x-casepath-idempotency-key", "x-casepath-native-research-mode", "x-casepath-session"]) {
    if (request.headers.has(name)) headers.set(name, request.headers.get(name));
  }
  headers.set("X-CasePath-Proxy-Token", env.CASEPATH_PROXY_TOKEN);
  headers.set("X-CasePath-Site-Origin", url.origin);
  try {
    const response = await fetch(new Request(new URL(`${url.pathname}${url.search}`, upstream), {
      method: request.method, headers,
      body: mutation ? request.body : undefined,
      duplex: "half", redirect: "manual", signal: AbortSignal.timeout(14000),
    }));
    const responseHeaders = new Headers(response.headers);
    responseHeaders.set("Cache-Control", "no-store");
    responseHeaders.delete("set-cookie");
    return new Response(response.body, {status: response.status, headers: responseHeaders});
  } catch { return unavailable(); }
}

async function serveStatic(request, env, url) {
  if (url.pathname === '/corpus.html' || url.pathname === '/corpus') {
    return Response.redirect(new URL('/#autonomous/cases', url), 302);
  }
  if (url.pathname === '/' && url.searchParams.get('journey') === 'review') {
    const target = new URL(url);
    target.searchParams.delete('journey');
    return Response.redirect(target, 302);
  }
  const assetUrl = new URL(url);
  if (assetUrl.pathname === "/") {
    assetUrl.pathname = "/index.html";
  }
  const response = await env.ASSETS.fetch(new Request(assetUrl, request));
  if (!response.ok || assetUrl.pathname !== "/index.html") {
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: staticHeaders(response),
    });
  }

  const marker = '<script src="assets/autonomous-entry-v1.js';
  const html = await response.text();
  if (!html.includes(marker)) {
    return new Response("CasePath entry point is invalid", { status: 500 });
  }
  const configuration = '<script>window.CASEPATH_API = window.location.origin;window.CASEPATH_HOSTED_AUTONOMOUS = true;</script>';
  const configured = html.includes(configuration)
    ? html
    : html.replace(marker, configuration + '\n  ' + marker);
  const headers = staticHeaders(response);
  headers.set("Content-Type", "text/html; charset=utf-8");
  return new Response(configured, { status: response.status, headers });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (isApiRequest(url.pathname)) {
      return proxyApi(request, env, url);
    }
    return serveStatic(request, env, url);
  },
};
