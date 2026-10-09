"""Local-only design preview. Saved fictional responses; no writes or credentials."""
import gzip
import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).parent
PRODUCT = ROOT.parents[1] / 'casepath'
FIXTURE = ROOT / 'recorded-fixtures.json.gz'
RESPONSES = json.loads(gzip.decompress(FIXTURE.read_bytes()))['responses']

class Preview(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send(self, status, payload, mime='application/json'):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        key = path + '?after=0' if path.endswith('/events') else path
        if key in RESPONSES:
            self.send(200, RESPONSES[key])
        elif path.startswith('/api/'):
            self.send(404, {'detail': 'No captured response.'})
        elif path == '/core.js':
            self.send(200, (PRODUCT/'assets/autonomous-workspace-v1.js').read_bytes(), 'text/javascript')
        elif path == '/font.ttf':
            self.send(200, (PRODUCT/'assets/fonts/OpenSans-VariableFont_wdth-wght.ttf').read_bytes(), 'font/ttf')
        else:
            super().do_GET()

    def do_POST(self):
        self.send(405, {'detail': 'Read-only design preview. Writes are refused.'})

    do_PUT = do_PATCH = do_DELETE = do_POST

    def log_message(self, *_args):
        pass

if __name__ == '__main__':
    print('CasePath design preview: http://127.0.0.1:4187', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 4187), Preview).serve_forever()
