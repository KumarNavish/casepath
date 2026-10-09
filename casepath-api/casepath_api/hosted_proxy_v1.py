"""Authenticate the Sites hop while retaining the API's same-origin guard."""
from hmac import compare_digest
from urllib.parse import urlsplit

from starlette.responses import JSONResponse


class SitesProxyBoundary:
    def __init__(self, app, *, site_origin, token):
        site = urlsplit(site_origin)
        if (site.scheme != 'https' or not site.hostname or site.username or site.password
                or site.path not in ('', '/') or site.query or site.fragment
                or not isinstance(token, str) or len(token) < 32 or not token.isascii()):
            raise ValueError('A fixed HTTPS Site origin and server secret are required.')
        self.app, self.origin, self.token = app, f'https://{site.netloc}', token
        self.server = (site.hostname, site.port or 443)
        self.host = site.netloc.encode('ascii')

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        # This probe must contain no claims or credentials. All data routes
        # remain accessible only through the authenticated Sites hop.
        if scope['method'] == 'GET' and scope['path'] == '/healthz':
            return await self.app(scope, receive, send)
        headers = {}
        for name, value in scope['headers']:
            key = name.lower()
            if key in headers:
                return await JSONResponse({'detail': 'Duplicate request header.'}, status_code=403)(scope, receive, send)
            headers[key] = value
        candidate = headers.get(b'x-casepath-proxy-token', b'')
        if (not compare_digest(candidate, self.token.encode('ascii')) or
                headers.get(b'x-casepath-site-origin') != self.origin.encode('ascii')):
            return await JSONResponse({'detail': 'Authenticated Site access required.'}, status_code=403)(scope, receive, send)
        if scope['method'] not in ('GET', 'HEAD') and headers.get(b'origin') != self.origin.encode('ascii'):
            return await JSONResponse({'detail': 'Cross-origin work requests are not accepted.'}, status_code=403)(scope, receive, send)
        forwarded = {k: v for k, v in headers.items() if k not in (
            b'x-casepath-proxy-token', b'x-casepath-site-origin', b'forwarded',
            b'x-forwarded-host', b'x-forwarded-proto', b'x-forwarded-for')}
        forwarded[b'host'] = self.host
        trusted_scope = {**scope, 'scheme': 'https', 'server': self.server, 'headers': list(forwarded.items())}
        await self.app(trusted_scope, receive, send)

