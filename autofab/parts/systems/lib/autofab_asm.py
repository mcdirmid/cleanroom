from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from autofab.parts.control.lib import control_asm
from autofab.parts.core.lib import file_paths_impl
from autofab.parts.dag.lib import dag_asm
from autofab.parts.metadata.lib import metadata_asm
from autofab.parts.uv.lib import uv_asm
from autofab.parts.workspace.lib import workspace_asm
from autofab.parts.workspace_cli.lib import workspace_cli_asm

# Contract: Declared constituents forming the master root system assembly.
CONSTITUENTS = (
    control_asm,
    file_paths_impl,
    metadata_asm,
    workspace_cli_asm,
    dag_asm,
    uv_asm,
    workspace_asm,
)


# Contract: Aggregates all Autofab UV subsystems into the master root system assembly.
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)


_initialize_ = __initialize__

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-29T17:15:00Z
# CHANGE: assemble cli_tool_impl under autofab
# --- END AUTOFAB METADATA ---
