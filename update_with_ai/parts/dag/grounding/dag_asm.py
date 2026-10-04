"""Dag subsystem assembly grounding specification module."""

from __future__ import annotations

from parts.dag.grounding import dag_subgraph_impl

CONSTITUENTS = (
    dag_subgraph_impl,
)


def __initialize__() -> None:
    """Aggregates topological subgraph queries and bounded visit tracking into the directed acyclic graph subsystem assembly.

    CONSTITUENTS:
    - dag_subgraph_impl.
    """
    dag_subgraph_impl.__initialize__()
