from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib import agent_node_config
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.dag.lib import dag_subgraph
from . import mcp_cache_arbiter
from . import mcp_cache_arbiter_impl
from . import mcp_gate
from . import mcp_gate_impl
from . import mcp_server
from . import mcp_server_impl
from . import mcp_session
from . import mcp_session_impl
from update_with_ai.parts.sandbox.lib import sandbox_file_editor
from update_with_ai.parts.sandbox.lib import sandbox_file_reader
from update_with_ai.parts.sandbox.lib import tool_provider

CONSTITUENTS = (
    agent_config,
    agent_node_config,
    agent_session,
    dag_storage,
    dag_subgraph,
    mcp_cache_arbiter,
    mcp_cache_arbiter_impl,
    mcp_gate,
    mcp_gate_impl,
    mcp_server,
    mcp_server_impl,
    mcp_session,
    mcp_session_impl,
    sandbox_file_editor,
    sandbox_file_reader,
    tool_provider,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
