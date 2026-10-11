# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:02Z
# LAST_CHANGED: 2026-10-11T03:44:39Z
# CHANGE: Contract node visit limit enforcement when a subgraph records the visits of a cleaned batch
# CODE_HASH: fd74c616a8d2
# SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
# --- END CLEANROOM METADATA ---

"""Dag config low-level interface specification."""

from typing import NewType, Protocol
from framework import singleton_type
from support.lib.lifecycle import InTier, SystemTier

NodeVisitLimit = NewType("NodeVisitLimit", int)
BatchSize = NewType("BatchSize", int)


@singleton_type("system")
class DagConfig(InTier[SystemTier], Protocol):
    """System service exposing operational limits governing graph node visit caps and dirty node batch sizes during cleaning passes."""

    @property
    def node_visit_limit(self) -> NodeVisitLimit:
        """Bound on the number of visits any node receives across dependency graph cleaning, enforced when a subgraph records the visits of a cleaned batch.

        POSTCONDITIONS:
        - MUST enforce the node visit limit when a subgraph records the visits of a cleaned batch.
        """
        ...

    @property
    def batch_size(self) -> BatchSize:
        """Bound on the number of dirty nodes of the same role address collected into a single cleaning batch."""
        ...
