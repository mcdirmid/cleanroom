# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261104_204126_deepseek-flash_inter_interface_baseline
# Timestamp: 2026-11-04T20:41:26.481441+00:00
# Benchmark Task: inter_interface
# Model: deepseek-flash (Tier 2)
# Methodology: baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 48,034
#   Cached Inbound Tokens:   1,986,816
#   Outbound Tokens:         38,356
#   Total Tokens:            2,073,206
#   Financial Cost ($USD):   $0.0362
#   Wall Clock Duration:     277.98s
#   Step Latencies (s):      [263.2]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       4
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: inter_interface.py ===
"""Low-level interface specification for resource allocator."""

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
        """Allocates funds by reserving them from the collaborator vault."""
        ...

    @operation
    def release(self, amount: int) -> None:
        """Releases previously allocated funds back to the collaborator vault."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:46:04Z
# LAST_CHANGED: 2026-11-04T20:46:04Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 512430c67ae6
# COVERAGE_AUDIT: 2026-11-04T20:46:04Z
# QA_AUDIT: 2026-11-04T20:46:04Z
# --- END AUTOFAB METADATA ---


# === File: inter_interface_impl.py ===
"""Low-level implementation specification for resource allocator."""

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

    tier = system

    def __init__(self) -> None:
        # Backing state initialized to zero cumulative allocation (GROUNDING).
        self._allocated: int = 0

    @property
    @override
    def allocated(self) -> int:
        # Unconditional postcondition: expose cumulative allocation.
        return self._allocated

    @operation
    @override
    def allocate(self, amount: int) -> None:
        # PRECONDITION: amount must be positive.
        if amount <= 0:  # unreachable (assumption: precondition_guard)
            raise inter_interface.AllocationLimitError()
        # POSTCONDITION: reserve funds from the collaborator vault.
        get_singleton(vault.Vault).withdraw(amount)
        # POSTCONDITION: successful allocation increments cumulative total.
        self._allocated += amount

    @operation
    @override
    def release(self, amount: int) -> None:
        # PRECONDITION: amount must be positive and within allocated funds.
        if amount <= 0 or amount > self._allocated:  # unreachable (assumption: precondition_guard)
            raise inter_interface.AllocationLimitError()
        # POSTCONDITION: return funds to the collaborator vault.
        get_singleton(vault.Vault).deposit(amount)
        # POSTCONDITION: successful release decrements cumulative total.
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
# LAST_CLEANED: 2026-11-04T20:46:04Z
# LAST_CHANGED: 2026-11-04T20:46:04Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: e929e09c1c96
# COVERAGE_AUDIT: 2026-11-04T20:46:04Z
# QA_AUDIT: 2026-11-04T20:46:04Z
# --- END AUTOFAB METADATA ---


# === File: vault.py ===
"""Low-level interface specification for resource vault."""

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
        """Deposits funds into the vault."""
        ...

    @operation
    def withdraw(self, amount: int) -> None:
        """Withdraws funds from the vault."""
        ...

    @operation
    @test_only
    def set_active(self, active: bool) -> None:
        """Test-only hook to toggle vault availability."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:46:04Z
# LAST_CHANGED: 2026-11-04T20:46:04Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 3e8f55266efb
# COVERAGE_AUDIT: 2026-11-04T20:46:04Z
# QA_AUDIT: 2026-11-04T20:46:04Z
# --- END AUTOFAB METADATA ---


# === File: vault_impl.py ===
"""Low-level implementation specification for resource vault."""

from __future__ import annotations

from typing import Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import vault


@singleton_type("system")
class Vault(vault.Vault):
    """Concrete realization of resource vault with internal balance counter."""

    tier = system

    def __init__(self) -> None:
        # Backing state initialized to empty and active vault (GROUNDING).
        self._balance: int = 0
        self._is_active: bool = True

    @property
    @override
    def balance(self) -> int:
        # Unconditional postcondition: expose internal balance.
        return self._balance

    @property
    @override
    def is_active(self) -> bool:
        # Unconditional postcondition: expose availability flag.
        return self._is_active

    @operation
    @override
    def deposit(self, amount: int) -> None:
        # PRECONDITION: amount must be positive.
        if amount <= 0:  # unreachable (assumption: precondition_guard)
            raise vault.InsufficientFundsError()
        # POSTCONDITION: inactive vault refuses deposits.
        if not self._is_active:
            raise vault.VaultInactiveException()
        # POSTCONDITION: positive deposit increments balance.
        self._balance += amount

    @operation
    @override
    def withdraw(self, amount: int) -> None:
        # PRECONDITION: amount must be positive and within balance.
        if amount <= 0 or amount > self._balance:  # unreachable (assumption: precondition_guard)
            raise vault.InsufficientFundsError()
        # POSTCONDITION: inactive vault refuses withdrawals.
        if not self._is_active:
            raise vault.VaultInactiveException()
        # POSTCONDITION: valid withdrawal decrements balance.
        self._balance -= amount

    @operation
    @override
    @test_only
    def set_active(self, active: bool) -> None:
        # POSTCONDITION: availability flag updated to requested state.
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
# LAST_CLEANED: 2026-11-04T20:46:04Z
# LAST_CHANGED: 2026-11-04T20:46:04Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 63941e0c24a6
# COVERAGE_AUDIT: 2026-11-04T20:46:04Z
# QA_AUDIT: 2026-11-04T20:46:04Z
# --- END AUTOFAB METADATA ---
