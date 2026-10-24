"""Load the authoritative gate guard from NS without changing its __file__."""
if not __debug__:
    raise RuntimeError("Publication requires Python assertions enabled.")

import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
_namespace = Path(__file__).resolve().parent.parent
_guard_path = _namespace / "require_completed_gate.py"
assert _guard_path.is_file(), "The authoritative namespace gate guard is missing"
_spec = importlib.util.spec_from_file_location("_casepath_demo_polish_completed_gate", _guard_path)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
assert Path(_module.__file__).resolve() == _guard_path.resolve()
assert _module.NS.resolve() == _namespace.resolve(), "Gate guard was loaded from the wrong namespace"
require_completed_gate = _module.require_completed_gate
