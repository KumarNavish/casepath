"""GET-only working-source preview over the owner's isolated deterministic API."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urlsplit
import argparse

ROOT = Path(__file__).resolve().parents[2]

class Preview(SimpleHTTPRequestHandler):
    def do_GET(self):
        route = urlsplit(self.path).path
        if route == '/':
            source, kind = ROOT / 'casepath/index.html', 'text/html; charset=utf-8'
        elif route in ('/assets/autonomous-workspace-v1.js', '/assets/autonomous-workspace-v1.css'):
            source = ROOT / 'casepath' / route.lstrip('/')
            kind = 'text/css' if route.endswith('.css') else 'text/javascript'
        else:
            try:
                with urlopen('http://127.0.0.1:4180' + self.path, timeout=60) as response:
                    body = response.read()
                    self.send_response(response.status)
                    self.send_header('Content-Type', response.headers.get('Content-Type', 'application/octet-stream'))
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            except HTTPError as error:
                self.send_error(error.code)
            return
        body = source.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, *args):
        pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=4181)
    args = parser.parse_args()
    print(f'Working desk preview: http://127.0.0.1:{args.port}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Preview).serve_forever()
