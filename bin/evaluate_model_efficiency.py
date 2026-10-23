#!/usr/bin/env python3
"""evaluate_model_efficiency.py - Cleanroom Empirical Model Efficiency & Verification Benchmark Runner

CLI entrypoint delegating to the contracted benchmark component in update_with_ai/parts/benchmark.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for p in [
    REPO_ROOT,
    REPO_ROOT / "update_with_ai",
    REPO_ROOT / "update_python_with_ai",
    REPO_ROOT / "update_with_ai" / "support" / "lib",
    REPO_ROOT / "update_python_with_ai" / "support" / "lib",
]:
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

from update_with_ai.support.lib.cleanroom_role_tool import run_benchmark_cli

if __name__ == "__main__":
    sys.exit(run_benchmark_cli(sys.argv[1:]))
