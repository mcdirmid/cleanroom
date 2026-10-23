from support.lib.lifecycle import Singleton, SystemTier
# Requirements specified in cleaner.pyi
from typing import Protocol
from . import node_cleaner
from update_with_ai.parts.dag.lib import dag_storage


# Contract: LoopCleaner coordinates topological graph cleaning across graph storage.
class LoopCleaner(Singleton[SystemTier], Protocol):
    # Contract: LoopCleaner.clean - cleans dirty nodes rooted at the target node in dependency-first topological order.
    def clean(
        self, target: dag_storage.DagNode, node_cleaner: node_cleaner.NodeCleaner
    ) -> bool: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# --- END CLEANROOM METADATA ---
