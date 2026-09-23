#!/usr/bin/env python3
"""antigravity_token_stats.py — Forwarding shim to update_with_ai.parts.antigravity.lib.antigravity_telemetry_impl."""

from __future__ import annotations

import os
import sys

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_python_with_ai"), os.path.join(_repo_root, "update_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from update_with_ai.parts.antigravity.lib.antigravity_telemetry_impl import (
    PRICING_MODELS,
    PRICING_TABLE,
    _DEFAULT_BRAIN_DIR,
    _DEFAULT_DB_DIR,
    compute_cost,
    get_conversation_stats,
    main,
)

if __name__ == "__main__":
    sys.exit(main())
