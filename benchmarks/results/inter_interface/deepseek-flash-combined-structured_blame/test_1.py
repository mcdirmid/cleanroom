# === File: inter_interface_impl_test.py ===
"""Unit tests for the allocator singleton per low/inter_interface_impl.pyi."""

from __future__ import annotations

import unittest
from typing import List

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

from inter_interface.lib.inter_interface import AllocationLimitError
from inter_interface.lib.inter_interface_impl import Allocator, __initialize__
from inter_interface.lib.vault import (
    InsufficientFundsError,
    Vault,
    VaultInactiveException,
)


class MockVault:
    """Vault protocol double honoring vault.pyi invariants and recording interactions."""

    def __init__(self) -> None:
        self.balance_value = 500
        self.active_value = True
        self.withdrawals: List[int] = []
        self.deposits: List[int] = []

    @property
    def balance(self) -> int:
        return self.balance_value

    @property
    def is_active(self) -> bool:
        return self.active_value

    def deposit(self, amount: int) -> None:
        if amount <= 0:
            raise InsufficientFundsError("deposit amount must be positive")
        if not self.active_value:
            raise VaultInactiveException("vault is inactive")
        self.deposits.append(amount)
        self.balance_value += amount

    def withdraw(self, amount: int) -> None:
        if amount <= 0 or amount > self.balance_value:
            raise InsufficientFundsError("withdrawal amount must be valid")
        if not self.active_value:
            raise VaultInactiveException("vault is inactive")
        self.withdrawals.append(amount)
        self.balance_value -= amount

    def set_active(self, active: bool) -> None:
        self.active_value = active


class AllocatorTest(unittest.TestCase):
    """Verifies the Allocator contract declared in low/inter_interface_impl.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.vault = MockVault()
        __initialize__(self.registry)
        self.registry.register_instance(self.vault, keys=[Vault], tier=system)

    def test_initial_allocated_is_zero(self) -> None:
        """GROUNDING: _allocated is initialized to 0 with no vault interaction."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            self.assertEqual(allocator.allocated, 0)
            self.assertEqual(self.vault.withdrawals, [])
            self.assertEqual(self.vault.deposits, [])

    def test_allocate_delegates_withdrawal_and_increments(self) -> None:
        """POSTCONDITION: successful allocate withdraws from vault and increments allocated."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(125)
            self.assertEqual(self.vault.withdrawals, [125])
            self.assertEqual(allocator.allocated, 125)
            self.assertEqual(self.vault.balance, 375)

    def test_allocate_accumulates_across_calls(self) -> None:
        """POSTCONDITION: each successful allocate adds its amount to allocated."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(30)
            allocator.allocate(20)
            self.assertEqual(self.vault.withdrawals, [30, 20])
            self.assertEqual(allocator.allocated, 50)

    def test_allocate_zero_raises_allocation_limit_error(self) -> None:
        """PRECONDITION: amount <= 0 raises AllocationLimitError without touching the vault."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            with self.assertRaises(AllocationLimitError):
                allocator.allocate(0)
            self.assertEqual(allocator.allocated, 0)
            self.assertEqual(self.vault.withdrawals, [])

    def test_allocate_negative_raises_allocation_limit_error(self) -> None:
        """PRECONDITION: negative amount raises AllocationLimitError without touching the vault."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            with self.assertRaises(AllocationLimitError):
                allocator.allocate(-40)
            self.assertEqual(allocator.allocated, 0)
            self.assertEqual(self.vault.withdrawals, [])

    def test_allocate_exceeding_vault_reserves_raises_allocation_limit_error(self) -> None:
        """PRECONDITION: amount exceeding available vault reserves raises AllocationLimitError."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            with self.assertRaises(AllocationLimitError):
                allocator.allocate(900)
            self.assertEqual(allocator.allocated, 0)
            self.assertEqual(self.vault.balance, 500)
            self.assertEqual(self.vault.withdrawals, [])

    def test_allocate_exact_vault_reserves_succeeds(self) -> None:
        """POSTCONDITION: allocating exactly the available reserves is permitted."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(500)
            self.assertEqual(self.vault.withdrawals, [500])
            self.assertEqual(allocator.allocated, 500)
            self.assertEqual(self.vault.balance, 0)

    def test_allocate_inactive_vault_raises(self) -> None:
        """POSTCONDITION: an inactive collaborator vault raises vault.VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            self.vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                allocator.allocate(10)
            self.assertEqual(allocator.allocated, 0)
            self.assertEqual(self.vault.withdrawals, [])
            self.assertEqual(self.vault.balance, 500)

    def test_release_delegates_deposit_and_decrements(self) -> None:
        """POSTCONDITION: successful release deposits back to vault and decrements allocated."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(80)
            allocator.release(50)
            self.assertEqual(self.vault.deposits, [50])
            self.assertEqual(allocator.allocated, 30)
            self.assertEqual(self.vault.balance, 470)

    def test_release_zero_raises_allocation_limit_error(self) -> None:
        """PRECONDITION: releasing a zero amount raises AllocationLimitError."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            with self.assertRaises(AllocationLimitError):
                allocator.release(0)
            self.assertEqual(allocator.allocated, 0)
            self.assertEqual(self.vault.deposits, [])

    def test_release_negative_raises_allocation_limit_error(self) -> None:
        """PRECONDITION: releasing a negative amount raises AllocationLimitError."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(25)
            with self.assertRaises(AllocationLimitError):
                allocator.release(-5)
            self.assertEqual(allocator.allocated, 25)
            self.assertEqual(self.vault.deposits, [])

    def test_release_exceeding_allocated_raises(self) -> None:
        """PRECONDITION: releasing more than allocated raises AllocationLimitError."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(25)
            with self.assertRaises(AllocationLimitError):
                allocator.release(26)
            self.assertEqual(allocator.allocated, 25)
            self.assertEqual(self.vault.deposits, [])

    def test_release_inactive_vault_raises(self) -> None:
        """POSTCONDITION: an inactive collaborator vault raises vault.VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(40)
            self.vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                allocator.release(10)
            self.assertEqual(allocator.allocated, 40)
            self.assertEqual(self.vault.deposits, [])


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T18:04:17Z
# LAST_CHANGED: 2026-11-08T18:03:42Z
# CHANGE: Resolved [slug:allocator.allocate.insufficient_vault_reserves]: allocate against insufficient vault reserves (amount=900 vs balance=500) now asserts the contracted AllocationLimitError — no longer expects vault.InsufficientFundsError propagation — and verifies allocated stays 0, vault balance remains 500, and no withdrawal is recorded. Reworked MockVault into a faithful vault.pyi double (positive-amount and reserve validation, inactive-vault VaultInactiveException) so inactive-vault allocate/release branches are driven through set_active rather than seeded exceptions, and added an exact-reserve boundary test asserting allocate(balance) succeeds.
# COVERAGE_AUDIT: 2026-11-08T18:04:17Z
# QA_AUDIT: 2026-11-08T18:04:05Z
# --- END AUTOFAB METADATA ---


# === File: vault_impl_test.py ===
"""Unit tests for the vault singleton per low/vault_impl.pyi."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

from inter_interface.lib.vault import InsufficientFundsError, VaultInactiveException
from inter_interface.lib.vault_impl import Vault, __initialize__


class VaultTest(unittest.TestCase):
    """Verifies the Vault contract declared in low/vault_impl.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state(self) -> None:
        """GROUNDING: _balance starts at 0 and _is_active starts as True."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            self.assertEqual(vault.balance, 0)
            self.assertIs(vault.is_active, True)

    def test_deposit_increments_balance(self) -> None:
        """POSTCONDITION: an active vault deposits a positive amount into its balance."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(120)
            self.assertEqual(vault.balance, 120)
            vault.deposit(30)
            self.assertEqual(vault.balance, 150)

    def test_deposit_zero_raises_insufficient_funds(self) -> None:
        """PRECONDITION: depositing a zero amount raises InsufficientFundsError."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            with self.assertRaises(InsufficientFundsError):
                vault.deposit(0)
            self.assertEqual(vault.balance, 0)

    def test_deposit_negative_raises_insufficient_funds(self) -> None:
        """PRECONDITION: depositing a negative amount raises InsufficientFundsError."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            with self.assertRaises(InsufficientFundsError):
                vault.deposit(-10)
            self.assertEqual(vault.balance, 0)

    def test_deposit_on_inactive_vault_raises(self) -> None:
        """POSTCONDITION: depositing into an inactive vault raises VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                vault.deposit(10)
            self.assertEqual(vault.balance, 0)

    def test_withdraw_decrements_balance(self) -> None:
        """POSTCONDITION: an active vault withdraws a valid amount from its balance."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(100)
            vault.withdraw(40)
            self.assertEqual(vault.balance, 60)

    def test_withdraw_entire_balance(self) -> None:
        """POSTCONDITION: withdrawing exactly the balance leaves the vault empty."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(75)
            vault.withdraw(75)
            self.assertEqual(vault.balance, 0)

    def test_withdraw_zero_raises_insufficient_funds(self) -> None:
        """PRECONDITION: withdrawing a zero amount raises InsufficientFundsError."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(50)
            with self.assertRaises(InsufficientFundsError):
                vault.withdraw(0)
            self.assertEqual(vault.balance, 50)

    def test_withdraw_negative_raises_insufficient_funds(self) -> None:
        """PRECONDITION: withdrawing a negative amount raises InsufficientFundsError."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(50)
            with self.assertRaises(InsufficientFundsError):
                vault.withdraw(-10)
            self.assertEqual(vault.balance, 50)

    def test_withdraw_exceeding_balance_raises(self) -> None:
        """PRECONDITION: withdrawing more than the balance raises InsufficientFundsError."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(50)
            with self.assertRaises(InsufficientFundsError):
                vault.withdraw(51)
            self.assertEqual(vault.balance, 50)

    def test_withdraw_on_inactive_vault_raises(self) -> None:
        """POSTCONDITION: withdrawing from an inactive vault raises VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(100)
            vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                vault.withdraw(10)
            self.assertEqual(vault.balance, 100)

    def test_set_active_updates_state(self) -> None:
        """POSTCONDITION: set_active must update is_active to the requested value."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.set_active(False)
            self.assertIs(vault.is_active, False)
            vault.set_active(True)
            self.assertIs(vault.is_active, True)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:31:08Z
# LAST_CHANGED: 2026-11-08T17:27:36Z
# CHANGE: Implemented comprehensive unit tests for the Vault singleton per low/vault_impl.pyi: zero initial balance with active state, deposit incrementing balance, non-positive deposit InsufficientFundsError, inactive-vault deposit VaultInactiveException, withdraw decrementing balance including exact-balance withdrawal, non-positive and exceeding-balance withdraw InsufficientFundsError, inactive-vault withdraw VaultInactiveException, and set_active state transitions. Each test runs within an enter_phase(system) scope resolving Vault via scope.get_singleton.
# COVERAGE_AUDIT: 2026-11-08T17:31:08Z
# QA_AUDIT: 2026-11-08T17:30:45Z
# --- END AUTOFAB METADATA ---
