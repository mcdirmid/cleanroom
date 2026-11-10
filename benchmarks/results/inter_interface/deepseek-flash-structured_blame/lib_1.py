# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_171308_deepseek-flash_inter_interface
# Timestamp: 2026-11-08T17:13:08.708408+00:00
# Benchmark Task: inter_interface
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 120,530
#   Cached Inbound Tokens:   4,232,192
#   Outbound Tokens:         85,132
#   Total Tokens:            4,437,854
#   Financial Cost ($USD):   $0.0819
#   Wall Clock Duration:     541.47s
#   Step Latencies (s):      [205.6, 289.9, 73.9, 20.4, 135.6, 10.0, 10.1]
#   Role Execution Rounds:   coverage: 2, lib: 1, qa: 2, test: 2 (Total: 7)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       8
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: inter_interface.py ===
"""Interface definitions for resource allocator.

Formalizes the allocator low-level specification (``low/inter_interface.pyi``):
the exception hierarchy and the abstract :class:`Allocator` protocol that
coordinates balance reservations with a :class:`vault.Vault` collaborator.
"""

from __future__ import annotations

from typing import Protocol

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError
from support.lib.framework import data_type, operation, poly_type

from . import vault


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
# LAST_CLEANED: 2026-11-08T17:17:59Z
# LAST_CHANGED: 2026-11-08T17:17:59Z
# CHANGE: Implement allocator interface module: formalize low/inter_interface.pyi with @data_type AllocatorError/AllocationLimitError hierarchy and @poly_type Allocator protocol exposing allocated property plus allocate/release operations; package-qualified pretense/framework imports and vault collaborator interface import.
# --- END AUTOFAB METADATA ---


# === File: inter_interface_impl.py ===
"""Concrete implementation of the resource allocator service."""

from __future__ import annotations

from typing import Optional

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)

from . import inter_interface, vault


@singleton_type("system")
class Allocator(inter_interface.Allocator):
    """Concrete realization of resource allocator delegating reserve management to vault."""

    tier: str = "system"

    def __init__(self) -> None:
        # No funds are reserved until the first successful allocation.
        self._allocated: int = 0

    @property
    @override
    def allocated(self) -> int:
        # Exposes the internal cumulative allocation counter.
        return self._allocated

    @operation
    @override
    def allocate(self, amount: int) -> None:
        # Guard the caller precondition: allocations must be strictly positive.
        if amount <= 0:
            raise inter_interface.AllocationLimitError(
                "Allocation amount must be a positive integer."
            )
        # Resolve the collaborator vault on demand rather than registering it here.
        custodian = get_singleton(vault.Vault)
        try:
            # Delegated withdrawal reserves the funds and propagates an inactive vault.
            custodian.withdraw(amount)
        except vault.InsufficientFundsError as error:
            # Requests beyond the available reserves violate the funding limit.
            raise inter_interface.AllocationLimitError(
                "Allocation amount exceeds the available vault reserves."
            ) from error
        # Apply the cumulative allocation increment for a successful reservation.
        self._allocated += amount

    @operation
    @override
    def release(self, amount: int) -> None:
        # Guard the caller precondition: releases must be positive and held.
        if amount <= 0 or amount > self._allocated:
            raise inter_interface.AllocationLimitError(
                "Release amount must be positive and not exceed the allocated funds."
            )
        # Resolve the collaborator vault on demand rather than registering it here.
        custodian = get_singleton(vault.Vault)
        # Delegated deposit returns the funds and propagates an inactive vault.
        custodian.deposit(amount)
        # Apply the cumulative allocation decrement for a successful release.
        self._allocated -= amount


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Allocator,
        keys=[Allocator, inter_interface.Allocator],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:22:06Z
# LAST_CHANGED: 2026-11-08T17:18:05Z
# CHANGE: Implement concrete Allocator singleton: @singleton_type('system') class with tier and _allocated=0 backup state, allocated property, allocate validating positive amounts and translating vault.InsufficientFundsError into AllocationLimitError while propagating VaultInactiveException from the on-demand get_singleton(vault.Vault) collaborator, and release validating held funds then delegating deposit; auto-generated registration block preserved.
# COVERAGE_AUDIT: 2026-11-08T17:22:06Z
# QA_AUDIT: 2026-11-08T17:21:54Z
# --- END AUTOFAB METADATA ---


# === File: vault.py ===
"""Interface definitions for resource vault.

Formalizes the vault low-level specification (``low/vault.pyi``): the exception
hierarchy and the abstract :class:`Vault` custody protocol.
"""

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
# LAST_CLEANED: 2026-11-08T17:17:48Z
# LAST_CHANGED: 2026-11-08T17:17:48Z
# CHANGE: Implement vault interface module: formalize low/vault.pyi with @data_type exception hierarchy (VaultError, InsufficientFundsError, VaultInactiveException) and @poly_type Vault protocol with balance/is_active properties plus deposit, withdraw, and test-only set_active operations; package-qualified pretense/framework imports.
# --- END AUTOFAB METADATA ---


# === File: vault_impl.py ===
"""Concrete implementation of the resource vault service."""

from __future__ import annotations

from typing import Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import vault


@singleton_type("system")
class Vault(vault.Vault):
    """Concrete realization of resource vault with internal balance counter."""

    tier: str = "system"

    def __init__(self) -> None:
        # Bounded in-memory vault starts empty and available.
        self._balance: int = 0
        self._is_active: bool = True

    @property
    @override
    def balance(self) -> int:
        # Exposes the internal balance counter.
        return self._balance

    @property
    @override
    def is_active(self) -> bool:
        # Exposes the internal availability flag.
        return self._is_active

    @operation
    @override
    def deposit(self, amount: int) -> None:
        # Reject non-positive deposit requests as invalid amounts.
        if amount <= 0:
            raise vault.InsufficientFundsError(
                "Deposit amount must be a positive integer."
            )
        # An inactive vault rejects every valid deposit.
        if not self._is_active:
            raise vault.VaultInactiveException("Cannot deposit into an inactive vault.")
        # Apply the balance increment for a valid, available deposit.
        self._balance += amount

    @operation
    @override
    def withdraw(self, amount: int) -> None:
        # Reject non-positive withdrawal requests as invalid amounts.
        if amount <= 0:
            raise vault.InsufficientFundsError(
                "Withdrawal amount must be a positive integer."
            )
        # An inactive vault rejects every withdrawal, even a covered one.
        if not self._is_active:
            raise vault.VaultInactiveException(
                "Cannot withdraw from an inactive vault."
            )
        # Requests larger than the stored balance violate the funding constraint.
        if amount > self._balance:
            raise vault.InsufficientFundsError(
                "Withdrawal amount exceeds the available balance."
            )
        # Apply the balance decrement for a valid, available withdrawal.
        self._balance -= amount

    @operation
    @override
    @test_only
    def set_active(self, active: bool) -> None:
        # Test-only availability toggle.
        self._is_active = active


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Vault,
        keys=[Vault, vault.Vault],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:19:49Z
# LAST_CHANGED: 2026-11-08T17:17:53Z
# CHANGE: Implement concrete Vault singleton: @singleton_type('system') class with tier, __init__ initializing _balance=0 and _is_active=True, balance/is_active properties, deposit/withdraw enforcing invalid-amount, inactive-vault, and balance-constraint guards with exact contracted errors, and test-only set_active; auto-generated registration block preserved.
# COVERAGE_AUDIT: 2026-11-08T17:19:49Z
# QA_AUDIT: 2026-11-08T17:18:35Z
# --- END AUTOFAB METADATA ---
