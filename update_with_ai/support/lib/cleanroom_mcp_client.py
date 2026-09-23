#!/usr/bin/env python3
"""cleanroom_mcp_client.py — Forwarding shim to update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl."""

from __future__ import annotations

import os
import sys

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_python_with_ai"), os.path.join(_repo_root, "update_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl import (
    AntigravityMcpClient,
    call_tool,
    main,
)

if __name__ == "__main__":
    sys.exit(main())
