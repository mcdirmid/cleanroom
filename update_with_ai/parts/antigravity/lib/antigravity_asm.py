# Requirements specified in antigravity_asm.pyi
from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import antigravity_coordinator_impl
from . import antigravity_mcp_client_impl
from . import antigravity_run_logger_impl
from . import antigravity_sandbox_gate_impl
from . import antigravity_telemetry_impl

CONSTITUENTS = (
    antigravity_coordinator_impl,
    antigravity_mcp_client_impl,
    antigravity_run_logger_impl,
    antigravity_sandbox_gate_impl,
    antigravity_telemetry_impl,
)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        init_fn = getattr(mod, "__initialize__", None)
        if callable(init_fn):
            init_fn(registry)


_initialize_ = __initialize__
