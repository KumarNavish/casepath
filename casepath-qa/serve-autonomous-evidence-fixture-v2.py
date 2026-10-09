"""Serve the production UI with captured fictional GET responses, never writes.

Run from the repository root:
    python3 casepath-qa/serve-autonomous-evidence-fixture-v2.py --port 4188

Use --built to inspect casepath-public after the ordinary static build. This is
frontend QA only: it does not run an API controller, acquire files, or call a
provider. Actual command behavior belongs to deterministic controller tests.
"""

from __future__ import annotations

import argparse
import gzip
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


REPOSITORY = Path(__file__).resolve().parents[1]
FIXTURE = REPOSITORY / "design/evidence-path/recorded-fixtures.json.gz"
PREFIX = "/api/claim-loops/v1/autonomous"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4188)
    parser.add_argument("--built", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    product = REPOSITORY / ("casepath-public" if args.built else "casepath")
    if not (product / "index.html").is_file():
        parser.error(f"production index is absent: {product}")
    captured = json.loads(gzip.decompress(FIXTURE.read_bytes()))
    responses = captured["responses"]

    class FixtureHandler(SimpleHTTPRequestHandler):
        def __init__(self, *handler_args, **handler_kwargs):
            super().__init__(*handler_args, directory=str(product), **handler_kwargs)

        def json_response(self, status: int, payload: object) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-CasePath-QA", "captured-fictional-get-only")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def read(self) -> None:
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            if path.startswith("/api/"):
                key = path + "?after=0" if path.endswith("/events") else path
                if key not in responses:
                    self.json_response(404, {"detail": "No captured fictional response."})
                    return
                payload = responses[key]
                if path.endswith("/events"):
                    raw = parse_qs(parsed.query, keep_blank_values=True).get("after", ["0"])
                    try:
                        after = int(raw[0])
                        if len(raw) != 1 or after < 0:
                            raise ValueError
                    except ValueError:
                        self.json_response(400, {"detail": "Invalid event cursor."})
                        return
                    payload = {**payload, "events": [event for event in payload["events"]
                                                      if event["seq"] > after]}
                self.json_response(200, payload)
                return
            if self.command == "HEAD":
                super().do_HEAD()
            else:
                super().do_GET()

        do_GET = read
        do_HEAD = read

        def refuse_write(self) -> None:
            self.json_response(405, {"detail": "Captured frontend QA is read-only. No claim was saved."})

        do_POST = refuse_write
        do_PUT = refuse_write
        do_PATCH = refuse_write
        do_DELETE = refuse_write

        def log_message(self, *_args) -> None:
            pass

    with ThreadingHTTPServer(("127.0.0.1", args.port), FixtureHandler) as server:
        print(f"Production frontend QA: http://127.0.0.1:{args.port} (captured fictional GETs only)", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
