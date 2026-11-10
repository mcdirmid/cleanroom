# === File: inter_interface_impl_test.py ===
"""Unit tests for inter_interface_impl per its low-level specification."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from inter_interface.lib.inter_interface import AllocationLimitError
from inter_interface.lib.vault import (
    InsufficientFundsError,
    Vault,
    VaultInactiveException,
)
from inter_interface.lib.inter_interface_impl import (
    Allocator,
    __initialize__,
)


class MockVault:
    """Scriptable vault collaborator implementing the vault.Vault protocol."""

    tier = system

    def __init__(self) -> None:
        self.balance = 0
        self.is_active = True
        self.withdrawals: list[int] = []
        self.deposits: list[int] = []

    def deposit(self, amount: int) -> None:
        """Records a deposit and grows the scripted balance."""
        if not self.is_active:
            raise VaultInactiveException("vault is inactive")
        if amount <= 0:
            raise InsufficientFundsError("deposit amount must be positive")
        self.deposits.append(amount)
        self.balance += amount

    def withdraw(self, amount: int) -> None:
        """Records a withdrawal and shrinks the scripted balance."""
        if not self.is_active:
            raise VaultInactiveException("vault is inactive")
        if amount <= 0 or amount > self.balance:
            raise InsufficientFundsError("withdraw amount exceeds available balance")
        self.withdrawals.append(amount)
        self.balance -= amount


class InterInterfaceImplTest(unittest.TestCase):
    """Verifies Allocator accounting and delegation to the vault collaborator."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.vault = MockVault()
        self.registry.register_instance(self.vault, keys=[Vault], tier=system)

    def test_initial_allocated_is_zero(self) -> None:
        """A freshly initialized allocator has no allocated funds."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            self.assertEqual(allocator.allocated, 0)

    def test_allocate_reserves_from_vault(self) -> None:
        """A successful allocation withdraws from the vault and increases allocated funds."""
        self.vault.balance = 500
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(120)
            self.assertEqual(self.vault.withdrawals, [120])
            self.assertEqual(self.vault.balance, 380)
            self.assertEqual(allocator.allocated, 120)

    def test_allocate_rejects_non_positive_amount(self) -> None:
        """Allocating zero or a negative amount raises AllocationLimitError."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            with self.assertRaises(AllocationLimitError):
                allocator.allocate(0)
            with self.assertRaises(AllocationLimitError):
                allocator.allocate(-25)
            self.assertEqual(self.vault.withdrawals, [])
            self.assertEqual(allocator.allocated, 0)

    def test_allocate_rejects_amount_exceeding_vault_reserves(self) -> None:
        """Allocating more than the vault holds raises AllocationLimitError."""
        self.vault.balance = 30
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            with self.assertRaises(AllocationLimitError):
                allocator.allocate(31)
            self.assertEqual(self.vault.withdrawals, [])
            self.assertEqual(allocator.allocated, 0)

    def test_allocate_on_inactive_vault_raises(self) -> None:
        """Allocating against an inactive vault raises VaultInactiveException."""
        self.vault.balance = 100
        self.vault.is_active = False
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            with self.assertRaises(VaultInactiveException):
                allocator.allocate(10)
            self.assertEqual(self.vault.withdrawals, [])
            self.assertEqual(allocator.allocated, 0)

    def test_release_returns_funds_to_vault(self) -> None:
        """A successful release deposits to the vault and decreases allocated funds."""
        self.vault.balance = 500
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(120)
            allocator.release(70)
            self.assertEqual(self.vault.deposits, [70])
            self.assertEqual(self.vault.balance, 450)
            self.assertEqual(allocator.allocated, 50)

    def test_release_rejects_invalid_amount(self) -> None:
        """Releasing a non-positive amount or more than allocated raises AllocationLimitError."""
        self.vault.balance = 500
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(100)
            with self.assertRaises(AllocationLimitError):
                allocator.release(0)
            with self.assertRaises(AllocationLimitError):
                allocator.release(-10)
            with self.assertRaises(AllocationLimitError):
                allocator.release(101)
            self.assertEqual(self.vault.deposits, [])
            self.assertEqual(allocator.allocated, 100)

    def test_release_on_inactive_vault_raises(self) -> None:
        """Releasing against an inactive vault raises VaultInactiveException."""
        self.vault.balance = 500
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(100)
            self.vault.is_active = False
            with self.assertRaises(VaultInactiveException):
                allocator.release(40)
            self.assertEqual(self.vault.deposits, [])
            self.assertEqual(allocator.allocated, 100)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:22:06Z
# LAST_CHANGED: 2026-11-08T17:21:29Z
# CHANGE: Resolved insufficient-reserve feedback: allocating more than the vault holds now asserts AllocationLimitError (the contracted exception) rather than InsufficientFundsError, and asserts no withdrawal is recorded and allocated stays zero. All other tests unchanged.
# COVERAGE_AUDIT: 2026-11-08T17:22:06Z
# QA_AUDIT: 2026-11-08T17:21:54Z
# --- END AUTOFAB METADATA ---


# === File: vault_impl_test.py ===
"""Unit tests for vault_impl per its low-level specification."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from inter_interface.lib.vault import (
    InsufficientFundsError,
    VaultInactiveException,
)
from inter_interface.lib.vault_impl import (
    Vault,
    __initialize__,
)


class VaultImplTest(unittest.TestCase):
    """Verifies Vault balance accounting and guarded deposit/withdraw operations."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state(self) -> None:
        """A freshly initialized vault is empty and active."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            self.assertEqual(vault.balance, 0)
            self.assertTrue(vault.is_active)

    def test_deposit_increments_balance(self) -> None:
        """Depositing a positive amount increases the active vault balance."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(100)
            self.assertEqual(vault.balance, 100)
            vault.deposit(50)
            self.assertEqual(vault.balance, 150)

    def test_deposit_rejects_non_positive_amount(self) -> None:
        """Depositing zero or a negative amount raises InsufficientFundsError."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            with self.assertRaises(InsufficientFundsError):
                vault.deposit(0)
            with self.assertRaises(InsufficientFundsError):
                vault.deposit(-10)
            self.assertEqual(vault.balance, 0)

    def test_deposit_on_inactive_vault_raises(self) -> None:
        """Depositing into an inactive vault raises VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                vault.deposit(10)
            self.assertEqual(vault.balance, 0)

    def test_withdraw_decrements_balance(self) -> None:
        """Withdrawing a valid amount decreases the active vault balance."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(100)
            vault.withdraw(40)
            self.assertEqual(vault.balance, 60)

    def test_withdraw_rejects_non_positive_amount(self) -> None:
        """Withdrawing zero or a negative amount raises InsufficientFundsError."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(100)
            with self.assertRaises(InsufficientFundsError):
                vault.withdraw(0)
            with self.assertRaises(InsufficientFundsError):
                vault.withdraw(-5)
            self.assertEqual(vault.balance, 100)

    def test_withdraw_rejects_amount_exceeding_balance(self) -> None:
        """Withdrawing more than the held balance raises InsufficientFundsError."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(30)
            with self.assertRaises(InsufficientFundsError):
                vault.withdraw(31)
            self.assertEqual(vault.balance, 30)

    def test_withdraw_on_inactive_vault_raises(self) -> None:
        """Withdrawing from an inactive vault raises VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(100)
            vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                vault.withdraw(10)
            self.assertEqual(vault.balance, 100)

    def test_set_active_updates_is_active(self) -> None:
        """Toggling availability updates the reported active state."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.set_active(False)
            self.assertFalse(vault.is_active)
            vault.set_active(True)
            self.assertTrue(vault.is_active)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:19:49Z
# LAST_CHANGED: 2026-11-08T17:16:39Z
# CHANGE: Authored unit tests for the Vault singleton implementation: initial empty/active state, deposit invalidation and balance increments, withdraw invalidation (non-positive, exceeding balance) and decrements, inactive-vault VaultInactiveException on deposit/withdraw, and set_active state transitions, all resolved within an active system lifecycle phase.
# COVERAGE_AUDIT: 2026-11-08T17:19:49Z
# QA_AUDIT: 2026-11-08T17:18:35Z
# --- END AUTOFAB METADATA ---
