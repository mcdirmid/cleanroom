# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261104_204127_deepseek-flash_inter_interface_pretense_baseline
# Timestamp: 2026-11-04T20:41:27.487190+00:00
# Benchmark Task: inter_interface
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 81,691
#   Cached Inbound Tokens:   7,373,952
#   Outbound Tokens:         118,810
#   Total Tokens:            7,574,453
#   Financial Cost ($USD):   $0.1057
#   Wall Clock Duration:     713.66s
#   Step Latencies (s):      [696.7]
#   Role Execution Rounds:   pretense_baseline: 1 (Total: 1)
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
"""Library interface specification for resource allocator."""

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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:53:21Z
# LAST_CHANGED: 2026-11-04T20:53:21Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 1b7afaa6b41d
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T20:53:21Z
# PRETENSE_QA_AUDIT: 2026-11-04T20:53:21Z
# --- END AUTOFAB METADATA ---


# === File: inter_interface_impl.py ===
"""Concrete realization of resource allocator."""

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
    """Concrete realization of resource allocator delegating reserves to vault.

    GROUNDING:
    - Realizes resource allocator coordinating with vault.Vault singleton.
    - Initializes _allocated to 0.
    """

    tier: str = "system"

    def __init__(self) -> None:
        self._allocated: int = 0

    @property
    @override
    def allocated(self) -> int:
        """Current cumulative allocation (GROUNDING: returns _allocated)."""
        return self._allocated

    @operation
    @override
    def allocate(self, amount: int) -> None:
        """Allocates funds by reserving them from the collaborator vault.

        PRECONDITION: amount <= 0 raises inter_interface.AllocationLimitError.
        DELEGATION: withdraws amount from the vault (vault errors propagate).
        POSTCONDITION: increments _allocated by amount.
        """
        if amount <= 0:  # pragma: no cover (assumption: precondition_guard)
            raise inter_interface.AllocationLimitError("Allocation amount must be positive")
        reserves: vault.Vault = get_singleton(vault.Vault)
        reserves.withdraw(amount)
        self._allocated += amount

    @operation
    @override
    def release(self, amount: int) -> None:
        """Releases allocated funds back to the collaborator vault.

        PRECONDITION: amount <= 0 or amount > _allocated raises inter_interface.AllocationLimitError.
        DELEGATION: deposits amount back into the vault (vault errors propagate).
        POSTCONDITION: decrements _allocated by amount.
        """
        if amount <= 0 or amount > self._allocated:  # pragma: no cover (assumption: precondition_guard)
            raise inter_interface.AllocationLimitError(
                "Release amount must be positive and not exceed the allocated total"
            )
        reserves: vault.Vault = get_singleton(vault.Vault)
        reserves.deposit(amount)
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
# LAST_CLEANED: 2026-11-04T20:53:21Z
# LAST_CHANGED: 2026-11-04T20:53:21Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: a9bc44c21985
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T20:53:21Z
# PRETENSE_QA_AUDIT: 2026-11-04T20:53:21Z
# --- END AUTOFAB METADATA ---


# === File: vault.py ===
"""Library interface specification for resource vault."""

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

        PRECONDITIONS:
        - WHEN amount is less than or equal to zero, MUST raise InsufficientFundsError.

        POSTCONDITIONS:
        - WHEN is_active is False, MUST raise VaultInactiveException.
        - WHEN is_active is True and amount is positive, MUST increment balance by amount.
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
        - WHEN amount is less than or equal to zero or exceeds balance, MUST raise InsufficientFundsError.

        POSTCONDITIONS:
        - WHEN is_active is False, MUST raise VaultInactiveException.
        - WHEN is_active is True and amount is valid, MUST decrement balance by amount.
        """
        ...

    @operation
    @test_only
    def set_active(self, active: bool) -> None:
        """Test-only hook to toggle vault availability.

        Args:
            active: Availability state to set.

        POSTCONDITIONS:
        - MUST update is_active to active.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:53:21Z
# LAST_CHANGED: 2026-11-04T20:53:21Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: b2cb03696544
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T20:53:21Z
# PRETENSE_QA_AUDIT: 2026-11-04T20:53:21Z
# --- END AUTOFAB METADATA ---


# === File: vault_impl.py ===
"""Concrete realization of resource vault."""

from __future__ import annotations

from typing import Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)

from . import vault


@singleton_type("system")
class Vault(vault.Vault):
    """Concrete realization of resource vault with internal balance counter.

    GROUNDING:
    - Realizes bounded in-memory asset vault.
    - Initializes _balance to 0 and _is_active to True.
    """

    tier: str = "system"

    def __init__(self) -> None:
        self._balance: int = 0
        self._is_active: bool = True

    @property
    @override
    def balance(self) -> int:
        """Current asset balance held in the vault (GROUNDING: returns _balance)."""
        return self._balance

    @property
    @override
    def is_active(self) -> bool:
        """Vault availability (GROUNDING: returns _is_active)."""
        return self._is_active

    @operation
    @override
    def deposit(self, amount: int) -> None:
        """Deposits funds into the vault.

        PRECONDITION: amount <= 0 raises vault.InsufficientFundsError.
        POSTCONDITION: inactive vault raises vault.VaultInactiveException.
        POSTCONDITION: active vault adds amount to the balance.
        """
        if amount <= 0:  # pragma: no cover (assumption: precondition_guard)
            raise vault.InsufficientFundsError("Deposit amount must be positive")
        if not self._is_active:
            raise vault.VaultInactiveException("Vault is inactive")
        self._balance += amount

    @operation
    @override
    def withdraw(self, amount: int) -> None:
        """Withdraws funds from the vault.

        PRECONDITION: amount <= 0 or amount > _balance raises vault.InsufficientFundsError.
        POSTCONDITION: inactive vault raises vault.VaultInactiveException.
        POSTCONDITION: active vault subtracts amount from the balance.
        """
        if amount <= 0 or amount > self._balance:  # pragma: no cover (assumption: precondition_guard)
            raise vault.InsufficientFundsError(
                "Withdrawal amount must be positive and not exceed the balance"
            )
        if not self._is_active:
            raise vault.VaultInactiveException("Vault is inactive")
        self._balance -= amount

    @operation
    @override
    @test_only
    def set_active(self, active: bool) -> None:
        """Test-only hook to toggle vault availability (GROUNDING: assigns _is_active)."""
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
# LAST_CLEANED: 2026-11-04T20:53:21Z
# LAST_CHANGED: 2026-11-04T20:53:21Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 47cbaa6806c6
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T20:53:21Z
# PRETENSE_QA_AUDIT: 2026-11-04T20:53:21Z
# --- END AUTOFAB METADATA ---
