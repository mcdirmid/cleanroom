# Requirements specified in loop_cleaner.pyi
from typing import Protocol
from . import loop_node_cleaner
from update_with_ai.parts.dag.lib import dag_storage


class LoopCleaner(Protocol):
    def clean(
        self, node: dag_storage.Node, cleaner: loop_node_cleaner.NodeCleaner
    ) -> None: ...
