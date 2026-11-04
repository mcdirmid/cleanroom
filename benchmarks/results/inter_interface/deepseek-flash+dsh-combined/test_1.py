# === File: inter_interface_impl_test.py ===
"""Unit tests for inter_interface_impl per its low-level specification."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from inter_interface.lib.vault import Vault as VaultProtocol, VaultInactiveException
from inter_interface.lib.inter_interface_impl import (
    Allocator,
    __initialize__,
)


class MockVault:
    """Lightweight vault protocol double recording delegated calls."""

    tier = system

    def __init__(self, balance: int = 100) -> None:
        self._balance = balance
        self._is_active = True
        self.withdrawals: list[int] = []
        self.deposits: list[int] = []

    @property
    def balance(self) -> int:
        return self._balance

    @property
    def is_active(self) -> bool:
        return self._is_active

    def deposit(self, amount: int) -> None:
        if not self._is_active:
            raise VaultInactiveException("vault is inactive")
        self.deposits.append(amount)
        self._balance += amount

    def withdraw(self, amount: int) -> None:
        if not self._is_active:
            raise VaultInactiveException("vault is inactive")
        self.withdrawals.append(amount)
        self._balance -= amount

    def set_active(self, active: bool) -> None:
        self._is_active = active


class InterInterfaceImplTest(unittest.TestCase):
    """Behavioral tests for the allocator singleton delegating to a vault."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_vault = MockVault()
        self.registry.register_instance(
            self.mock_vault,
            keys=[VaultProtocol],
            tier=system,
        )

    def test_initial_allocated_is_zero(self) -> None:
        """Grounding: allocator starts with an accumulated allocation of zero."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            self.assertEqual(0, allocator.allocated)

    def test_allocate_reserves_funds_from_vault(self) -> None:
        """WHEN successful, allocate MUST withdraw from the vault and increment allocated."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(40)
            self.assertEqual([40], self.mock_vault.withdrawals)
            self.assertEqual(60, self.mock_vault.balance)
            self.assertEqual(40, allocator.allocated)

    def test_allocate_accumulates_cumulative_funds(self) -> None:
        """INVARIANT: allocated tracks cumulative successful allocations."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(30)
            allocator.allocate(20)
            self.assertEqual([30, 20], self.mock_vault.withdrawals)
            self.assertEqual(50, allocator.allocated)

    def test_release_returns_funds_to_vault(self) -> None:
        """WHEN successful, release MUST deposit into the vault and decrement allocated."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(50)
            allocator.release(15)
            self.assertEqual([15], self.mock_vault.deposits)
            self.assertEqual(65, self.mock_vault.balance)
            self.assertEqual(35, allocator.allocated)

    def test_release_all_allocated_funds(self) -> None:
        """WHEN releasing the full allocated amount, allocated MUST return to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(45)
            allocator.release(45)
            self.assertEqual([45], self.mock_vault.deposits)
            self.assertEqual(0, allocator.allocated)

    def test_allocate_raises_when_vault_inactive(self) -> None:
        """WHEN collaborator vault is inactive, allocate MUST raise VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            self.mock_vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                allocator.allocate(10)
            self.assertEqual(0, allocator.allocated)

    def test_release_raises_when_vault_inactive(self) -> None:
        """WHEN collaborator vault is inactive, release MUST raise VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(50)
            self.mock_vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                allocator.release(10)
            self.assertEqual(50, allocator.allocated)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T21:06:41Z
# LAST_CHANGED: 2026-11-04T20:45:54Z
# CHANGE: Implement behavioral unit tests for inter_interface_impl: verify zero initial allocated state, allocate reserves funds via mocked vault withdrawal and increments allocated, cumulative allocations, release deposits back and decrements allocated (including full release), and VaultInactiveException propagation for allocate and release when the collaborator vault is inactive.
# COVERAGE_AUDIT: 2026-11-04T21:06:41Z
# QA_AUDIT: 2026-11-04T21:06:23Z
# --- END AUTOFAB METADATA ---


# === File: vault_impl_test.py ===
"""Unit tests for vault_impl per its low-level specification."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from inter_interface.lib.vault import VaultInactiveException
from inter_interface.lib.vault_impl import (
    Vault,
    __initialize__,
)


class VaultImplTest(unittest.TestCase):
    """Behavioral tests for the vault singleton."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state(self) -> None:
        """Grounding: fresh vault starts with a zero balance and is active."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            self.assertEqual(0, vault.balance)
            self.assertTrue(vault.is_active)

    def test_deposit_increments_balance(self) -> None:
        """WHEN is_active is True and amount is positive, MUST increment balance by amount."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(50)
            self.assertEqual(50, vault.balance)
            vault.deposit(25)
            self.assertEqual(75, vault.balance)

    def test_withdraw_decrements_balance(self) -> None:
        """WHEN is_active is True and amount is valid, MUST decrement balance by amount."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(100)
            vault.withdraw(40)
            self.assertEqual(60, vault.balance)
            vault.withdraw(60)
            self.assertEqual(0, vault.balance)

    def test_set_active_updates_is_active(self) -> None:
        """set_active MUST update is_active to the supplied active flag."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.set_active(False)
            self.assertFalse(vault.is_active)
            vault.set_active(True)
            self.assertTrue(vault.is_active)

    def test_deposit_raises_when_inactive(self) -> None:
        """WHEN is_active is False, deposit MUST raise VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                vault.deposit(10)
            self.assertEqual(0, vault.balance)

    def test_withdraw_raises_when_inactive(self) -> None:
        """WHEN is_active is False, withdraw MUST raise VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(30)
            vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                vault.withdraw(10)
            self.assertEqual(30, vault.balance)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T21:06:43Z
# LAST_CHANGED: 2026-11-04T20:45:50Z
# CHANGE: Implement behavioral unit tests for vault_impl: verify zero-balance/active initial state, deposit increments balance, withdraw decrements balance, set_active updates is_active, and both deposit and withdraw raise VaultInactiveException when the vault is inactive (balance preserved).
# COVERAGE_AUDIT: 2026-11-04T21:06:43Z
# QA_AUDIT: 2026-11-04T21:06:25Z
# --- END AUTOFAB METADATA ---
