"""Hash-bound runtime for the exact CasePath paper planner.

The runtime loads only a server-side pack. It validates every declared byte before
serving a plan, then delegates inference to casepath_process_service_v2.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from . import casepath_process_service_v3 as service
from .arena_v1 import transport

CONTRACT = "casepath.paper-method-runtime/3.0.0"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PaperMethodRuntimeV3:
    def __init__(self, pack_dir: Path, call: Callable[[str, str], str] | None = None):
        self.pack_dir = Path(pack_dir)
        self.call = call
        self.error: str | None = None
        self.manifest: dict[str, Any] = {}
        self.source: dict[str, Any] = {}
        self.propositions: list[dict[str, Any]] = []
        self.prepared: dict[str, Any] = {}
        self.demo: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            manifest_path = self.pack_dir / "PACK_MANIFEST.json"
            self.manifest = json.loads(manifest_path.read_text())
            if self.manifest.get("contract") != "casepath.paper-method-pack/5.0.0":
                raise ValueError("unexpected paper-method pack contract")
            for rel, expected in (self.manifest.get("files") or {}).items():
                path = self.pack_dir / rel
                if not path.is_file() or _sha(path) != expected:
                    raise ValueError(f"paper-method pack integrity failure: {rel}")
            self.source = json.loads((self.pack_dir / "SOURCE_SNAPSHOT.json").read_text())
            self.propositions = json.loads((self.pack_dir / "PROPOSITIONS.json").read_text())
            self.prepared = json.loads((self.pack_dir / "PREPARED.json").read_text())
            self.demo = json.loads((self.pack_dir / "DEMO_CASE.json").read_text())
        except Exception as exc:
            message = str(exc)
            self.error = (message if isinstance(exc, ValueError) and "integrity failure" in message
                          else "paper-method pack unavailable or invalid")

    @property
    def ready(self) -> bool:
        return self.error is None and bool(self.manifest)

    def status(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "error": self.error,
            "scope": self.manifest.get("scope"),
            "method_freeze_sha256": self.manifest.get("method_freeze_sha256"),
            "pack_manifest_sha256": _sha(self.pack_dir / "PACK_MANIFEST.json") if self.ready else None,
            "demo_case": self.demo if self.ready else None,
        }

    def _provider_call(self, system: str, user: str) -> str:
        cfg = self.manifest.get("model") or {}
        result = transport.call_with_transport_retry(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=cfg["name"], max_tokens=int(cfg["max_tokens"]),
            temperature=float(cfg.get("temperature", 0.0)),
            provider_only=list(cfg.get("provider_only") or []),
        )
        if not result.get("ok"):
            raise RuntimeError(f"paper-method provider failure: {result.get('status')} {result.get('error')}")
        return result["content"]

    def plan(self, case: Mapping[str, str], already_held: list[str]) -> dict[str, Any]:
        if not self.ready:
            raise RuntimeError(self.error or "paper-method runtime is not ready")
        return service.plan_claim(
            prepared=self.prepared,
            propositions=self.propositions,
            passages=self.source.get("passages") or [],
            case=case,
            already_held=already_held,
            call=self.call or self._provider_call,
        )

    @staticmethod
    def diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
        return service.diff_plans(before, after)
