"""CLI runner for Pretense state machines (uv run pretense)."""

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (_REPO_ROOT, _REPO_ROOT / "update_python_with_ai", _REPO_ROOT / "update_with_ai"):
    _str_p = str(_p)
    if _p.is_dir() and _str_p not in sys.path:
        sys.path.insert(0, _str_p)

# Also discover support/lib if run within a role workspace
_curr = Path.cwd().resolve()
while _curr and _curr != _curr.parent:
    if (_curr / "support" / "lib").is_dir():
        _sup = str(_curr / "support" / "lib")
        if _sup not in sys.path:
            sys.path.insert(0, _sup)
        break
    _curr = _curr.parent

from update_python_with_ai.parts.pretense.lib.pretense_impl import main, run_pretense_cli

if __name__ == "__main__":
    sys.exit(main())

__all__ = ["main", "run_pretense_cli"]
