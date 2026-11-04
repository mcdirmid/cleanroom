# === File: inter_interface_impl_test.py ===
"""Unit tests for inter_interface_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Optional

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inter_interface.lib import vault
from inter_interface.lib.inter_interface_impl import (
    Allocator,
    __initialize__,
)


class MockVault:
    """Lightweight vault.Vault double recording reserve operations."""

    def __init__(self) -> None:
        self.balance: int = 0
        self.is_active: bool = True
        self.withdrawn: list[int] = []
        self.deposited: list[int] = []
        self.withdraw_failure: Optional[Exception] = None
        self.deposit_failure: Optional[Exception] = None

    def deposit(self, amount: int) -> None:
        if self.deposit_failure is not None:
            raise self.deposit_failure
        self.deposited.append(amount)
        self.balance += amount

    def withdraw(self, amount: int) -> None:
        if self.withdraw_failure is not None:
            raise self.withdraw_failure
        self.withdrawn.append(amount)
        self.balance -= amount

    def set_active(self, active: bool) -> None:
        self.is_active = active


class InterInterfaceImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_vault = MockVault()
        self.registry.register_instance(
            self.mock_vault,
            keys=[vault.Vault],
            tier=system,
        )

    def test_allocate_reserves_from_collaborator_vault(self) -> None:
        """POSTCONDITION: successful allocation withdraws amount and increments allocated."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(50)
            self.assertEqual(self.mock_vault.withdrawn, [50])
            self.assertEqual(allocator.allocated, 50)

    def test_release_returns_funds_to_collaborator_vault(self) -> None:
        """POSTCONDITION: successful release deposits amount and decrements allocated."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(50)
            allocator.release(20)
            self.assertEqual(self.mock_vault.deposited, [20])
            self.assertEqual(allocator.allocated, 30)

    def test_allocate_propagates_inactive_vault_failure(self) -> None:
        """POSTCONDITION: an inactive collaborator vault raises VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            self.mock_vault.withdraw_failure = vault.VaultInactiveException()
            with self.assertRaises(vault.VaultInactiveException):
                allocator.allocate(10)
            self.assertEqual(allocator.allocated, 0)

    def test_release_propagates_inactive_vault_failure(self) -> None:
        """POSTCONDITION: an inactive collaborator vault raises VaultInactiveException."""
        with enter_phase(system, registry=self.registry) as scope:
            allocator = scope.get_singleton(Allocator)
            allocator.allocate(10)
            self.mock_vault.deposit_failure = vault.VaultInactiveException()
            with self.assertRaises(vault.VaultInactiveException):
                allocator.release(10)
            self.assertEqual(allocator.allocated, 10)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:46:04Z
# LAST_CHANGED: 2026-11-04T20:46:04Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: ae407df6a50d
# COVERAGE_AUDIT: 2026-11-04T20:46:04Z
# QA_AUDIT: 2026-11-04T20:46:04Z
# --- END AUTOFAB METADATA ---


# === File: vault_impl_test.py ===
"""Unit tests for vault_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inter_interface.lib.vault import VaultInactiveException
from inter_interface.lib.vault_impl import Vault, __initialize__


class VaultImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_vault_state(self) -> None:
        """GROUNDING: balance starts at 0 and the vault starts active."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            self.assertEqual(vault.balance, 0)
            self.assertTrue(vault.is_active)

    def test_deposit_increments_balance(self) -> None:
        """POSTCONDITION: a positive deposit increments balance by amount."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(10)
            self.assertEqual(vault.balance, 10)
            vault.deposit(5)
            self.assertEqual(vault.balance, 15)

    def test_withdraw_decrements_balance(self) -> None:
        """POSTCONDITION: a valid withdrawal decrements balance by amount."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(10)
            vault.withdraw(4)
            self.assertEqual(vault.balance, 6)

    def test_deposit_on_inactive_vault_raises(self) -> None:
        """POSTCONDITION: an inactive vault raises VaultInactiveException on deposit."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                vault.deposit(10)
            self.assertEqual(vault.balance, 0)

    def test_withdraw_on_inactive_vault_raises(self) -> None:
        """POSTCONDITION: an inactive vault raises VaultInactiveException on withdraw."""
        with enter_phase(system, registry=self.registry) as scope:
            vault = scope.get_singleton(Vault)
            vault.deposit(10)
            vault.set_active(False)
            with self.assertRaises(VaultInactiveException):
                vault.withdraw(5)
            self.assertEqual(vault.balance, 10)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:46:04Z
# LAST_CHANGED: 2026-11-04T20:46:04Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 454d6dd5edd1
# COVERAGE_AUDIT: 2026-11-04T20:46:04Z
# QA_AUDIT: 2026-11-04T20:46:04Z
# --- END AUTOFAB METADATA ---
