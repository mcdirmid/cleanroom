"""Low-level interface specification for resource allocator."""

from __future__ import annotations

from typing import Protocol
from pretense import PretenseSpecificationError
from support.lib.framework import data_type, operation, poly_type
import vault


@data_type
class AllocatorError(PretenseSpecificationError):
    """Base exception for all allocator operations."""


@data_type
class AllocationLimitError(AllocatorError):
    """Raised when an allocation request violates funding limits."""


@poly_type
class Allocator(Protocol):
    """Resource allocator protocol for coordinating balance reservations."""

    @property
    def allocated(self) -> int:
        """Current amount of cumulative funds actively allocated."""
        ...

    @operation
    def allocate(self, amount: int) -> None:
        """Allocates funds by reserving them from the collaborator vault.

        Args:
            amount: Positive integer amount to allocate.

        Raises:
            AllocationLimitError: If amount is non-positive or exceeds available vault reserves.
            vault.VaultInactiveException: If the collaborator vault is inactive.

        PRECONDITIONS:
        - WHEN amount is less than or equal to zero, MUST raise AllocationLimitError.

        POSTCONDITIONS:
        - WHEN collaborator vault is inactive, MUST raise vault.VaultInactiveException.
        - WHEN amount exceeds available vault reserves, MUST raise AllocationLimitError.
        - WHEN successful, MUST increment allocated by amount.
        """
        ...

    @operation
    def release(self, amount: int) -> None:
        """Releases previously allocated funds back to the collaborator vault.

        Args:
            amount: Positive integer amount to release.

        Raises:
            AllocationLimitError: If amount is non-positive or exceeds allocated funds.
            vault.VaultInactiveException: If the collaborator vault is inactive.

        PRECONDITIONS:
        - WHEN amount is less than or equal to zero or exceeds allocated, MUST raise AllocationLimitError.

        POSTCONDITIONS:
        - WHEN collaborator vault is inactive, MUST raise vault.VaultInactiveException.
        - WHEN successful, MUST decrement allocated by amount.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-11-03T23:55:00Z
# LAST_CHANGED: 2026-11-03T23:55:00Z
# CHANGE: Initial creation of inter_interface low-level specification
# SPEC_QA_AUDIT: 2026-11-03T23:55:00Z
# --- END CLEANROOM METADATA ---
