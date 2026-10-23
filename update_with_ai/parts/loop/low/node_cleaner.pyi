"""Loop node cleaner low-level interface specification."""

from typing import Protocol, Sequence
from support.lib.framework import operation, poly_type
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
            True if processing can continue, or False when cleaning fails for nodes that no other node cleaning can address.

        PRECONDITIONS:
        - A caller supplies dirty nodes when cleaning nodes.

        POSTCONDITIONS:
        - MUST clean dirty nodes sharing a role.
        - MUST communicate whether processing should continue.
        - WHEN cleaning fails for nodes that no other node cleaning can address, MUST return false.
        - WHEN cleaning does not fail for nodes that no other node cleaning can address, MUST return true.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T03:19:47Z
# CHANGE: Align node cleaner continuation and unaddressable failure contracts
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
