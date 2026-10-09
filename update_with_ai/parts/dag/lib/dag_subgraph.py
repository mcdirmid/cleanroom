# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:18:35Z
# CHANGE: Use relative import for sibling module dag_storage
# CODE_HASH: 20f259ad10ff
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Protocol, Sequence
from .dag_storage import DagNode

# Requirements specified in dag_subgraph.pyi

class DagSubgraph(Protocol):
    def set_target(self, target: DagNode) -> None:
        # TODO_set_target_body
        ...

    def is_complete(self) -> bool:
        # TODO_is_complete_body
        ...

    def next_ready_batch(self) -> Sequence[DagNode]:
        # TODO_next_ready_batch_body
        ...

    def record_visit(self, batch: Sequence[DagNode]) -> None:
        # TODO_record_visit_body
        ...
