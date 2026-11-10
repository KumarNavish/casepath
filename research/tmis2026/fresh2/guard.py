"""Guard for the sealed fresh2 data (Study 3 confirmatory test).

No design, baseline or scorer may run on fresh2/ before research/tmis2026/ANALYSIS_PLAN_STUDY3.md exists, is
tracked by git and is committed unmodified. Two places enforce it:

- harness/v2/common.py::data(kind, "fresh2") calls require_study3_plan() unconditionally, so every runner and
  scorer that selects the data through common.data refuses to load fresh2 without the committed plan;
- the loaders tenancy_fresh2.py and theft_fresh2.py call check_model_process() on every data access: if the
  repository's model client (module `llm`) is imported in the same process, or TMIS_MODEL is set, the access is
  refused unless the plan is committed. Model-free checks (fresh2/check.py, which imports neither) are unaffected.

Neither guard can stop a person or program that copies the files elsewhere; it prevents accidental use from the
repository's own harness.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TMIS = Path(__file__).resolve().parents[1]
REPO = TMIS.parents[1]
PLAN = TMIS / "ANALYSIS_PLAN_STUDY3.md"
MESSAGE = ("refusing to load fresh2 for a model run: research/tmis2026/ANALYSIS_PLAN_STUDY3.md must exist and be "
           "committed unmodified (see research/tmis2026/fresh2/README.md)")


def plan_committed() -> bool:
    if not PLAN.exists():
        return False
    rel = str(PLAN.relative_to(REPO))
    tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", rel], capture_output=True)
    clean = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", rel], capture_output=True)
    return tracked.returncode == 0 and clean.returncode == 0


def require_study3_plan() -> None:
    if not plan_committed():
        raise SystemExit(MESSAGE)


def model_process() -> bool:
    return "llm" in sys.modules or bool(os.environ.get("TMIS_MODEL"))


_ok = False


def check_model_process() -> None:
    global _ok
    if _ok or not model_process():
        return
    require_study3_plan()
    _ok = True
