# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_233022_deepseek-flash_inter_interface_pretense
# Timestamp: 2026-11-12T23:30:22.019183+00:00
# Benchmark Task: inter_interface
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 221,729
#   Cached Inbound Tokens:   28,796,800
#   Outbound Tokens:         292,050
#   Total Tokens:            29,310,579
#   Financial Cost ($USD):   $0.2949
#   Wall Clock Duration:     2043.22s
#   Step Latencies (s):      [180.8, 387.0, 282.0, 375.1, 95.4, 220.1, 116.2, 157.8, 179.6, 324.9, 20.6, 20.4]
#   Role Execution Rounds:   lib: 1, pretense: 5, pretense_coverage: 1, pretense_qa: 5 (Total: 12)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       2
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: inter_interface.py ===
"""Interface specification for resource allocator."""

from __future__ import annotations

from typing import Protocol

from pretense import PretenseSpecificationError
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
            AllocationLimitError: If amount is non-positive or exceeds available vault reserves.
            VaultInactiveException: If the collaborator vault is inactive.
        """
        ...

    @operation
    def release(self, amount: int) -> None:
        """Releases previously allocated funds back to the collaborator vault.

        Args:
            amount: Positive integer amount to release.

        Raises:
            AllocationLimitError: If amount is non-positive or exceeds allocated funds.
            VaultInactiveException: If the collaborator vault is inactive.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T23:33:02Z
# LAST_CHANGED: 2026-11-12T23:33:02Z
# CHANGE: Implement allocator interface protocol: exception hierarchy and abstract Allocator protocol with allocated, allocate, and release stubs per low/inter_interface.pyi.
# --- END AUTOFAB METADATA ---


# === File: inter_interface_impl.py ===
"""Implementation specification for resource allocator."""

from __future__ import annotations

from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton

from . import inter_interface, vault


@singleton
class Allocator(inter_interface.Allocator):
    """Concrete realization of resource allocator delegating reserve management to vault."""

    tier = "system"

    def __init__(self) -> None:
        self._allocated: int = 0

    @property
    @override
    def allocated(self) -> int:
        return self._allocated

    @operation
    @override
    def allocate(self, amount: int) -> None:
        # Reject non-positive allocation requests outright.
        if amount <= 0:
            raise inter_interface.AllocationLimitError()
        vault_service = get_singleton(vault.Vault)
        try:
            # Reserve the funds from the collaborator vault.
            vault_service.withdraw(amount)
        except vault.InsufficientFundsError:
            # Insufficient vault reserves are reported as a funding limit violation.
            raise inter_interface.AllocationLimitError() from None
        self._allocated += amount

    @operation
    @override
    def release(self, amount: int) -> None:
        # Reject releases that are non-positive or exceed the allocated funds.
        if amount <= 0 or amount > self._allocated:
            raise inter_interface.AllocationLimitError()
        vault_service = get_singleton(vault.Vault)
        # Return the released funds to the collaborator vault.
        vault_service.deposit(amount)
        self._allocated -= amount

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:04:11Z
# LAST_CHANGED: 2026-11-12T23:33:13Z
# CHANGE: Implement concrete Allocator singleton: initializes allocated counter, validates positive and limit-bounded amounts, reserves funds via vault.withdraw translating InsufficientFundsError to AllocationLimitError, releases via vault.deposit, and maintains allocated balance per low/inter_interface_impl.pyi.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:04:11Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:03:47Z
# --- END AUTOFAB METADATA ---


# === File: vault.py ===
"""Interface specification for resource vault."""

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
# LAST_CLEANED: 2026-11-12T23:32:57Z
# LAST_CHANGED: 2026-11-12T23:32:57Z
# CHANGE: Implement vault interface protocol: exception hierarchy and abstract Vault protocol with balance, is_active, deposit, withdraw, and test-only set_active stubs per low/vault.pyi.
# --- END AUTOFAB METADATA ---


# === File: vault_impl.py ===
"""Implementation specification for resource vault."""

from __future__ import annotations

from pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from . import vault


@singleton
class Vault(vault.Vault):
    """Concrete realization of resource vault with internal balance counter."""

    tier = "system"

    def __init__(self) -> None:
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
        # Reject non-positive deposits before touching the balance.
        if amount <= 0:
            raise vault.InsufficientFundsError()
        # Inactive vaults reject all deposits.
        if not self._is_active:
            raise vault.VaultInactiveException()
        self._balance += amount

    @operation
    @override
    def withdraw(self, amount: int) -> None:
        # Reject non-positive withdrawals and overdrafts before touching the balance.
        if amount <= 0 or amount > self._balance:
            raise vault.InsufficientFundsError()
        # Inactive vaults reject all withdrawals.
        if not self._is_active:
            raise vault.VaultInactiveException()
        self._balance -= amount

    @operation
    @override
    @test_only
    def set_active(self, active: bool) -> None:
        self._is_active = active

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:04:13Z
# LAST_CHANGED: 2026-11-12T23:33:08Z
# CHANGE: Implement concrete Vault singleton: initializes balance and active state, enforces positive amounts and inactive-vault guards, mutates balance on deposit/withdraw, and supports test-only set_active per low/vault_impl.pyi.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:04:13Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:03:50Z
# --- END AUTOFAB METADATA ---
