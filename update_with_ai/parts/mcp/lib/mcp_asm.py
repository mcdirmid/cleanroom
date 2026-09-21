from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import mcp_cache_arbiter_impl
from . import mcp_config_impl
from . import mcp_gate_impl
from . import mcp_server_impl
from . import mcp_session_impl

CONSTITUENTS = (
    mcp_cache_arbiter_impl,
    mcp_config_impl,
    mcp_gate_impl,
    mcp_server_impl,
    mcp_session_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
