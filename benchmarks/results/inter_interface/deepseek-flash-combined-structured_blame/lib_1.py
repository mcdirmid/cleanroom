# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_172432_deepseek-flash_inter_interface_combined
# Timestamp: 2026-11-08T17:24:32.691789+00:00
# Benchmark Task: inter_interface
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 423,495
#   Cached Inbound Tokens:   40,182,144
#   Outbound Tokens:         439,133
#   Total Tokens:            41,044,772
#   Financial Cost ($USD):   $0.4476
#   Wall Clock Duration:     2551.11s
#   Step Latencies (s):      [158.2, 327.3, 20.4, 20.5, 672.1, 282.3, 293.0, 62.3, 191.8, 106.2, 104.3, 20.6, 10.1, 410.6, 242.7, 41.5, 85.2, 74.8, 112.7, 46.0, 10.1, 129.2, 10.1, 10.1, 245.1, 53.8, 10.2, 10.1]
#   Role Execution Rounds:   coverage: 2, lib: 2, pretense: 7, pretense_coverage: 4, pretense_qa: 8, qa: 3, test: 2 (Total: 28)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       14
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: inter_interface.py ===
"""Library interface formalizing the low-level resource allocator specification."""

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
        """
        ...

    @operation
    def release(self, amount: int) -> None:
        """Releases previously allocated funds back to the collaborator vault.

        Args:
            amount: Positive integer amount to release.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:30:11Z
# LAST_CHANGED: 2026-11-08T17:30:11Z
# CHANGE: Implement allocator interface: AllocatorError/AllocationLimitError data types and Allocator protocol with allocated property plus allocate/release operation stubs
# --- END AUTOFAB METADATA ---


# === File: inter_interface_impl.py ===
"""Library implementation of the resource allocator service."""

from __future__ import annotations

from typing import Optional

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)

from . import inter_interface
from . import vault


@singleton_type("system")
class Allocator(inter_interface.Allocator):
    """Concrete resource allocator delegating reserve management to the vault."""

    tier: str = "system"

    def __init__(self) -> None:
        self._allocated: int = 0

    @property
    @override
    def allocated(self) -> int:
        return self._allocated

    @operation
    @override
    def allocate(self, amount: int) -> None:
        # non-positive allocations are rejected before touching the vault
        if amount <= 0:
            raise inter_interface.AllocationLimitError(
                "allocation amount must be positive"
            )
        # reserves are held by the collaborator vault
        reserved = get_singleton(vault.Vault)
        # unavailable vaults reject any allocation request
        if not reserved.is_active:
            raise vault.VaultInactiveException("vault is inactive")
        # requests beyond the currently available reserves are rejected up front
        if amount > reserved.balance:
            raise inter_interface.AllocationLimitError(
                "allocation exceeds available vault reserves"
            )
        reserved.withdraw(amount)
        self._allocated += amount

    @operation
    @override
    def release(self, amount: int) -> None:
        # non-positive releases and releases exceeding the reservation are rejected
        if amount <= 0 or amount > self._allocated:
            raise inter_interface.AllocationLimitError("invalid release amount")
        # released funds are returned to the collaborator vault
        reserved = get_singleton(vault.Vault)
        # unavailable vaults reject any release request
        if not reserved.is_active:
            raise vault.VaultInactiveException("vault is inactive")
        reserved.deposit(amount)
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
# LAST_CLEANED: 2026-11-08T18:06:59Z
# LAST_CHANGED: 2026-11-08T17:59:41Z
# CHANGE: Allocate now validates vault availability and available reserves before withdrawing: inactive vault raises VaultInactiveException and over-reserve requests raise AllocationLimitError; release also guards vault availability
# COVERAGE_AUDIT: 2026-11-08T18:04:17Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T18:06:59Z
# PRETENSE_QA_AUDIT: 2026-11-08T18:06:48Z
# QA_AUDIT: 2026-11-08T18:04:05Z
# --- END AUTOFAB METADATA ---


# === File: vault.py ===
"""Library interface formalizing the low-level resource vault specification."""

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
        """
        ...

    @operation
    def withdraw(self, amount: int) -> None:
        """Withdraws funds from the vault.

        Args:
            amount: Positive integer amount to withdraw.
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
# LAST_CLEANED: 2026-11-08T17:30:00Z
# LAST_CHANGED: 2026-11-08T17:30:00Z
# CHANGE: Implement vault interface: frozen exception types, Vault protocol with balance/is_active/deposit/withdraw/set_active stubs, decorators and framework imports
# --- END AUTOFAB METADATA ---


# === File: vault_impl.py ===
"""Library implementation of the resource vault service."""

from __future__ import annotations

from typing import Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import vault


@singleton_type("system")
class Vault(vault.Vault):
    """Concrete resource vault backed by an internal balance counter."""

    tier: str = "system"

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
        # non-positive deposits are rejected before any state changes
        if amount <= 0:
            raise vault.InsufficientFundsError("deposit amount must be positive")
        if not self._is_active:
            raise vault.VaultInactiveException("vault is inactive")
        self._balance += amount

    @operation
    @override
    def withdraw(self, amount: int) -> None:
        # non-positive or over-balance withdrawals are rejected before any state changes
        if amount <= 0 or amount > self._balance:
            raise vault.InsufficientFundsError("invalid withdrawal amount")
        if not self._is_active:
            raise vault.VaultInactiveException("vault is inactive")
        self._balance -= amount

    @operation
    @override
    @test_only
    def set_active(self, active: bool) -> None:
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
# LAST_CLEANED: 2026-11-08T17:52:15Z
# LAST_CHANGED: 2026-11-08T17:30:06Z
# CHANGE: Implement concrete Vault singleton: initialize _balance=0/_is_active=True, expose balance/is_active, deposit/withdraw with validation and inactive guards, test-only set_active; keep auto-generated registration
# COVERAGE_AUDIT: 2026-11-08T17:31:08Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:52:15Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:51:51Z
# QA_AUDIT: 2026-11-08T17:30:45Z
# --- END AUTOFAB METADATA ---
