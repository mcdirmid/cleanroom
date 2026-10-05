# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 624cde94c118
# --- END CLEANROOM METADATA ---

# Requirements specified in dag_subgraph.pyi
from typing import Protocol, Sequence
from . import dag_storage


class DagSubgraph(Protocol):
    def set_target(self, target: dag_storage.DagNode) -> None: ...

    def is_complete(self) -> bool: ...

    def next_ready_batch(self) -> Sequence[dag_storage.DagNode]: ...

    def record_visit(self, batch: Sequence[dag_storage.DagNode]) -> None: ...
