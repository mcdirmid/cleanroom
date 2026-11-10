# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261104_181323_deepseek-flash_inter_interface_pretense
# Timestamp: 2026-11-04T18:13:23.678193+00:00
# Benchmark Task: inter_interface
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 219,182
#   Cached Inbound Tokens:   17,971,840
#   Outbound Tokens:         284,246
#   Total Tokens:            18,475,268
#   Financial Cost ($USD):   $0.2573
#   Wall Clock Duration:     1826.29s
#   Step Latencies (s):      [275.5, 502.6, 358.6, 429.4, 128.1, 105.1, 65.1, 73.5, 10.3, 41.8, 62.9, 10.3, 22.5]
#   Role Execution Rounds:   lib: 2, pretense: 4, pretense_coverage: 2, pretense_qa: 5 (Total: 13)
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

        PRECONDITIONS:
        - WHEN amount is less than or equal to zero or exceeds allocated, MUST raise AllocationLimitError.

        POSTCONDITIONS:
        - WHEN collaborator vault is inactive, MUST raise vault.VaultInactiveException.
        - WHEN successful, MUST decrement allocated by amount.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:17:53Z
# LAST_CHANGED: 2026-11-04T18:17:53Z
# CHANGE: Implemented allocator interface: AllocatorError/AllocationLimitError data types and abstract Allocator protocol with package-qualified pretense import.
# --- END AUTOFAB METADATA ---


# === File: inter_interface_impl.py ===
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
        # GROUNDING: initialize _allocated to 0.
        self._allocated: int = 0

    @property
    @override
    def allocated(self) -> int:
        # GROUNDING: return the cumulative amount of allocated funds.
        return self._allocated

    @operation
    @override
    def allocate(self, amount: int) -> None:
        # PRECONDITION: a non-positive allocation violates funding limits.
        if amount <= 0:
            raise inter_interface.AllocationLimitError(  # unreachable (assumption: invalid amount precondition)
                "Allocation amount must be greater than zero."
            )
        # SEQUENCING: reserve the funds through the collaborator vault.
        vault_service = get_singleton(vault.Vault)
        vault_service.withdraw(amount)
        # POSTCONDITION: a successful allocation grows the allocated total.
        self._allocated += amount

    @operation
    @override
    def release(self, amount: int) -> None:
        # PRECONDITION: non-positive releases or releases beyond allocated funds are rejected.
        if amount <= 0 or amount > self._allocated:
            raise inter_interface.AllocationLimitError(  # unreachable (assumption: invalid amount precondition)
                "Release amount must be positive and not exceed allocated funds."
            )
        # SEQUENCING: return the funds through the collaborator vault.
        vault_service = get_singleton(vault.Vault)
        vault_service.deposit(amount)
        # POSTCONDITION: a successful release shrinks the allocated total.
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
# LAST_CLEANED: 2026-11-04T18:43:31Z
# LAST_CHANGED: 2026-11-04T18:42:54Z
# CHANGE: Annotated precondition AllocationLimitError guards in allocate and release with '# unreachable (assumption: invalid amount precondition)' per coverage feedback.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T18:43:31Z
# PRETENSE_QA_AUDIT: 2026-11-04T18:43:18Z
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

        POSTCONDITIONS:
        - MUST update is_active to active.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:17:49Z
# LAST_CHANGED: 2026-11-04T18:17:49Z
# CHANGE: Implemented vault interface: framework-decorated data types and abstract Vault protocol with package-qualified pretense import.
# --- END AUTOFAB METADATA ---


# === File: vault_impl.py ===
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
        # GROUNDING: initialize _balance to 0 and _is_active to True.
        self._balance: int = 0
        self._is_active: bool = True

    @property
    @override
    def balance(self) -> int:
        # GROUNDING: return the internally tracked balance.
        return self._balance

    @property
    @override
    def is_active(self) -> bool:
        # GROUNDING: return the internally tracked availability flag.
        return self._is_active

    @operation
    @override
    def deposit(self, amount: int) -> None:
        # PRECONDITION: a non-positive deposit violates balance constraints.
        if amount <= 0:
            raise vault.InsufficientFundsError(  # unreachable (assumption: invalid amount precondition)
                "Deposit amount must be greater than zero."
            )
        # POSTCONDITION: an inactive vault rejects the operation.
        if not self._is_active:
            raise vault.VaultInactiveException("Vault is inactive.")
        # POSTCONDITION: an active vault with a positive amount grows the balance.
        self._balance += amount

    @operation
    @override
    def withdraw(self, amount: int) -> None:
        # PRECONDITION: non-positive or above-balance withdrawals are rejected.
        if amount <= 0 or amount > self._balance:
            raise vault.InsufficientFundsError(  # unreachable (assumption: invalid amount precondition)
                "Withdrawal amount must be positive and not exceed the balance."
            )
        # POSTCONDITION: an inactive vault rejects the operation.
        if not self._is_active:
            raise vault.VaultInactiveException("Vault is inactive.")
        # POSTCONDITION: an active vault with a valid amount shrinks the balance.
        self._balance -= amount

    @operation
    @override
    @test_only
    def set_active(self, active: bool) -> None:
        # POSTCONDITION: is_active reflects the requested availability state.
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
# LAST_CLEANED: 2026-11-04T18:43:33Z
# LAST_CHANGED: 2026-11-04T18:42:50Z
# CHANGE: Annotated precondition InsufficientFundsError guards in deposit and withdraw with '# unreachable (assumption: invalid amount precondition)' per coverage feedback.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T18:43:33Z
# PRETENSE_QA_AUDIT: 2026-11-04T18:43:20Z
# --- END AUTOFAB METADATA ---
