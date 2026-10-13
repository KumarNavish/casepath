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
    parser.add_argument("--native-fixture", type=Path)
    parser.add_argument("--operations-sidecars", type=Path)
    parser.add_argument("--operations-live-unavailable", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    product = REPOSITORY / ("casepath-public" if args.built else "casepath")
    if not (product / "index.html").is_file():
        parser.error(f"production index is absent: {product}")
    native = json.loads(args.native_fixture.read_text()) if args.native_fixture else None
    captured = None if native else json.loads(gzip.decompress(FIXTURE.read_bytes()))
    responses = {} if native else captured["responses"]
    if native:
        responses[PREFIX + "/status"] = {"read_only": True, "writable": False, "enabled": False}
        responses[PREFIX + "/claims"] = {"claims": [
            {**row["state"], "origin": "canonical_original"} for row in native["snapshots"].values()]}
        responses[PREFIX + "/knowledge"] = native["knowledge"]
        for claim_id, row in native["snapshots"].items():
            responses[PREFIX + "/claims/" + claim_id] = row
            responses[PREFIX + "/claims/" + claim_id + "/snapshot"] = row
            responses[PREFIX + "/claims/" + claim_id + "/events?after=0"] = row
        for identity, row in native["sources"].items():
            responses[PREFIX + "/sources/" + identity + "/text"] = row

    def replay(claim_id, through):
        head = native["snapshots"][claim_id]
        if through == 0:
            row = native["unprocessed"][claim_id]
        elif through == head["current_revision"]:
            row = head
        else:
            row = native["prefixes"][claim_id][str(through)]
        state = row["state"]
        provenance = {field: state[field] for field in ("source_roster_sha256", "policy_id", "run_id") if field in state}
        provenance["event_sha256"] = state["last_event_sha256"]
        if state.get("original_binding"):
            provenance["original_binding_sha256"] = state["original_binding"]["original_binding_sha256"]
        return {**row, "mode": "replay", "replay_only": True, "through_seq": through,
                "current_revision": head["current_revision"], "current_state_sha256": head["current_state_sha256"],
                "current_event_sha256": head["current_event_sha256"], "replay_start": head["replay_start"],
                "provenance": provenance}

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
                if native and path.endswith("/operations"):
                    mode = parse_qs(parsed.query).get("mode", ["live"])[0]
                    if mode == "live" and args.operations_live_unavailable:
                        self.json_response(503, {"detail": "QA live transport unavailable."})
                        return
                    claim_id = path.split("/")[-2]
                    sidecar_path = args.operations_sidecars / (claim_id + ".json") if args.operations_sidecars else None
                    if not sidecar_path or not sidecar_path.is_file():
                        self.json_response(409, {"detail": "No captured native operation trace."})
                        return
                    frames = json.loads(sidecar_path.read_text())["frames"]
                    body = b"".join(json.dumps(frame, ensure_ascii=False, separators=(",", ":")).encode() + b"\n" for frame in frames)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-ndjson")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("X-CasePath-QA", "captured-native-operations-get-only")
                    self.end_headers()
                    if self.command != "HEAD":
                        try:
                            self.wfile.write(body)
                        except (BrokenPipeError, ConnectionResetError):
                            pass
                    return
                if native and path.endswith("/replay"):
                    try:
                        payload = replay(path.split("/")[-2], int(parse_qs(parsed.query)["through_seq"][0]))
                    except (KeyError, ValueError):
                        self.json_response(404, {"detail": "No exact captured native prefix."})
                        return
                    self.json_response(200, payload)
                    return
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
