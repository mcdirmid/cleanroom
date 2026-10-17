# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 5841388ecb8d
# --- END CLEANROOM METADATA ---

# Requirements specified in loop_node_cleaner.pyi
from typing import Protocol, Sequence
from update_with_ai.parts.dag.lib import dag_storage


# Contract: NodeCleaner protocol - cleans dirty nodes sharing a role, communicating whether processing should continue.
class NodeCleaner(Protocol):
    # Contract: NodeCleaner.clean - cleans dirty nodes sharing a role.
    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool: ...
