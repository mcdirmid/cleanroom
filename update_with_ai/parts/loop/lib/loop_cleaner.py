# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 5172b091ce25
# --- END CLEANROOM METADATA ---

# Requirements specified in loop_cleaner.pyi
from typing import Protocol
from . import loop_node_cleaner
from update_with_ai.parts.dag.lib import dag_storage


class LoopCleaner(Protocol):
    def clean(
        self, target: dag_storage.DagNode, node_cleaner: loop_node_cleaner.NodeCleaner
    ) -> bool: ...
