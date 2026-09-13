"""DAG configuration interface and data types."""

from typing import Protocol

NodeVisitLimit = int


class DagConfig(Protocol):
    @property
    def node_visit_limit(self) -> NodeVisitLimit: ...
