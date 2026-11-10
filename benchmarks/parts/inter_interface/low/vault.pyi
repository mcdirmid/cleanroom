"""Low-level interface specification for resource vault."""

from __future__ import annotations

from typing import Protocol
from pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type


@data_type
class VaultError(PretenseSpecificationError):
    """Base exception for all vault operations."""


@data_type
class InsufficientFundsError(VaultError):
    """Raised when deposit or withdrawal violates balance constraints."""


@data_type
class VaultInactiveException(Exception):
    """Raised when attempting an operation on an inactive vault."""


@poly_type
class Vault(Protocol):
    """Resource vault protocol for bounded asset custody."""

    @property
    def balance(self) -> int:
        """Current asset balance held in the vault."""
        ...

    @property
    def is_active(self) -> bool:
        """Indicates whether the vault service is currently active."""
        ...

    @operation
    def deposit(self, amount: int) -> None:
        """Deposits funds into the vault.

        Args:
            amount: Positive integer amount to deposit.

        Raises:
            InsufficientFundsError: If amount is less than or equal to zero.
            VaultInactiveException: If the vault is inactive.

        PRECONDITIONS:
        - [slug:vault.deposit.invalid_amount]: WHEN amount is less than or equal to zero, MUST raise InsufficientFundsError.

        POSTCONDITIONS:
        - [slug:vault.deposit.inactive_vault]: WHEN is_active is False, MUST raise VaultInactiveException.
        - [slug:vault.deposit.increment_balance]: WHEN is_active is True and amount is positive, MUST increment balance by amount.
        """
        ...

    @operation
    def withdraw(self, amount: int) -> None:
        """Withdraws funds from the vault.

        Args:
            amount: Positive integer amount to withdraw.

        Raises:
            InsufficientFundsError: If amount is non-positive or exceeds balance.
            VaultInactiveException: If the vault is inactive.

        PRECONDITIONS:
        - [slug:vault.withdraw.invalid_amount]: WHEN amount is less than or equal to zero or exceeds balance, MUST raise InsufficientFundsError.

        POSTCONDITIONS:
        - [slug:vault.withdraw.inactive_vault]: WHEN is_active is False, MUST raise VaultInactiveException.
        - [slug:vault.withdraw.decrement_balance]: WHEN is_active is True and amount is valid, MUST decrement balance by amount.
        """
        ...

    @operation
    @test_only
    def set_active(self, active: bool) -> None:
        """Test-only hook to toggle vault availability.

        Args:
            active: Availability state to set.

        POSTCONDITIONS:
        - [slug:vault.set_active.update_active_state]: MUST update is_active to active.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-11-03T23:55:00Z
# LAST_CHANGED: 2026-11-03T23:55:00Z
# CHANGE: Initial creation of vault low-level specification
# SPEC_QA_AUDIT: 2026-11-03T23:55:00Z
# --- END CLEANROOM METADATA ---
