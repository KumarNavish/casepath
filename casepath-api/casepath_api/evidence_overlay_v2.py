"""Evidence overlay with atomic per-guard interpretation."""
from __future__ import annotations

from functools import partial
from typing import Any, Callable, Mapping, Sequence

from . import case_interpreter_v3 as ci
from . import evidence_overlay_v1 as v1

CONTRACT = "casepath.evidence-overlay/2.0.0"
materialize = v1.materialize
prepare = v1.prepare


def plan_case(*, case: Mapping[str, str], prepared: Mapping[str, Any], held: Sequence[str],
              call: Callable[[str, str], str] | None = None, workers: int = 12,
              decided: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = v1.plan_case(
        case=case,
        prepared=prepared,
        held=held,
        call=call,
        decide_fn=partial(ci.decide, workers=workers),
        decided=decided,
    )
    result["contract"] = CONTRACT
    return result
