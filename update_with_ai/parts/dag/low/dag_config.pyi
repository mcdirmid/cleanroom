"""Dag config low-level interface specification."""

from typing import NewType, Protocol
from support.lib.framework import singleton_type
from support.lib.lifecycle import Singleton, SystemTier

NodeVisitLimit = NewType("NodeVisitLimit", int)
BatchSize = NewType("BatchSize", int)


@singleton_type("system")
class DagConfig(Singleton[SystemTier], Protocol):
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T03:44:39Z
# CHANGE: Contract node visit limit enforcement when a subgraph records the visits of a cleaned batch
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
