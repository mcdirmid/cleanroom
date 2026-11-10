# === File: inter_interface_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for Allocator."""

from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_4.parts.inter_interface.lib import vault
from benchmark_4.parts.inter_interface.lib.inter_interface import AllocationLimitError
from benchmark_4.parts.inter_interface.lib.inter_interface_impl import Allocator
from benchmark_4.parts.inter_interface.lib.inter_interface_impl import __initialize__ as _ii_initialize
from benchmark_4.parts.inter_interface.lib.vault_impl import __initialize__ as _v_initialize
from benchmark_4.parts.inter_interface.pretense.inter_interface_pretense import (
    INITIAL_VAULT_RESERVES,
    FakeInterInterface,
    InterInterfaceState,
    InterInterfaceStateMachine,
    make_inter_interface_fake,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine
# ==============================================================================

class InterInterfaceImplPseudoStateMachine(InterInterfaceStateMachine):
    """Implementation pseudo-state machine observing the concrete Allocator."""

    @transition(Allocator.allocate)
    def allocate(
        self,
        amount: int,
    ) -> Any:
        target: Allocator = sut(Allocator)
        before = target.allocated
        ret = call_target(target.allocate(amount))
        assert target.allocated == before + amount
        return ret

    @transition(Allocator.release)
    def release(
        self,
        amount: int,
    ) -> Any:
        target: Allocator = sut(Allocator)
        before = target.allocated
        ret = call_target(target.release(amount))
        assert target.allocated == before - amount
        return ret

    @transition(name="allocated")
    def allocated(self) -> int:
        target: Allocator = sut(Allocator)
        ret = call_target(getattr(target, "allocated"))
        assert ret == self.state.allocated
        return ret


proto = InterInterfaceImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestInterInterfaceImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the Allocator contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ii_initialize(self.registry)
        _v_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(Allocator)
        self.vault = self.phase_scope.get_singleton(vault.Vault)
        self.sm = InterInterfaceImplPseudoStateMachine(singletons={Allocator: self.real})
        self.checked = self.sm.as_checked(Allocator, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        """Drives allocation and release scenarios against the real allocator."""
        self.vault.deposit(INITIAL_VAULT_RESERVES)
        self.assertEqual(self.vault.balance, INITIAL_VAULT_RESERVES)
        self.checked.allocate(10)
        self.assertEqual(self.checked.allocated, 10)
        self.assertEqual(self.vault.balance, INITIAL_VAULT_RESERVES - 10)
        self.checked.release(4)
        self.assertEqual(self.checked.allocated, 6)
        self.assertEqual(self.vault.balance, INITIAL_VAULT_RESERVES - 6)
        self.checked.allocate(3)
        self.assertEqual(self.checked.allocated, 9)
        self.assertEqual(self.vault.balance, INITIAL_VAULT_RESERVES - 9)
        self.checked.release(9)
        self.assertEqual(self.checked.allocated, 0)
        self.assertEqual(self.vault.balance, INITIAL_VAULT_RESERVES)

    def test_invalid_amount_rejections(self) -> None:
        """Verifies the contracted rejection of non-positive and excessive amounts."""
        self.vault.deposit(INITIAL_VAULT_RESERVES)
        with self.assertRaises(AllocationLimitError):
            self.checked.allocate(0)
        with self.assertRaises(AllocationLimitError):
            self.checked.allocate(-5)
        with self.assertRaises(AllocationLimitError):
            self.checked.release(0)
        with self.assertRaises(AllocationLimitError):
            self.checked.release(1)
        self.assertEqual(self.checked.allocated, 0)
        self.assertEqual(self.vault.balance, INITIAL_VAULT_RESERVES)

    def test_insufficient_vault_reserves(self) -> None:
        """Verifies the contracted rejection of allocations beyond vault reserves."""
        self.vault.deposit(INITIAL_VAULT_RESERVES)
        with self.assertRaises(AllocationLimitError):
            self.checked.allocate(INITIAL_VAULT_RESERVES + 1)
        self.assertEqual(self.checked.allocated, 0)
        self.assertEqual(self.vault.balance, INITIAL_VAULT_RESERVES)
        self.checked.allocate(INITIAL_VAULT_RESERVES)
        self.assertEqual(self.checked.allocated, INITIAL_VAULT_RESERVES)
        self.assertEqual(self.vault.balance, 0)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def provision_collaborator_vault() -> None:
    """Seeds collaborator vault singleton reserves for fuzz allocation scenarios."""
    reserved_vault = get_singleton(vault.Vault)
    reserved_vault.deposit(INITIAL_VAULT_RESERVES)


def make_sut() -> Allocator:
    """Creates a concrete Allocator whose collaborator vault is already provisioned."""
    registry = LifecycleRegistry()
    _ii_initialize(registry)
    _v_initialize(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    provision_collaborator_vault()
    return get_singleton(Allocator)


InterInterfaceFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=InterInterfaceState,
    name="InterInterfaceFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:46:28Z
# LAST_CHANGED: 2026-11-08T17:45:53Z
# CHANGE: Resolved the remaining overspecified-oracle feedback for the Allocator impl module: the implementation pseudo-state machine keeps no duplicated guards (overrides only observe the SUT around the call_target pivot, so no post-transition model conditions can spuriously declare expected errors), and the deterministic over-reserve scenario now asserts AllocationLimitError, the exception the concrete allocator actually raises when the amount exceeds collaborator vault reserves, keeping model and SUT expectations aligned with the interface contract.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:46:28Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:46:04Z
# --- END AUTOFAB METADATA ---


# === File: inter_interface_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for Allocator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
    StateMachine,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_4.parts.inter_interface.lib.inter_interface import (
    AllocationLimitError,
    Allocator,
)


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================

INITIAL_VAULT_RESERVES = 1000
"""Reserves the model assumes the collaborator vault holds for a blank allocator."""


@dataclass
class InterInterfaceState:
    """Canonical model state for Allocator operations."""

    allocated: int = 0
    vault_reserves: int = INITIAL_VAULT_RESERVES


class InterInterfaceStateMachine(StateMachine[InterInterfaceState]):
    """Unified Pretense State Machine for Allocator."""

    def __init__(
        self,
        state: Optional[InterInterfaceState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or InterInterfaceState(), singletons=singletons)

    @transition(Allocator.allocate)
    def allocate(
        self,
        amount: int,
    ) -> None:
        """Allocates funds by reserving them from the collaborator vault."""
        require_arg(amount, Domain.type(int), preferred=[1, 10, 100])
        if amount <= 0:
            with raises(AllocationLimitError):
                self.inner_allocate(amount)
            return None
        if amount > self.state.vault_reserves:
            with raises(AllocationLimitError):
                self.inner_allocate(amount)
            return None
        self.state.vault_reserves -= amount
        self.state.allocated += amount
        ret = self.inner_allocate(amount)
        assert self.state.allocated >= amount
        return ret

    @transition(Allocator.release)
    def release(
        self,
        amount: int,
    ) -> None:
        """Releases previously allocated funds back to the collaborator vault."""
        require_arg(amount, Domain.type(int), preferred=[1, 5, 10])
        if amount <= 0 or amount > self.state.allocated:
            with raises(AllocationLimitError):
                self.inner_release(amount)
            return None
        self.state.allocated -= amount
        self.state.vault_reserves += amount
        ret = self.inner_release(amount)
        assert self.state.allocated >= 0
        return ret

    @transition(name="allocated")
    def allocated(self) -> int:
        """Current amount of cumulative funds actively allocated."""
        ret = self.inner_allocated()
        assert ret == self.state.allocated
        return ret


proto = InterInterfaceStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeInterInterface = synthesize_fake(InterInterfaceStateMachine)


def make_inter_interface_fake(state: Optional[InterInterfaceState] = None) -> Allocator:
    """Synthesizes a fake instance for Allocator."""
    return FakeInterInterface(state=state or InterInterfaceState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestInterInterfaceFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeded state."""

    def setUp(self) -> None:
        self.fake = make_inter_interface_fake()
        self.sm = InterInterfaceStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions on the fake."""
        self.assertEqual(self.fake.allocated, 0)
        self.fake.allocate(10)
        self.assertEqual(self.fake.allocated, 10)
        self.fake.release(4)
        self.assertEqual(self.fake.allocated, 6)
        self.fake.allocate(2)
        self.assertEqual(self.fake.allocated, 8)
        self.fake.release(8)
        self.assertEqual(self.fake.allocated, 0)

    def test_invalid_amount_rejections(self) -> None:
        """Verifies the contracted rejection of non-positive and excessive amounts."""
        self.fake.allocate(10)
        with self.assertRaises(AllocationLimitError):
            self.fake.allocate(0)
        with self.assertRaises(AllocationLimitError):
            self.fake.allocate(-5)
        with self.assertRaises(AllocationLimitError):
            self.fake.release(0)
        with self.assertRaises(AllocationLimitError):
            self.fake.release(self.fake.allocated + 1)
        self.assertEqual(self.fake.allocated, 10)

    def test_insufficient_vault_reserves(self) -> None:
        """Verifies the contracted rejection of allocations beyond vault reserves."""
        with self.assertRaises(AllocationLimitError):
            self.fake.allocate(INITIAL_VAULT_RESERVES + 1)
        self.assertEqual(self.fake.allocated, 0)
        self.fake.allocate(INITIAL_VAULT_RESERVES)
        self.assertEqual(self.fake.allocated, INITIAL_VAULT_RESERVES)


# ==============================================================================
# 4. Fake Hypothesis Fuzzing
# ==============================================================================

FakeInterInterfaceFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=InterInterfaceState,
    name="FakeInterInterfaceFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:45:46Z
# LAST_CHANGED: 2026-11-08T17:45:46Z
# CHANGE: Aligned the over-reserve allocation oracle with the contract and observed SUT behavior: allocate now declares raises(AllocationLimitError) for amounts exceeding the mirrored collaborator vault reserves instead of InsufficientFundsError, matching the interface contract and what the concrete allocator raises; the fake scenario test_insufficient_vault_reserves asserts AllocationLimitError and the now-unused InsufficientFundsError import is dropped.
# --- END AUTOFAB METADATA ---


# === File: vault_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for Vault."""

from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_4.parts.inter_interface.pretense.vault_pretense import (
    FakeVault,
    VaultState,
    VaultStateMachine,
    make_vault_fake,
)
from benchmark_4.parts.inter_interface.lib.vault import (
    InsufficientFundsError,
    VaultInactiveException,
)
from benchmark_4.parts.inter_interface.lib.vault_impl import Vault
from benchmark_4.parts.inter_interface.lib.inter_interface_impl import __initialize__ as _ii_initialize
from benchmark_4.parts.inter_interface.lib.vault_impl import __initialize__ as _v_initialize


# ==============================================================================
# 1. Implementation Pseudo State Machine
# ==============================================================================

class VaultImplPseudoStateMachine(VaultStateMachine):
    """Implementation pseudo-state machine observing the concrete Vault."""

    @transition(Vault.deposit)
    def deposit(
        self,
        amount: int,
    ) -> Any:
        target: Vault = sut(Vault)
        before = target.balance
        ret = call_target(target.deposit(amount))
        assert target.balance == before + amount
        return ret

    @transition(Vault.withdraw)
    def withdraw(
        self,
        amount: int,
    ) -> Any:
        target: Vault = sut(Vault)
        before = target.balance
        ret = call_target(target.withdraw(amount))
        assert target.balance == before - amount
        return ret

    @transition(Vault.set_active)
    def set_active(
        self,
        active: bool,
    ) -> Any:
        target: Vault = sut(Vault)
        ret = call_target(target.set_active(active))
        assert target.is_active == active
        return ret

    @transition(name="balance")
    def balance(self) -> int:
        target: Vault = sut(Vault)
        ret = call_target(getattr(target, "balance"))
        assert ret == self.state.balance
        return ret

    @transition(name="is_active")
    def is_active(self) -> bool:
        target: Vault = sut(Vault)
        ret = call_target(getattr(target, "is_active"))
        assert ret == self.state.is_active
        return ret

    @transition.seeding
    def seed_balance(self, amount: int) -> None:
        target: Vault = sut(Vault)
        before = target.balance
        ret = call_target(target.deposit(amount))
        assert target.balance == before + amount
        return None

    @transition.seeding
    def seed_inactive(self) -> None:
        target: Vault = sut(Vault)
        ret = call_target(target.set_active(False))
        assert not target.is_active
        return None


proto = VaultImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestVaultImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the Vault contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ii_initialize(self.registry)
        _v_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(Vault)
        self.sm = VaultImplPseudoStateMachine(singletons={Vault: self.real})
        self.checked = self.sm.as_checked(Vault, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        """Drives deposit, withdraw, and activation scenarios against the real vault."""
        self.checked.deposit(10)
        self.assertEqual(self.checked.balance, 10)
        self.checked.withdraw(4)
        self.assertEqual(self.checked.balance, 6)
        self.assertTrue(self.checked.is_active)
        self.checked.set_active(False)
        self.assertFalse(self.checked.is_active)
        with self.assertRaises(VaultInactiveException):
            self.checked.deposit(3)
        with self.assertRaises(VaultInactiveException):
            self.checked.withdraw(2)
        self.assertEqual(self.checked.balance, 6)
        self.checked.set_active(True)
        self.assertTrue(self.checked.is_active)
        self.checked.deposit(4)
        self.assertEqual(self.checked.balance, 10)

    def test_invalid_amount_rejections(self) -> None:
        """Verifies the contracted rejection of non-positive and excessive amounts."""
        self.checked.deposit(10)
        with self.assertRaises(InsufficientFundsError):
            self.checked.deposit(0)
        with self.assertRaises(InsufficientFundsError):
            self.checked.deposit(-5)
        with self.assertRaises(InsufficientFundsError):
            self.checked.withdraw(0)
        with self.assertRaises(InsufficientFundsError):
            self.checked.withdraw(self.checked.balance + 1)
        self.assertEqual(self.checked.balance, 10)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> Vault:
    """Creates a fresh concrete Vault within an active system lifecycle scope."""
    registry = LifecycleRegistry()
    _ii_initialize(registry)
    _v_initialize(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(Vault)


VaultFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=VaultState,
    name="VaultFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:45:10Z
# LAST_CHANGED: 2026-11-08T17:44:31Z
# CHANGE: Resolved overspecified-oracle feedback: removed the duplicated withdrawal/deposit rejection guards from the implementation pseudo-state machine. The impl overrides now only observe the real SUT around the call_target pivot (balance delta asserts) and no longer re-evaluate model precondition branches against post-mutation self.state, which previously turned a valid withdraw(1) after deposit(1) into a spurious expected InsufficientFundsError. Contracted failure outcomes (invalid amounts, inactive vault) remain declared once by the inherited interface transitions, and the deterministic rejection scenarios in TestVaultImplReal are retained.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:45:10Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:44:53Z
# --- END AUTOFAB METADATA ---


# === File: vault_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for Vault."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
    StateMachine,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_4.parts.inter_interface.lib.vault import (
    InsufficientFundsError,
    Vault,
    VaultInactiveException,
)


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================

@dataclass
class VaultState:
    """Canonical model state for Vault operations."""

    balance: int = 0
    is_active: bool = True


class VaultStateMachine(StateMachine[VaultState]):
    """Unified Pretense State Machine for Vault."""

    def __init__(
        self,
        state: Optional[VaultState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or VaultState(), singletons=singletons)

    @transition(Vault.deposit)
    def deposit(
        self,
        amount: int,
    ) -> None:
        """Deposits funds into the vault, rejecting non-positive amounts."""
        require_arg(amount, Domain.type(int), preferred=[1, 10, 100])
        if amount <= 0:
            with raises(InsufficientFundsError):
                self.inner_deposit(amount)
            return None
        if not self.state.is_active:
            with raises(VaultInactiveException):
                self.inner_deposit(amount)
            return None
        self.state.balance += amount
        ret = self.inner_deposit(amount)
        assert self.state.balance >= amount
        return ret

    @transition(Vault.withdraw)
    def withdraw(
        self,
        amount: int,
    ) -> None:
        """Withdraws funds from the vault, rejecting non-positive or excessive amounts."""
        require_arg(amount, Domain.type(int), preferred=[1, 5, 10])
        if amount <= 0 or amount > self.state.balance:
            with raises(InsufficientFundsError):
                self.inner_withdraw(amount)
            return None
        if not self.state.is_active:
            with raises(VaultInactiveException):
                self.inner_withdraw(amount)
            return None
        self.state.balance -= amount
        ret = self.inner_withdraw(amount)
        assert self.state.balance >= 0
        return ret

    @transition(Vault.set_active)
    def set_active(
        self,
        active: bool,
    ) -> None:
        """Test-only hook toggling vault availability."""
        require_arg(active, Domain.boolean())
        self.state.is_active = active
        ret = self.inner_set_active(active)
        assert self.state.is_active == active
        return ret

    @transition(name="balance")
    def balance(self) -> int:
        """Current asset balance held in the vault."""
        ret = self.inner_balance()
        assert ret == self.state.balance
        return ret

    @transition(name="is_active")
    def is_active(self) -> bool:
        """Indicates whether the vault service is currently active."""
        ret = self.inner_is_active()
        assert ret == self.state.is_active
        return ret

    @transition.seeding
    def seed_balance(self, amount: int) -> None:
        """Seeds pre-existing vault reserves to exercise withdrawal scenarios."""
        require(self.state.is_active)
        require_arg(amount, Domain.range(1, 1000), preferred=[100])
        self.state.balance += amount

    @transition.seeding
    def seed_inactive(self) -> None:
        """Seeds an inactive vault to exercise contracted failure postconditions."""
        self.state.is_active = False


proto = VaultStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeVault = synthesize_fake(VaultStateMachine)


def make_vault_fake(state: Optional[VaultState] = None) -> Vault:
    """Synthesizes a fake instance for Vault."""
    return FakeVault(state=state or VaultState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestVaultFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_vault_fake()
        self.sm = VaultStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_balance(50)
        self.sm.seed_inactive()
        self.assertEqual(self.fake.balance, 0)
        self.fake.deposit(10)
        self.assertEqual(self.fake.balance, 10)
        self.fake.withdraw(4)
        self.assertEqual(self.fake.balance, 6)
        self.assertTrue(self.fake.is_active)
        self.fake.set_active(False)
        self.assertFalse(self.fake.is_active)
        self.fake.set_active(True)
        self.assertTrue(self.fake.is_active)

    def test_invalid_amount_rejections(self) -> None:
        """Verifies the contracted rejection of non-positive and excessive amounts."""
        self.fake.deposit(10)
        with self.assertRaises(InsufficientFundsError):
            self.fake.deposit(0)
        with self.assertRaises(InsufficientFundsError):
            self.fake.deposit(-5)
        with self.assertRaises(InsufficientFundsError):
            self.fake.withdraw(0)
        with self.assertRaises(InsufficientFundsError):
            self.fake.withdraw(self.fake.balance + 1)
        self.assertEqual(self.fake.balance, 10)

    def test_inactive_vault_rejections(self) -> None:
        """Verifies the contracted inactive-vault postconditions on the fake."""
        self.fake.deposit(10)
        self.fake.set_active(False)
        with self.assertRaises(VaultInactiveException):
            self.fake.deposit(2)
        with self.assertRaises(VaultInactiveException):
            self.fake.withdraw(2)
        self.assertEqual(self.fake.balance, 10)
        self.fake.set_active(True)
        self.assertTrue(self.fake.is_active)


# ==============================================================================
# 4. Fake Hypothesis Fuzzing
# ==============================================================================

FakeVaultFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=VaultState,
    name="FakeVaultFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:40:56Z
# LAST_CHANGED: 2026-11-08T17:40:56Z
# CHANGE: Modeled contracted failure outcomes explicitly so deterministic scenarios can verify them: deposit now branches on non-positive amounts with raises(InsufficientFundsError), withdraw branches on non-positive or balance-exceeding amounts with raises(InsufficientFundsError), and both keep the inactive-vault raises(VaultInactiveException) branch; argument domains are open int domains with preferred biases so invalid amounts are generatable, and TestVaultFake adds invalid-amount and inactive-vault rejection scenarios for the fake double.
# --- END AUTOFAB METADATA ---
