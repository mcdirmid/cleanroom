"""
lib/dag_cleaner_asm.py

Assembly of the DAG cleaner component.

Performs configuration and assembly only: subclasses DagCleanerImpl over a supplied
graph storage and clean logic. Implements no functionality beyond assembly,
and is never tested.

Library usage:
    from testing.lib.dag_cleaner_asm import DagCleanerAsm
    dag_cleaner = DagCleanerAsm(graph, clean_logic)
"""

from __future__ import annotations

from .dag_clean_logic import DagCleanLogic
from .build_graph_storage import BuildGraphStorage
from .dag_cleaner_impl import DagCleanerImpl


class DagCleanerAsm(DagCleanerImpl):
    """
    Assembles the concrete DAG cleaner implementation (configuration and assembly
    only; no other functionality).
    """

    def __init__(
        self,
        storage: BuildGraphStorage,
        clean_logic: DagCleanLogic,
    ) -> None:
        super().__init__(storage=storage, clean_logic=clean_logic)
