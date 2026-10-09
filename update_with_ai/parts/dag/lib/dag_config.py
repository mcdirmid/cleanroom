# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:18:05Z
# CHANGE: Align with dag_config.pyi specification
# CODE_HASH: 810339822708
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Protocol

# Requirements specified in dag_config.pyi

NodeVisitLimit = NewType('NodeVisitLimit', int)

BatchSize = NewType('BatchSize', int)

class DagConfig(Protocol):
    @property
    def node_visit_limit(self) -> NodeVisitLimit:
        # TODO_node_visit_limit_body
        ...

    @property
    def batch_size(self) -> BatchSize:
        # TODO_batch_size_body
        ...
