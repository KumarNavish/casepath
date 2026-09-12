const API_ORIGIN = "https://casepath-agentic-api.onrender.com";

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

async function proxyApi(request, url) {
  const upstreamUrl = new URL(`${url.pathname}${url.search}`, API_ORIGIN);
  const headers = new Headers(request.headers);
  headers.delete("host");
  const upstreamRequest = new Request(upstreamUrl, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    redirect: "manual",
  });
  return fetch(upstreamRequest);
}

async function serveStatic(request, env, url) {
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

  const marker = '<script src="assets/live-v16.js';
  const html = await response.text();
  if (!html.includes(marker)) {
    return new Response("CasePath entry point is invalid", { status: 500 });
  }
  const configuration = '<script>window.CASEPATH_API = window.location.origin;</script>';
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
      return proxyApi(request, url);
    }
    return serveStatic(request, env, url);
  },
};
