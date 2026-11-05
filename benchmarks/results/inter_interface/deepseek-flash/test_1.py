# === File: inter_interface_impl_test.py ===
"""Unit tests for inter_interface_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PARTS_ROOT = str(Path(__file__).resolve().parents[2])
if _PARTS_ROOT not in sys.path:
    sys.path.insert(0, _PARTS_ROOT)

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from inter_interface.lib.vault import Vault, VaultInactiveException
from inter_interface.lib.inter_interface_impl import (
    Allocator,
    __initialize__,
)


class MockVault:
    """Lightweight collaborator double for the vault interface protocol.

    Records reserve interactions and can script an inactive-vault failure.
    """

    def __init__(self, balance: int = 100, active: bool = True) -> None:
        self.current_balance = balance
        self.active = active
        self.deposits: list[int] = []
        self.withdrawals: list[int] = []

    @property
    def balance(self) -> int:
        return self.current_balance

    @property
    def is_active(self) -> bool:
        return self.active

    def deposit(self, amount: int) -> None:
        self.deposits.append(amount)
        if not self.active:
            raise VaultInactiveException("vault is inactive")
        self.current_balance += amount

    def withdraw(self, amount: int) -> None:
        self.withdrawals.append(amount)
        if not self.active:
            raise VaultInactiveException("vault is inactive")
        self.current_balance -= amount

    def set_active(self, active: bool) -> None:
        self.active = active


class InterInterfaceImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.vault = MockVault(balance=100)
        self.registry.register_instance(self.vault, keys=[Vault], tier=system)
        __initialize__(self.registry)

    def test_initial_allocated_is_zero(self) -> None:
        """Invariant: a newly created allocator has no cumulative allocated funds."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            self.assertEqual(allocator.allocated, 0)

    def test_allocate_reserves_funds_from_vault(self) -> None:
        """Postcondition: a successful allocate withdraws from the vault and increments allocated."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(30)
            self.assertEqual(allocator.allocated, 30)
            self.assertEqual(self.vault.withdrawals, [30])
            self.assertEqual(self.vault.balance, 70)

    def test_allocate_accumulates_cumulative_total(self) -> None:
        """Postcondition: each successful allocate adds its amount to the cumulative allocated total."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(30)
            allocator.allocate(15)
            self.assertEqual(allocator.allocated, 45)
            self.assertEqual(self.vault.withdrawals, [30, 15])

    def test_release_returns_funds_to_vault(self) -> None:
        """Postcondition: a successful release deposits into the vault and decrements allocated."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(30)
            allocator.release(10)
            self.assertEqual(allocator.allocated, 20)
            self.assertEqual(self.vault.deposits, [10])
            self.assertEqual(self.vault.balance, 80)

    def test_allocate_when_vault_inactive_raises(self) -> None:
        """Postcondition: WHEN the collaborator vault is inactive, allocate MUST raise VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            self.vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                allocator.allocate(10)
            self.assertEqual(allocator.allocated, 0)

    def test_release_when_vault_inactive_raises(self) -> None:
        """Postcondition: WHEN the collaborator vault is inactive, release MUST raise VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(30)
            self.vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                allocator.release(10)
            self.assertEqual(allocator.allocated, 30)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:45:55Z
# LAST_CHANGED: 2026-11-04T20:45:21Z
# CHANGE: Added unit tests for inter_interface_impl covering zero initial allocated invariant, allocate/release vault delegation and cumulative allocated updates, plus inactive-vault VaultInactiveException branches using a lightweight MockVault collaborator.
# COVERAGE_AUDIT: 2026-11-04T20:45:55Z
# QA_AUDIT: 2026-11-04T20:45:42Z
# --- END AUTOFAB METADATA ---


# === File: vault_impl_test.py ===
"""Unit tests for vault_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PARTS_ROOT = str(Path(__file__).resolve().parents[2])
if _PARTS_ROOT not in sys.path:
    sys.path.insert(0, _PARTS_ROOT)

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from inter_interface.lib.vault import VaultInactiveException
from inter_interface.lib.vault_impl import (
    Vault,
    __initialize__,
)


class VaultImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state(self) -> None:
        """Invariant: a newly created vault holds a zero balance and is active."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            self.assertEqual(vault.balance, 0)
            self.assertTrue(vault.is_active)

    def test_deposit_increments_balance(self) -> None:
        """Postcondition: an active vault increments balance by the deposited amount."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(40)
            self.assertEqual(vault.balance, 40)
            vault.deposit(2)
            self.assertEqual(vault.balance, 42)

    def test_withdraw_decrements_balance(self) -> None:
        """Postcondition: an active vault decrements balance by the withdrawn amount."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(100)
            vault.withdraw(30)
            self.assertEqual(vault.balance, 70)
            vault.withdraw(70)
            self.assertEqual(vault.balance, 0)

    def test_set_active_updates_is_active(self) -> None:
        """Postcondition: set_active must update is_active to the supplied value."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.set_active(False)
            self.assertFalse(vault.is_active)
            vault.set_active(True)
            self.assertTrue(vault.is_active)

    def test_deposit_when_inactive_raises_and_preserves_balance(self) -> None:
        """Postcondition: WHEN is_active is False, deposit MUST raise VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(5)
            vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                vault.deposit(10)
            self.assertEqual(vault.balance, 5)

    def test_withdraw_when_inactive_raises_and_preserves_balance(self) -> None:
        """Postcondition: WHEN is_active is False, withdraw MUST raise VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(50)
            vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                vault.withdraw(10)
            self.assertEqual(vault.balance, 50)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:45:57Z
# LAST_CHANGED: 2026-11-04T20:45:17Z
# CHANGE: Added unit tests for vault_impl covering initial state invariant, deposit/withdraw balance updates, set_active toggling, and inactive-vault VaultInactiveException branches with postcondition assertions.
# COVERAGE_AUDIT: 2026-11-04T20:45:57Z
# QA_AUDIT: 2026-11-04T20:45:43Z
# --- END AUTOFAB METADATA ---
