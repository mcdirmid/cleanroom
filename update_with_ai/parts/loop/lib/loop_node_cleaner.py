# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 5841388ecb8d
# --- END CLEANROOM METADATA ---

# Requirements specified in loop_node_cleaner.pyi
from typing import Protocol, Sequence
from update_with_ai.parts.dag.lib import dag_storage


class NodeCleaner(Protocol):
    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool: ...
