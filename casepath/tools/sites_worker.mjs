const API_ROOT_PATHS = new Set([
  "/deployment-health",
  "/healthz",
  "/readyz",
]);
const TIMED_READ_PATHS = new Set([
  "/api/claim-loops/v1/autonomous/knowledge",
  "/api/claim-loops/v1/autonomous/claims",
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
  if (/^\/api\/claim-loops\/v1\/autonomous\/claims\/[^/]+\/operations$/.test(url.pathname) &&
      request.headers.has("accept-encoding")) {
    headers.set("Accept-Encoding", request.headers.get("accept-encoding"));
  }
  headers.set("X-CasePath-Proxy-Token", env.CASEPATH_PROXY_TOKEN);
  headers.set("X-CasePath-Site-Origin", url.origin);
  try {
    const started = request.method === "GET" && TIMED_READ_PATHS.has(url.pathname) ? performance.now() : null;
    const response = await fetch(new Request(new URL(`${url.pathname}${url.search}`, upstream), {
      method: request.method, headers,
      duplex: "half", redirect: "manual",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(14000)]),
    }));
    const elapsed = started === null ? null : performance.now() - started;
    const responseHeaders = new Headers(response.headers);
    if (elapsed !== null) {
      const duration = Number.isFinite(elapsed) ? Math.min(999999999.999, Math.max(0, elapsed)) : 0;
      responseHeaders.append("Server-Timing", `casepath_upstream;dur=${duration.toFixed(3)}`);
    }
    responseHeaders.set("Cache-Control", "no-store");
    responseHeaders.delete("set-cookie");
    // Workers Fetch preserves compressed origin bytes when the body is unread
    // and Content-Encoding is retained; pass the native stream through intact.
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
  if (!html.includes(marker) || !html.includes('<head>')) {
    return new Response("CasePath entry point is invalid", { status: 500 });
  }
  const configuration = '<script>window.CASEPATH_API = window.location.origin;window.CASEPATH_HOSTED_AUTONOMOUS = true;window.CASEPATH_PUBLIC_READ_ONLY = true;</script>';
  const configured = html.includes(configuration)
    ? html
    : html.replace('<head>', '<head>\n  ' + configuration);
  const headers = staticHeaders(response);
  headers.set("Content-Type", "text/html; charset=utf-8");
  return new Response(configured, { status: response.status, headers });
}

export default {
  async fetch(request, env) {
    // Public access is an inspection capability. Visitor headers, identities,
    // and runtime flags never grant work authority through this server hop.
    if (!["GET", "HEAD"].includes(request.method)) {
      return Response.json({detail: "The public workspace is read-only. Saved cases, sources, replay and Knowledge remain available."},
        {status: 403, headers: {"Cache-Control": "no-store"}});
    }
    const url = new URL(request.url);
    if (isApiRequest(url.pathname)) {
      return proxyApi(request, env, url);
    }
    return serveStatic(request, env, url);
  },
};
