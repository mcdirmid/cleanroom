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
from benchmark_5.parts.inter_interface.pretense.inter_interface_pretense import (
    AllocatorState,
    AllocatorStateMachine,
    FakeAllocator,
    make_allocator_fake,
)
from benchmark_5.parts.inter_interface.pretense.vault_pretense import (
    FakeVault,
    VaultState,
    VaultStateMachine,
    make_vault_fake,
)
from benchmark_5.parts.inter_interface.pretense.vault_impl_pretense import (
    VaultImplPseudoStateMachine,
)
from benchmark_5.parts.inter_interface.lib.inter_interface import AllocationLimitError
from benchmark_5.parts.inter_interface.lib.vault import (
    InsufficientFundsError,
    VaultInactiveException,
)
from benchmark_5.parts.inter_interface.lib.vault_impl import Vault
from benchmark_5.parts.inter_interface.lib.inter_interface_impl import Allocator
from benchmark_5.parts.inter_interface.lib.inter_interface_impl import (
    __initialize__ as _ii_initialize,
)
from benchmark_5.parts.inter_interface.lib.vault_impl import __initialize__ as _v_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class AllocatorImplPseudoStateMachine(AllocatorStateMachine):
    """Implementation pseudo-state machine for Allocator."""

    @transition(Allocator.allocate)
    def allocate(self, amount: int) -> Any:
        """Allocates funds by delegating reservation to the collaborator vault."""
        target: Allocator = sut(Allocator)
        before = target.allocated
        ret = call_target(target.allocate(amount))
        assert target.allocated == before + amount
        return ret

    @transition(Allocator.release)
    def release(self, amount: int) -> Any:
        """Releases allocated funds by delegating deposit to the collaborator vault."""
        target: Allocator = sut(Allocator)
        before = target.allocated
        ret = call_target(target.release(amount))
        assert target.allocated == before - amount
        return ret

    @transition(name="allocated")
    def allocated(self) -> Any:
        """Reports the real allocator's cumulative allocated funds."""
        target: Allocator = sut(Allocator)
        ret = call_target(target.allocated)
        assert ret == target.allocated
        return ret


proto = AllocatorImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================


class TestAllocatorImplReal(unittest.TestCase):
    """Verifies that the concrete allocator implementation satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ii_initialize(self.registry)
        _v_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(Allocator)
        self.real_vault = get_singleton(Vault)
        self.sm = AllocatorImplPseudoStateMachine(
            singletons={Allocator: self.real, Vault: self.real_vault}
        )
        self.checked = self.sm.as_checked(Allocator, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_allocate_release_round_trip(self) -> None:
        """Drives allocation and release against seeded collaborator reserves."""
        self.sm.seed_reserves(90)
        self.real_vault.deposit(90)
        assert self.checked.allocated == 0
        self.checked.allocate(40)
        assert self.checked.allocated == 40
        self.checked.release(25)
        assert self.checked.allocated == 15

    def test_inactive_vault_preserves_allocation(self) -> None:
        """Observes the collaborator inactive failure for allocate and release."""
        self.sm.seed_reserves(90)
        self.real_vault.deposit(90)
        self.checked.allocate(40)
        assert self.checked.allocated == 40
        self.real_vault.set_active(False)
        self.sm.seed_inactive()
        with self.assertRaises(VaultInactiveException):
            self.checked.allocate(10)
        assert self.checked.allocated == 40
        with self.assertRaises(VaultInactiveException):
            self.checked.release(10)
        assert self.checked.allocated == 40
        self.real_vault.set_active(True)
        self.sm.seed_active()
        self.checked.release(40)
        assert self.checked.allocated == 0

    def test_invalid_amounts_raise_allocation_limit(self) -> None:
        """Observes the contracted allocation limit failures for invalid amounts."""
        self.sm.seed_reserves(90)
        self.real_vault.deposit(90)
        with self.assertRaises(AllocationLimitError):
            self.checked.allocate(0)
        with self.assertRaises(AllocationLimitError):
            self.checked.allocate(-1)
        with self.assertRaises(AllocationLimitError):
            self.checked.release(5)
        assert self.checked.allocated == 0

    def test_insufficient_reserves_reject_allocation(self) -> None:
        """Observes the contracted rejection when allocation exceeds reserves."""
        self.sm.seed_reserves(90)
        self.real_vault.deposit(90)
        with self.assertRaises((AllocationLimitError, InsufficientFundsError)):
            self.checked.allocate(91)
        assert self.checked.allocated == 0
        self.checked.allocate(40)
        assert self.checked.allocated == 40


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================


def make_sut() -> Allocator:
    """Creates a freshly scoped concrete allocator instance for fuzzing."""
    registry = LifecycleRegistry()
    _ii_initialize(registry)
    _v_initialize(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    get_singleton(Vault)
    return get_singleton(Allocator)


AllocatorFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[VaultImplPseudoStateMachine],
    sut_factory=make_sut,
    initial_state_factory=AllocatorState,
    name="AllocatorFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T18:06:59Z
# LAST_CHANGED: 2026-11-08T18:06:32Z
# CHANGE: Added a real scenario exercising the insufficient-reserve rejection path (reserves=90, amount=91) so the rejection contract is no longer starved: the checked allocation guards the contracted failure with self.assertRaises over AllocationLimitError or the delegated vault InsufficientFundsError, verifies allocated remains unchanged, and then confirms a within-reserve allocation still succeeds. Only remaining static-check error is the tool-injected FEEDBACK metadata line quoting the contract slug.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T18:06:59Z
# PRETENSE_QA_AUDIT: 2026-11-08T18:06:48Z
# --- END AUTOFAB METADATA ---


# === File: inter_interface_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for Allocator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import unittest

from hypothesis import given, settings, strategies as st

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
from benchmark_5.parts.inter_interface.lib.inter_interface import (
    AllocationLimitError,
    Allocator,
)
from benchmark_5.parts.inter_interface.lib.vault import VaultInactiveException


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================


@dataclass
class AllocatorState:
    """Canonical model state for Allocator operations."""

    allocated: int = 0
    reserves: int = 0
    vault_active: bool = True


class AllocatorStateMachine(StateMachine[AllocatorState]):
    """Unified Pretense State Machine for Allocator."""

    def __init__(
        self,
        state: Optional[AllocatorState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or AllocatorState(), singletons=singletons)

    @transition(Allocator.allocate)
    def allocate(self, amount: int) -> None:
        """Allocates funds reserved from the collaborator vault."""
        require_arg(amount, Domain.type(int), preferred=[10])
        before_allocated = self.state.allocated
        before_reserves = self.state.reserves
        ret: Any = None
        if amount <= 0 or amount > before_reserves:
            with raises(AllocationLimitError):
                ret = self.inner_allocate(amount)
            assert self.state.allocated == before_allocated
        elif self.state.vault_active:
            ret = self.inner_allocate(amount)
            self.state.reserves = before_reserves - amount
            self.state.allocated = before_allocated + amount
            assert self.state.allocated == before_allocated + amount
        else:
            with raises(VaultInactiveException):
                ret = self.inner_allocate(amount)
            assert self.state.allocated == before_allocated
        assert ret is None
        return ret

    @transition(Allocator.release)
    def release(self, amount: int) -> None:
        """Releases allocated funds back into the collaborator vault."""
        require_arg(amount, Domain.type(int), preferred=[1])
        before_allocated = self.state.allocated
        before_reserves = self.state.reserves
        ret: Any = None
        if amount <= 0 or amount > before_allocated:
            with raises(AllocationLimitError):
                ret = self.inner_release(amount)
            assert self.state.allocated == before_allocated
        elif self.state.vault_active:
            ret = self.inner_release(amount)
            self.state.allocated = before_allocated - amount
            self.state.reserves = before_reserves + amount
            assert self.state.allocated == before_allocated - amount
        else:
            with raises(VaultInactiveException):
                ret = self.inner_release(amount)
            assert self.state.allocated == before_allocated
        assert ret is None
        return ret

    @transition(name="allocated")
    def allocated(self) -> int:
        """Reports the cumulative amount of funds actively allocated."""
        ret = self.inner_allocated()
        assert ret == self.state.allocated
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Restores the allocator to its pristine blank initial state."""
        self.state.allocated = 0
        self.state.reserves = 0
        self.state.vault_active = True

    @transition.seeding
    def seed_reserves(self, amount: int) -> None:
        """Seeds collaborator vault reserves so allocations become reachable."""
        require_arg(amount, Domain.range(1, 100), preferred=[50])
        self.state.reserves = self.state.reserves + amount

    @transition.seeding
    def seed_inactive(self) -> None:
        """Synchronizes the model with an inactive collaborator vault."""
        self.state.vault_active = False

    @transition.seeding
    def seed_active(self) -> None:
        """Synchronizes the model with an active collaborator vault."""
        self.state.vault_active = True


proto = AllocatorStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeAllocator = synthesize_fake(AllocatorStateMachine)


def make_allocator_fake(state: Optional[AllocatorState] = None) -> Allocator:
    """Synthesizes a fake allocator sharing the canonical model state."""
    return FakeAllocator(state=state or AllocatorState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestAllocatorFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_allocator_fake()
        self.sm = AllocatorStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every transition and seeding transition on the fake."""
        self.sm.seed_initial()
        self.sm.seed_reserves(50)
        self.sm.allocate(20)
        assert self.sm.allocated() == 20
        self.sm.release(5)
        assert self.sm.allocated() == 15
        self.sm.seed_inactive()
        self.sm.seed_active()
        self.sm.seed_initial()
        assert self.sm.allocated() == 0

        assert self.fake.allocated == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeAllocatorFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=AllocatorState,
    name="FakeAllocatorFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:54:17Z
# LAST_CHANGED: 2026-11-08T17:54:17Z
# CHANGE: Model the collaborator vault reserve precondition in the Allocator interface state machine: added reserves and vault-activity model fields with seeding transitions (seed_reserves, seed_inactive, seed_active) to keep the model synchronizable, opened the amount domains to Domain.type(int), and modeled the contracted AllocationLimitError branches (amount <= 0 or exceeding available reserves on allocate; amount <= 0 or exceeding allocated on release) with VaultInactiveException on the inactive path. Only remaining static-check error is the tool-injected FEEDBACK metadata line quoting the contract slug.
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
from benchmark_5.parts.inter_interface.pretense.vault_pretense import (
    FakeVault,
    VaultState,
    VaultStateMachine,
    make_vault_fake,
)
from benchmark_5.parts.inter_interface.lib.vault import (
    InsufficientFundsError,
    VaultInactiveException,
)
from benchmark_5.parts.inter_interface.lib.vault_impl import Vault
from benchmark_5.parts.inter_interface.lib.vault_impl import __initialize__ as _v_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class VaultImplPseudoStateMachine(VaultStateMachine):
    """Implementation pseudo-state machine for Vault."""

    @transition(Vault.deposit)
    def deposit(self, amount: int) -> Any:
        """Deposits a positive amount, observing the real vault postcondition."""
        target: Vault = sut(Vault)
        before = target.balance
        ret = call_target(target.deposit(amount))
        assert target.balance == before + amount
        return ret

    @transition(Vault.withdraw)
    def withdraw(self, amount: int) -> Any:
        """Withdraws a valid amount, observing the real vault postcondition."""
        target: Vault = sut(Vault)
        before = target.balance
        ret = call_target(target.withdraw(amount))
        assert target.balance == before - amount
        return ret

    @transition(Vault.set_active)
    def set_active(self, active: bool) -> Any:
        """Toggles vault availability, observing the real vault postcondition."""
        target: Vault = sut(Vault)
        ret = call_target(target.set_active(active))
        assert target.is_active == active
        return ret

    @transition(name="balance")
    def balance(self) -> Any:
        """Reports the real vault balance."""
        target: Vault = sut(Vault)
        ret = call_target(target.balance)
        assert ret == target.balance
        return ret

    @transition(name="is_active")
    def is_active(self) -> Any:
        """Reports whether the real vault is currently active."""
        target: Vault = sut(Vault)
        ret = call_target(target.is_active)
        assert ret == target.is_active
        return ret


proto = VaultImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================


class TestVaultImplReal(unittest.TestCase):
    """Verifies that the concrete vault implementation satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _v_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(Vault)
        self.sm = VaultImplPseudoStateMachine(singletons={Vault: self.real})
        self.checked = self.sm.as_checked(Vault, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_deposit_withdraw_round_trip(self) -> None:
        """Drives a deposit and withdrawal balance round trip."""
        self.checked.deposit(40)
        assert self.checked.balance == 40
        self.checked.deposit(10)
        assert self.checked.balance == 50
        self.checked.withdraw(20)
        assert self.checked.balance == 30

    def test_inactive_vault_rejects_operations(self) -> None:
        """Observes the inactive failure path while leaving the balance untouched."""
        self.checked.deposit(40)
        self.checked.set_active(False)
        assert self.checked.is_active is False
        with self.assertRaises(VaultInactiveException):
            self.checked.deposit(10)
        assert self.checked.balance == 40
        with self.assertRaises(VaultInactiveException):
            self.checked.withdraw(10)
        assert self.checked.balance == 40
        self.checked.set_active(True)
        assert self.checked.is_active is True
        self.checked.deposit(10)
        assert self.checked.balance == 50

    def test_invalid_amounts_raise_insufficient_funds(self) -> None:
        """Observes the contracted insufficient-funds failures for invalid amounts."""
        with self.assertRaises(InsufficientFundsError):
            self.checked.deposit(0)
        with self.assertRaises(InsufficientFundsError):
            self.checked.deposit(-1)
        assert self.checked.balance == 0
        with self.assertRaises(InsufficientFundsError):
            self.checked.withdraw(0)
        self.checked.deposit(10)
        assert self.checked.balance == 10
        with self.assertRaises(InsufficientFundsError):
            self.checked.withdraw(11)
        assert self.checked.balance == 10


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================


def make_sut() -> Vault:
    """Creates a freshly scoped concrete vault instance for fuzzing."""
    registry = LifecycleRegistry()
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
# LAST_CLEANED: 2026-11-08T17:52:15Z
# LAST_CHANGED: 2026-11-08T17:51:37Z
# CHANGE: Added a real scenario test covering the contracted invalid-amount failure witnesses (deposit 0 and -1, withdraw 0 and balance+1) guarded with self.assertRaises(InsufficientFundsError) after the interface amount domains were widened to open Domain.type(int) so those contract outcomes are reachable instead of starved. Only remaining static-check error is the tool-injected FEEDBACK metadata line quoting the contract slugs.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:52:15Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:51:51Z
# --- END AUTOFAB METADATA ---


# === File: vault_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for Vault."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import unittest

from hypothesis import given, settings, strategies as st

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
from benchmark_5.parts.inter_interface.lib.vault import (
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
    def deposit(self, amount: int) -> None:
        """Deposits a positive amount, raising when the vault is inactive."""
        require_arg(amount, Domain.type(int), preferred=[10])
        before = self.state.balance
        ret: Any = None
        if amount <= 0:
            with raises(InsufficientFundsError):
                ret = self.inner_deposit(amount)
            assert self.state.balance == before
        elif self.state.is_active:
            ret = self.inner_deposit(amount)
            self.state.balance = before + amount
            assert self.state.balance == before + amount
        else:
            with raises(VaultInactiveException):
                ret = self.inner_deposit(amount)
            assert self.state.balance == before
        assert ret is None
        return ret

    @transition(Vault.withdraw)
    def withdraw(self, amount: int) -> None:
        """Withdraws a positive amount bounded by the current balance."""
        require_arg(amount, Domain.type(int), preferred=[1])
        before = self.state.balance
        ret: Any = None
        if amount <= 0 or amount > before:
            with raises(InsufficientFundsError):
                ret = self.inner_withdraw(amount)
            assert self.state.balance == before
        elif self.state.is_active:
            ret = self.inner_withdraw(amount)
            self.state.balance = before - amount
            assert self.state.balance == before - amount
        else:
            with raises(VaultInactiveException):
                ret = self.inner_withdraw(amount)
            assert self.state.balance == before
        assert ret is None
        return ret

    @transition(Vault.set_active)
    def set_active(self, active: bool) -> None:
        """Toggles vault availability."""
        require_arg(active, Domain.boolean(), preferred=[True])
        ret = self.inner_set_active(active)
        self.state.is_active = active
        assert self.state.is_active == active
        assert ret is None
        return ret

    @transition(name="balance")
    def balance(self) -> int:
        """Reports the balance currently held by the vault."""
        ret = self.inner_balance()
        assert ret == self.state.balance
        return ret

    @transition(name="is_active")
    def is_active(self) -> bool:
        """Reports whether the vault is currently active."""
        ret = self.inner_is_active()
        assert ret == self.state.is_active
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Restores the vault to its pristine blank initial state."""
        self.state.balance = 0
        self.state.is_active = True


proto = VaultStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeVault = synthesize_fake(VaultStateMachine)


def make_vault_fake(state: Optional[VaultState] = None) -> Vault:
    """Synthesizes a fake vault sharing the canonical model state."""
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
        """Exercises every transition and seeding transition on the fake."""
        self.sm.seed_initial()
        self.sm.deposit(10)
        assert self.sm.balance() == 10
        assert self.sm.is_active()
        self.sm.withdraw(4)
        assert self.sm.balance() == 6
        self.sm.set_active(False)
        assert self.sm.is_active() is False
        self.sm.set_active(True)
        assert self.sm.is_active() is True

        assert self.fake.is_active
        self.fake.deposit(30)
        assert self.fake.balance == 30
        self.fake.withdraw(10)
        assert self.fake.balance == 20
        self.fake.set_active(False)
        assert self.fake.is_active is False
        self.fake.set_active(True)
        assert self.fake.is_active is True


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeVaultFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=VaultState,
    name="FakeVaultFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:51:34Z
# LAST_CHANGED: 2026-11-08T17:51:34Z
# CHANGE: Widen deposit/withdraw amount domains to open Domain.type(int) so invalid-amount contract outcomes are reachable, and model the contracted InsufficientFundsError branches (amount <= 0 for deposit; amount <= 0 or amount > balance for withdraw) in the Vault model transitions, with the open-domain preferred biases retained.
# --- END AUTOFAB METADATA ---
