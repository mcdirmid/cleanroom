from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import dag_subgraph_impl

CONSTITUENTS = (dag_subgraph_impl,)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)


_initialize_ = __initialize__
