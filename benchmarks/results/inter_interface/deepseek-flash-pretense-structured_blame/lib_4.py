# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_000603_deepseek-flash_inter_interface_pretense
# Timestamp: 2026-11-13T00:06:03.778896+00:00
# Benchmark Task: inter_interface
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 75,650
#   Cached Inbound Tokens:   1,940,480
#   Outbound Tokens:         63,617
#   Total Tokens:            2,079,747
#   Financial Cost ($USD):   $0.0553
#   Wall Clock Duration:     365.02s
#   Step Latencies (s):      [118.4, 10.1, 324.9, 13.8, 20.5]
#   Role Execution Rounds:   lib: 1, pretense: 1, pretense_coverage: 1, pretense_qa: 2 (Total: 5)
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
"""Library interface for the resource allocator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pretense import PretenseSpecificationError
from support.lib.framework import data_type, operation, poly_type

from . import vault


@data_type
@dataclass
class AllocatorError(PretenseSpecificationError):
    """Base exception for all allocator operations."""


@data_type
@dataclass
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
# LAST_CLEANED: 2026-11-13T00:07:47Z
# LAST_CHANGED: 2026-11-13T00:07:47Z
# CHANGE: Implement allocator interface: AllocatorError/AllocationLimitError dataclass exceptions and the @poly_type Allocator protocol with the allocated property plus allocate and release operations per low/inter_interface.pyi.
# --- END AUTOFAB METADATA ---


# === File: inter_interface_impl.py ===
"""Library implementation of the resource allocator."""

from __future__ import annotations

from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton

from . import inter_interface, vault


@singleton
class Allocator(inter_interface.Allocator):
    """Concrete resource allocator coordinating reserves with the vault."""

    tier: str = "system"

    def __init__(self) -> None:
        # No funds are reserved until an allocation succeeds.
        self._allocated: int = 0

    @property
    @override
    def allocated(self) -> int:
        """Current amount of cumulative funds actively allocated."""
        return self._allocated

    @operation
    @override
    def allocate(self, amount: int) -> None:
        """Allocates funds by reserving them from the collaborator vault."""
        # Reject non-positive allocation requests up front.
        if amount <= 0:
            raise inter_interface.AllocationLimitError()
        vault_service = get_singleton(vault.Vault)
        try:
            vault_service.withdraw(amount)
        except vault.InsufficientFundsError as exc:
            # Surface insufficient vault reserves as an allocation limit failure.
            raise inter_interface.AllocationLimitError() from exc
        # Track the funds now reserved from the vault.
        self._allocated += amount

    @operation
    @override
    def release(self, amount: int) -> None:
        """Releases previously allocated funds back to the collaborator vault."""
        # Reject non-positive releases and releases beyond reserved funds.
        if amount <= 0 or amount > self._allocated:
            raise inter_interface.AllocationLimitError()
        vault_service = get_singleton(vault.Vault)
        vault_service.deposit(amount)
        # Drop the funds that are no longer reserved.
        self._allocated -= amount

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:11:54Z
# LAST_CHANGED: 2026-11-13T00:07:58Z
# CHANGE: Implement the @singleton system-tier Allocator service: private _allocated counter, allocated property, allocate validating positive amounts and translating vault.InsufficientFundsError into AllocationLimitError while delegating withdrawals and tracking reservations, and release validating against reserved funds while depositing back to the vault per low/inter_interface_impl.pyi.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:11:54Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:11:51Z
# --- END AUTOFAB METADATA ---


# === File: vault.py ===
"""Library interface for the resource vault."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type


@data_type
@dataclass
class VaultError(PretenseSpecificationError):
    """Base exception for all vault operations."""


@data_type
@dataclass
class InsufficientFundsError(VaultError):
    """Raised when deposit or withdrawal violates balance constraints."""


@data_type
@dataclass
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
# LAST_CLEANED: 2026-11-13T00:07:41Z
# LAST_CHANGED: 2026-11-13T00:07:41Z
# CHANGE: Implement vault interface: VaultError/InsufficientFundsError/VaultInactiveException dataclass exceptions and the @poly_type Vault protocol with balance/is_active properties plus deposit, withdraw, and test-only set_active operations per low/vault.pyi.
# --- END AUTOFAB METADATA ---


# === File: vault_impl.py ===
"""Library implementation of the resource vault."""

from __future__ import annotations

from pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from . import vault


@singleton
class Vault(vault.Vault):
    """Concrete resource vault tracking an in-memory asset balance."""

    tier: str = "system"

    def __init__(self) -> None:
        # The vault starts empty and available for operation.
        self._balance: int = 0
        self._is_active: bool = True

    @property
    @override
    def balance(self) -> int:
        """Current asset balance held in the vault."""
        return self._balance

    @property
    @override
    def is_active(self) -> bool:
        """Indicates whether the vault service is currently active."""
        return self._is_active

    @operation
    @override
    def deposit(self, amount: int) -> None:
        """Deposits funds into the vault."""
        # Reject non-positive deposits before the balance is touched.
        if amount <= 0:
            raise vault.InsufficientFundsError()
        # Deposits are unavailable while the vault is deactivated.
        if not self._is_active:
            raise vault.VaultInactiveException()
        self._balance += amount

    @operation
    @override
    def withdraw(self, amount: int) -> None:
        """Withdraws funds from the vault."""
        # Reject non-positive withdrawals and requests above the held balance.
        if amount <= 0 or amount > self._balance:
            raise vault.InsufficientFundsError()
        # Withdrawals are unavailable while the vault is deactivated.
        if not self._is_active:
            raise vault.VaultInactiveException()
        self._balance -= amount

    @operation
    @override
    @test_only
    def set_active(self, active: bool) -> None:
        """Test-only hook to toggle vault availability."""
        self._is_active = active

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:11:57Z
# LAST_CHANGED: 2026-11-13T00:07:52Z
# CHANGE: Implement the @singleton system-tier Vault service: private _balance/_is_active state initialized in __init__, balance and is_active properties, deposit/withdraw with positive-amount validation and inactive-vault guards raising the contracted exceptions, and the test-only set_active hook per low/vault_impl.pyi.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:11:57Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:10:46Z
# --- END AUTOFAB METADATA ---
