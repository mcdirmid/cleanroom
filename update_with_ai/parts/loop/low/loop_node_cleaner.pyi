# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 74a13fa61eea
# --- END CLEANROOM METADATA ---

"""Loop node cleaner low-level interface specification."""

from typing import Protocol, Sequence
from framework import operation, poly_type
import dag_storage


@poly_type
class NodeCleaner(Protocol):
    """Polymorphic service that cleans nodes sharing a role."""

    @operation
    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool:
        """Cleans dirty nodes, communicating whether processing should continue.

        Args:
            nodes: The sequence of dirty nodes sharing a role to clean.

        Returns:
            True if processing can continue, or False if an unhandleable failure occurred.

        POSTCONDITIONS:
        - MUST clean dirty nodes sharing a role.
        - MUST communicate whether processing should continue.
        - WHEN an unhandleable failure occurs while cleaning, MUST return false.
        - WHEN cleaning completes without unhandleable failure, MUST return true.
        """
        ...
