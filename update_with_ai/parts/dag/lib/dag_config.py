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
