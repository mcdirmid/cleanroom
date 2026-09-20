# Requirements specified in dag_subgraph.pyi
from typing import List, Protocol, Sequence
from update_with_ai.parts.dag.lib import dag_storage


class DagSubgraph(Protocol):
    def set_target(self, root: dag_storage.Node) -> None: ...

    @property
    def is_complete(self) -> bool: ...

    def next_ready_batch(self) -> List[dag_storage.Node]: ...

    def record_visit(self, nodes: Sequence[dag_storage.Node]) -> None: ...
