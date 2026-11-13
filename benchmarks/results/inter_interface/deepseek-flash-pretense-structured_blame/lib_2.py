# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_210002_deepseek-flash_inter_interface_pretense
# Timestamp: 2026-11-12T21:00:02.679428+00:00
# Benchmark Task: inter_interface
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 159,235
#   Cached Inbound Tokens:   13,660,928
#   Outbound Tokens:         171,586
#   Total Tokens:            13,991,749
#   Financial Cost ($USD):   $0.1678
#   Wall Clock Duration:     1045.24s
#   Step Latencies (s):      [191.6, 584.5, 147.2, 10.1, 306.8, 10.1, 10.0]
#   Role Execution Rounds:   lib: 1, pretense: 2, pretense_coverage: 2, pretense_qa: 2 (Total: 7)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: inter_interface.py ===
from __future__ import annotations

from typing import Protocol

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError
from support.lib.framework import data_type, operation, poly_type


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
            AllocationLimitError: If amount is non-positive.
            vault.InsufficientFundsError: If amount exceeds available vault balance.
            vault.VaultInactiveException: If the collaborator vault is inactive.
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
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:02:59Z
# LAST_CHANGED: 2026-11-12T21:02:59Z
# CHANGE: Implement allocator interface protocol with AllocatorError, AllocationLimitError, and abstract allocated/allocate/release members mirroring low/inter_interface.pyi bases exactly.
# --- END AUTOFAB METADATA ---


# === File: inter_interface_impl.py ===
from __future__ import annotations

from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton
from . import inter_interface
from . import vault


@singleton
class Allocator(inter_interface.Allocator):
    """Resource allocator that reserves and returns funds in the collaborator vault."""

    tier = "system"

    def __init__(self) -> None:
        # No funds are allocated until a successful reservation occurs.
        self._allocated: int = 0

    @property
    @override
    def allocated(self) -> int:
        return self._allocated

    @operation
    @override
    def allocate(self, amount: int) -> None:
        # Reject non-positive requests before interacting with the vault.
        if amount <= 0:
            raise inter_interface.AllocationLimitError()
        # Reserve the amount from the collaborator vault; vault failures propagate
        # unchanged so callers can distinguish inactive vaults from funding limits.
        vault_service = get_singleton(vault.Vault)
        vault_service.withdraw(amount)
        # Track the reservation only after the vault accepted the withdrawal.
        self._allocated += amount

    @operation
    @override
    def release(self, amount: int) -> None:
        # Releases must be positive and cannot exceed outstanding allocations.
        if amount <= 0 or amount > self._allocated:
            raise inter_interface.AllocationLimitError()
        # Return the funds to the collaborator vault; inactivity propagates.
        vault_service = get_singleton(vault.Vault)
        vault_service.deposit(amount)
        # Drop the reservation only after the vault accepted the deposit.
        self._allocated -= amount

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:17:24Z
# LAST_CHANGED: 2026-11-12T21:03:07Z
# CHANGE: Implement concrete Allocator singleton with system tier and allocated backing state; allocate validates positive amounts, reserves via get_singleton(vault.Vault).withdraw propagating vault errors, and increments allocated on success; release validates bounds, deposits back, and decrements allocated.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T21:17:24Z
# PRETENSE_QA_AUDIT: 2026-11-12T21:17:12Z
# --- END AUTOFAB METADATA ---


# === File: vault.py ===
from __future__ import annotations

from typing import Protocol

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only
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
        """
        ...

    @operation
    @test_only
    def set_active(self, active: bool) -> None:
        """Test-only hook to toggle vault availability.

        Args:
            active: Availability state to set.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:02:55Z
# LAST_CHANGED: 2026-11-12T21:02:55Z
# CHANGE: Implement vault interface protocol with VaultError, InsufficientFundsError, VaultInactiveException, and abstract balance/is_active/deposit/withdraw/set_active members mirroring low/vault.pyi; uses full cross-part pretense import path.
# --- END AUTOFAB METADATA ---


# === File: vault_impl.py ===
from __future__ import annotations

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton
from . import vault


@singleton
class Vault(vault.Vault):
    """Bounded in-memory asset vault."""

    tier = "system"

    def __init__(self) -> None:
        # Start empty and available for operations.
        self._balance: int = 0
        self._is_active: bool = True

    @property
    @override
    def balance(self) -> int:
        return self._balance

    @property
    @override
    def is_active(self) -> bool:
        return self._is_active

    @operation
    @override
    def deposit(self, amount: int) -> None:
        # Reject non-positive deposits before checking availability.
        if amount <= 0:
            raise vault.InsufficientFundsError()
        # Refuse to touch the balance of an inactive vault.
        if not self._is_active:
            raise vault.VaultInactiveException()
        self._balance += amount

    @operation
    @override
    def withdraw(self, amount: int) -> None:
        # Withdrawals must be positive and covered by the current balance.
        if amount <= 0 or amount > self._balance:
            raise vault.InsufficientFundsError()
        # Refuse to touch the balance of an inactive vault.
        if not self._is_active:
            raise vault.VaultInactiveException()
        self._balance -= amount

    @operation
    @override
    @test_only
    def set_active(self, active: bool) -> None:
        # Test-only toggle of the availability flag.
        self._is_active = active

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:12:29Z
# LAST_CHANGED: 2026-11-12T21:03:03Z
# CHANGE: Implement concrete Vault singleton with system tier, balance/is_active backing state initialized to 0/True, deposit and withdraw validation (non-positive and over-balance raise InsufficientFundsError, inactive raises VaultInactiveException), and test-only set_active toggle.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T21:12:29Z
# PRETENSE_QA_AUDIT: 2026-11-12T21:10:00Z
# --- END AUTOFAB METADATA ---
