# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: a56f31c647ed
# GROUNDING_QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

"""Dag config grounding specification module."""

from __future__ import annotations
from typing import NewType, Protocol
from support.lib.grounding_support import InTier, SystemTier

NodeVisitLimit = NewType("NodeVisitLimit", int)
BatchSize = NewType("BatchSize", int)


class DagConfig(InTier[SystemTier], Protocol):
    """System service providing graph traversal and batching limits."""

    @property
    def node_visit_limit(self) -> NodeVisitLimit:
        """
        DEFERRED:
        - Bound on the maximum number of times any node can be visited.
        """
        raise NotImplementedError

    @property
    def batch_size(self) -> BatchSize:
        """
        DEFERRED:
        - Bound on the maximum number of dirty nodes of the same role processed together.
        """
        raise NotImplementedError
