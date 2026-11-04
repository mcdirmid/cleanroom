# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261104_204125_deepseek-flash_inter_interface
# Timestamp: 2026-11-04T20:41:25.469509+00:00
# Benchmark Task: inter_interface
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 74,051
#   Cached Inbound Tokens:   2,482,944
#   Outbound Tokens:         57,070
#   Total Tokens:            2,614,065
#   Financial Cost ($USD):   $0.0528
#   Wall Clock Duration:     275.52s
#   Step Latencies (s):      [206.7, 226.3, 10.4, 10.3]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       6
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: inter_interface.py ===
"""Library interface for the resource allocator abstraction."""

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
# LAST_CLEANED: 2026-11-04T20:44:38Z
# LAST_CHANGED: 2026-11-04T20:44:38Z
# CHANGE: Implemented allocator library interface: @data_type exception hierarchy (AllocatorError, AllocationLimitError) and @poly_type Allocator protocol with contract docstrings; imports use package-qualified pretense path and sibling vault import.
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
    """Concrete realization of resource allocator delegating reserve management to vault.

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
        """Current amount of cumulative funds actively allocated."""
        # GROUNDING: expose the cumulative amount reserved from the collaborator vault.
        return self._allocated

    @operation
    @override
    def allocate(self, amount: int) -> None:
        """Allocates funds by reserving them from the collaborator vault.

        Args:
            amount: Positive integer amount to allocate.

        Raises:
            inter_interface.AllocationLimitError: If amount is non-positive.
            vault.InsufficientFundsError: If amount exceeds available vault balance.
            vault.VaultInactiveException: If the collaborator vault is inactive.
        """
        # PRECONDITION: WHEN amount is non-positive, MUST raise AllocationLimitError.
        if amount <= 0:
            raise inter_interface.AllocationLimitError()
        # POSTCONDITION: reserve the funds; inactivity and insufficient reserves
        # propagate from the collaborator vault's withdraw contract.
        get_singleton(vault.Vault).withdraw(amount)
        # POSTCONDITION: WHEN successful, increment allocated by amount.
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
        # PRECONDITION: WHEN amount is non-positive or exceeds allocated, MUST raise AllocationLimitError.
        if amount <= 0 or amount > self._allocated:
            raise inter_interface.AllocationLimitError()
        # POSTCONDITION: return the funds; inactivity propagates from the
        # collaborator vault's deposit contract.
        get_singleton(vault.Vault).deposit(amount)
        # POSTCONDITION: WHEN successful, decrement allocated by amount.
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
# LAST_CLEANED: 2026-11-04T20:45:55Z
# LAST_CHANGED: 2026-11-04T20:45:00Z
# CHANGE: Implemented Allocator singleton: tier='system', __init__ backs _allocated=0, allocated property, allocate validates positive amount (AllocationLimitError) then delegates withdraw to get_singleton(vault.Vault) and increments, release validates bounds then delegates deposit and decrements; auto-generated __initialize__ preserved.
# COVERAGE_AUDIT: 2026-11-04T20:45:55Z
# QA_AUDIT: 2026-11-04T20:45:42Z
# --- END AUTOFAB METADATA ---


# === File: vault.py ===
"""Library interface for the resource vault abstraction."""

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
# LAST_CLEANED: 2026-11-04T20:44:34Z
# LAST_CHANGED: 2026-11-04T20:44:34Z
# CHANGE: Implemented vault library interface: @data_type exception hierarchy (VaultError, InsufficientFundsError, VaultInactiveException) and @poly_type Vault protocol with contract docstrings; replaced bare pretense import with full package path.
# --- END AUTOFAB METADATA ---


# === File: vault_impl.py ===
"""Library implementation of the resource vault service."""

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
        """Current asset balance held in the vault."""
        # GROUNDING: expose the current internal balance counter.
        return self._balance

    @property
    @override
    def is_active(self) -> bool:
        """Indicates whether the vault service is currently active."""
        # GROUNDING: expose the current availability flag.
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
        # PRECONDITION: WHEN amount is non-positive, MUST raise InsufficientFundsError.
        if amount <= 0:
            raise vault.InsufficientFundsError()
        # POSTCONDITION: WHEN is_active is False, MUST raise VaultInactiveException.
        if not self._is_active:
            raise vault.VaultInactiveException()
        # POSTCONDITION: WHEN active and amount is positive, increment balance by amount.
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
        # PRECONDITION: WHEN amount is non-positive or exceeds balance, MUST raise InsufficientFundsError.
        if amount <= 0 or amount > self._balance:
            raise vault.InsufficientFundsError()
        # POSTCONDITION: WHEN is_active is False, MUST raise VaultInactiveException.
        if not self._is_active:
            raise vault.VaultInactiveException()
        # POSTCONDITION: WHEN active and amount is valid, decrement balance by amount.
        self._balance -= amount

    @operation
    @override
    @test_only
    def set_active(self, active: bool) -> None:
        """Test-only hook to toggle vault availability.

        Args:
            active: Availability state to set.
        """
        # POSTCONDITION: MUST update is_active to active.
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
# LAST_CLEANED: 2026-11-04T20:45:57Z
# LAST_CHANGED: 2026-11-04T20:44:55Z
# CHANGE: Implemented Vault singleton: tier='system', __init__ backs _balance=0/_is_active=True, balance/is_active properties, deposit/withdraw enforce amount and activity contracts, test-only set_active; auto-generated __initialize__ preserved.
# COVERAGE_AUDIT: 2026-11-04T20:45:57Z
# QA_AUDIT: 2026-11-04T20:45:43Z
# --- END AUTOFAB METADATA ---
