# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_172215_deepseek-flash_inter_interface_pretense
# Timestamp: 2026-11-08T17:22:15.826364+00:00
# Benchmark Task: inter_interface
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 255,373
#   Cached Inbound Tokens:   24,313,856
#   Outbound Tokens:         251,842
#   Total Tokens:            24,821,071
#   Financial Cost ($USD):   $0.2624
#   Wall Clock Duration:     1456.21s
#   Step Latencies (s):      [259.6, 701.9, 84.4, 72.0, 128.0, 20.4, 41.1, 10.1, 92.9, 82.5, 448.1, 107.7, 20.4, 10.1, 78.1, 10.0]
#   Role Execution Rounds:   lib: 1, pretense: 4, pretense_coverage: 5, pretense_qa: 6 (Total: 16)
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
"""Library interface for resource allocation."""

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
# LAST_CLEANED: 2026-11-08T17:26:35Z
# LAST_CHANGED: 2026-11-08T17:26:35Z
# CHANGE: Implemented resource allocator library interface: polytype Allocator protocol with operation stubs, data-type error hierarchy (AllocatorError, AllocationLimitError), and package-qualified pretense import.
# --- END AUTOFAB METADATA ---


# === File: inter_interface_impl.py ===
"""Library implementation for resource allocation."""

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
    """Concrete realization of resource allocator delegating reserve management to vault."""

    tier: str = "system"

    def __init__(self) -> None:
        # GROUNDING: initialize the cumulative allocated counter.
        self._allocated: int = 0

    @property
    @override
    def allocated(self) -> int:
        """Current amount of cumulative funds actively allocated."""
        # GROUNDING: return the backing allocated counter.
        return self._allocated

    @operation
    @override
    def allocate(self, amount: int) -> None:
        """Allocates funds by reserving them from the collaborator vault.

        Args:
            amount: Positive integer amount to allocate.

        Raises:
            inter_interface.AllocationLimitError: If amount is non-positive or exceeds available vault reserves.
            vault.VaultInactiveException: If the collaborator vault is inactive.
        """
        # PRECONDITIONS: WHEN amount <= 0, MUST raise AllocationLimitError.
        if amount <= 0:
            raise inter_interface.AllocationLimitError(
                "Allocation amount must be greater than zero."
            )
        vault_service = get_singleton(vault.Vault)
        # PRECONDITIONS: WHEN amount exceeds available vault reserves, MUST raise AllocationLimitError.
        if amount > vault_service.balance:
            raise inter_interface.AllocationLimitError(
                "Allocation amount exceeds available vault reserves."
            )
        # POSTCONDITIONS: delegate the reserve withdrawal; an inactive vault raises
        # VaultInactiveException from the collaborator.
        vault_service.withdraw(amount)
        # POSTCONDITIONS: WHEN successful, increment allocated by amount.
        self._allocated += amount

    @operation
    @override
    def release(self, amount: int) -> None:
        """Releases previously allocated funds back to the collaborator vault.

        Args:
            amount: Positive integer amount to release.

        Raises:
            inter_interface.AllocationLimitError: If amount is non-positive or exceeds allocated funds.
            vault.VaultInactiveException: If the collaborator vault is inactive.
        """
        # PRECONDITIONS: WHEN amount <= 0 or amount > allocated, MUST raise AllocationLimitError.
        if amount <= 0 or amount > self._allocated:
            raise inter_interface.AllocationLimitError(
                "Release amount must be positive and not exceed allocated funds."
            )
        vault_service = get_singleton(vault.Vault)
        # POSTCONDITIONS: delegate the reserve deposit; an inactive vault raises
        # VaultInactiveException from the collaborator.
        vault_service.deposit(amount)
        # POSTCONDITIONS: WHEN successful, decrement allocated by amount.
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
# LAST_CLEANED: 2026-11-08T17:46:28Z
# LAST_CHANGED: 2026-11-08T17:26:45Z
# CHANGE: Implemented concrete Allocator singleton delegating reserve withdrawals/deposits to the Vault collaborator via get_singleton, with AllocationLimitError preconditions and allocated counter updates.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:46:28Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:46:04Z
# --- END AUTOFAB METADATA ---


# === File: vault.py ===
"""Library interface for bounded resource vault custody."""

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
# LAST_CLEANED: 2026-11-08T17:26:29Z
# LAST_CHANGED: 2026-11-08T17:26:29Z
# CHANGE: Implemented vault library interface: polytype Vault protocol with operation stubs, data-type error hierarchy (VaultError, InsufficientFundsError, VaultInactiveException), and package-qualified pretense import.
# --- END AUTOFAB METADATA ---


# === File: vault_impl.py ===
"""Library implementation for bounded resource vault custody."""

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
        # GROUNDING: initialize the balance counter and active flag.
        self._balance: int = 0
        self._is_active: bool = True

    @property
    @override
    def balance(self) -> int:
        """Current asset balance held in the vault."""
        # GROUNDING: return the backing balance counter.
        return self._balance

    @property
    @override
    def is_active(self) -> bool:
        """Indicates whether the vault service is currently active."""
        # GROUNDING: return the backing availability flag.
        return self._is_active

    @operation
    @override
    def deposit(self, amount: int) -> None:
        """Deposits funds into the vault.

        Args:
            amount: Positive integer amount to deposit.

        Raises:
            vault.InsufficientFundsError: If amount is non-positive.
            vault.VaultInactiveException: If the vault is inactive.
        """
        # PRECONDITIONS: WHEN amount <= 0, MUST raise InsufficientFundsError.
        if amount <= 0:
            raise vault.InsufficientFundsError("Deposit amount must be greater than zero.")
        # POSTCONDITIONS: WHEN is_active is False, MUST raise VaultInactiveException.
        if not self._is_active:
            raise vault.VaultInactiveException("Vault is inactive.")
        # POSTCONDITIONS: WHEN active and amount is positive, increment balance by amount.
        self._balance += amount

    @operation
    @override
    def withdraw(self, amount: int) -> None:
        """Withdraws funds from the vault.

        Args:
            amount: Positive integer amount to withdraw.

        Raises:
            vault.InsufficientFundsError: If amount is non-positive or exceeds balance.
            vault.VaultInactiveException: If the vault is inactive.
        """
        # PRECONDITIONS: WHEN amount <= 0 or amount > balance, MUST raise InsufficientFundsError.
        if amount <= 0 or amount > self._balance:
            raise vault.InsufficientFundsError(
                "Withdrawal amount must be positive and not exceed the balance."
            )
        # POSTCONDITIONS: WHEN is_active is False, MUST raise VaultInactiveException.
        if not self._is_active:
            raise vault.VaultInactiveException("Vault is inactive.")
        # POSTCONDITIONS: WHEN active and amount is valid, decrement balance by amount.
        self._balance -= amount

    @operation
    @override
    @test_only
    def set_active(self, active: bool) -> None:
        """Test-only hook to toggle vault availability.

        Args:
            active: Availability state to set.
        """
        # POSTCONDITIONS: MUST update is_active to active.
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
# LAST_CLEANED: 2026-11-08T17:45:10Z
# LAST_CHANGED: 2026-11-08T17:26:39Z
# CHANGE: Implemented concrete Vault singleton with tier, balance/active backing state, and contract-realized deposit/withdraw/set_active including InsufficientFundsError and VaultInactiveException branching.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:45:10Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:44:53Z
# --- END AUTOFAB METADATA ---
