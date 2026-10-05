# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 1f5d37aab721
# --- END CLEANROOM METADATA ---

# Requirements specified in dag_config.pyi
"""DAG configuration interface and data types."""

from typing import Protocol

NodeVisitLimit = int
BatchSize = int


class DagConfig(Protocol):
    @property
    def node_visit_limit(self) -> NodeVisitLimit: ...

    @property
    def batch_size(self) -> BatchSize: ...
