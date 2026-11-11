"""Model transports for the speed work (no product code imported).

- CacheOnlyTransport: answers a request from runs/product/cache with the harness's key sha256(url, body, run) and RAISES
  on a miss. It holds no network transport at all, writes nothing, and counts hits and misses. Used for the replay of
  stored runs (development runs, and the finished study's stored runs on fresh2, which may be replayed only this way).
- LiveTransport: run_product.CachingTransport (cache, then the container's proxy; cost rows in
  runs/product/ledger_dev_<model>.jsonl under the arm), with the start, end and latency of every call recorded, and
  latency_s added to each ledger row it writes. A cached answer is returned at once and is marked as such.
"""
from __future__ import annotations

import hashlib
import json
import time

import httpx

import run_product as rp


class CacheMiss(RuntimeError):
    """A request the stored responses do not answer. Not an httpx error, so the connector does not retry it."""


def cache_key(request, run):
    body = request.read()
    return hashlib.sha256(str(request.url).encode() + b"\0" + body + b"\0" + str(run).encode()).hexdigest(), body


class CacheOnlyTransport(httpx.BaseTransport):
    def __init__(self, run: int):
        self.run, self.keys, self.misses = run, [], []

    def handle_request(self, request):
        key, body = cache_key(request, self.run)
        self.keys.append(key)
        path = rp.CACHE / f"{key}.json"
        if not path.exists():
            self.misses.append(key)
            raise CacheMiss(f"no stored response for request {key[:16]}")
        saved = json.loads(path.read_text())
        return httpx.Response(200, content=saved["body"].encode(), headers={"content-type": "application/json"}, request=request)

    def report(self):
        return {"mode": "cache-only", "keys": self.keys, "misses": self.misses}


class LiveTransport(rp.CachingTransport):
    def __init__(self, model, run, case_id, arm):
        super().__init__(model, run, case_id, arm=arm)
        self.t0 = time.monotonic()
        self.calls = []

    def handle_request(self, request):
        key, body = cache_key(request, self.run)
        start = time.monotonic()
        path = rp.CACHE / f"{key}.json"
        if path.exists():
            saved = json.loads(path.read_text())
            self.calls.append({"key": key, "start": round(start - self.t0, 3), "end": round(time.monotonic() - self.t0, 3), "cached": True})
            return httpx.Response(200, content=saved["body"].encode(), headers={"content-type": "application/json"}, request=request)
        response = self.inner.handle_request(request)
        content = response.read()
        end = time.monotonic()
        row = {"key": key, "start": round(start - self.t0, 3), "end": round(end - self.t0, 3), "cached": False,
               "status": response.status_code}
        if response.status_code == 200:
            try:
                payload = json.loads(content)
            except ValueError:
                payload = {}
            usage = payload.get("usage") or {}
            cost = usage.get("cost")
            row.update(usd=cost if cost is not None else rp._list_price(self.model, usage),
                       input=usage.get("prompt_tokens"), cached_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                       output=usage.get("completion_tokens"),
                       reasoning=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                       choices=len(payload.get("choices") or []))
            ledger_row = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "model": self.model, "case": self.case_id,
                          "run": self.run, "key": key, "input_tokens": usage.get("prompt_tokens"),
                          "cached_tokens": row["cached_tokens"], "output_tokens": usage.get("completion_tokens"),
                          "usd": row["usd"], "arm": self.arm, "latency_s": round(end - start, 3)}
            with rp._lock:
                path.write_text(json.dumps({"body": content.decode()}))
                with self.ledger.open("a") as f:
                    f.write(json.dumps(ledger_row) + "\n")
        self.calls.append(row)
        # the body is already decoded: pass it on without the content-encoding header
        headers = [(k, v) for k, v in response.headers.items() if k.lower() not in {"content-encoding", "content-length", "transfer-encoding"}]
        return httpx.Response(response.status_code, content=content, headers=headers, request=request)

    def report(self):
        return {"mode": "live", "calls": self.calls, "keys": [c["key"] for c in self.calls]}
