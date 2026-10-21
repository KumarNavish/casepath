"""Local GET-only design preview. Reuses the owner's seeded preview at :4180."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError
import argparse

ROOT = Path(__file__).resolve().parent
class Preview(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
    def do_GET(self):
        if self.path.startswith(('/assets/', '/api/claim-loops/v1/autonomous/claims/')):
            try:
                with urlopen('http://127.0.0.1:4180' + self.path, timeout=60) as response:
                    body=response.read();self.send_response(response.status)
                    self.send_header('Content-Type', response.headers.get('Content-Type','application/octet-stream'))
                    self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            except HTTPError as error:
                self.send_error(error.code)
            return
        super().do_GET()
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()
if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=4181);args=parser.parse_args()
    print(f'Options preview: http://127.0.0.1:{args.port}/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Preview).serve_forever()
