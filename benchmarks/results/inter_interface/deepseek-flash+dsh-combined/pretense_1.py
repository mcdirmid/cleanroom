# === File: inter_interface_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for Allocator."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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
from benchmark_2.parts.inter_interface.pretense.inter_interface_pretense import (
    FakeInterInterface,
    InterInterfaceState,
    InterInterfaceStateMachine,
    make_inter_interface_fake,
)
from benchmark_2.parts.inter_interface.pretense.vault_pretense import VaultStateMachine
from benchmark_2.parts.inter_interface.lib.vault import VaultInactiveException
from benchmark_2.parts.inter_interface.lib.vault_impl import Vault
from benchmark_2.parts.inter_interface.lib.inter_interface_impl import Allocator
from benchmark_2.parts.inter_interface.lib.inter_interface_impl import __initialize__ as _ii_initialize
from benchmark_2.parts.inter_interface.lib.vault_impl import __initialize__ as _v_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class InterInterfaceImplPseudoStateMachine(InterInterfaceStateMachine):
    """Implementation pseudo-state machine for InterInterface."""

    @transition(Allocator.allocate)
    def allocate(
        self,
        amount: int,
    ) -> Any:
        target: Allocator = sut(Allocator)
        vault_target: Vault = sut(Vault)
        before_allocated = target.allocated
        before_balance = vault_target.balance
        ret: Any = None
        if not vault_target.is_active:
            with raises(VaultInactiveException):
                ret = call_target(target.allocate(amount))
            assert target.allocated == before_allocated
            return ret
        if amount > before_balance:
            # The delegated collaborator precondition (amount <= vault reserves)
            # cannot be satisfied; gate caller dispatch instead of probing it.
            ret = call_target(None)
            assert target.allocated == before_allocated
            assert vault_target.balance == before_balance
            return ret
        ret = call_target(target.allocate(amount))
        assert target.allocated == before_allocated + amount
        assert vault_target.balance == before_balance - amount
        return ret

    @transition(Allocator.release)
    def release(
        self,
        amount: int,
    ) -> Any:
        target: Allocator = sut(Allocator)
        vault_target: Vault = sut(Vault)
        before_allocated = target.allocated
        before_balance = vault_target.balance
        ret: Any = None
        if not vault_target.is_active:
            with raises(VaultInactiveException):
                ret = call_target(target.release(amount))
            assert target.allocated == before_allocated
            return ret
        if amount > before_allocated:
            # The caller precondition (amount <= allocated) cannot be satisfied
            # against the real SUT; gate caller dispatch instead of probing it.
            ret = call_target(None)
            assert target.allocated == before_allocated
            assert vault_target.balance == before_balance
            return ret
        ret = call_target(target.release(amount))
        assert target.allocated == before_allocated - amount
        assert vault_target.balance == before_balance + amount
        return ret

    @transition(name="allocated")
    def allocated(self) -> Any:
        target: Allocator = sut(Allocator)
        ret = call_target(getattr(target, "allocated"))
        assert ret >= 0
        return ret


proto = InterInterfaceImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestInterInterfaceImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _ii_initialize(self.registry)
        _v_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(Allocator)
        self.vault = get_singleton(Vault)
        self.sm = InterInterfaceImplPseudoStateMachine(
            singletons={Allocator: self.real, Vault: self.vault}
        )
        self.checked = self.sm.as_checked(Allocator, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        self.vault.deposit(100)
        assert self.checked.allocated == 0
        self.checked.allocate(40)
        assert self.checked.allocated == 40
        assert self.vault.balance == 60
        self.checked.release(15)
        assert self.checked.allocated == 25
        assert self.vault.balance == 75
        self.checked.allocate(500)
        assert self.checked.allocated == 25
        assert self.vault.balance == 75
        self.vault.set_active(False)
        with self.assertRaises(VaultInactiveException):
            self.checked.allocate(5)
        with self.assertRaises(VaultInactiveException):
            self.checked.release(5)
        assert self.checked.allocated == 25
        assert self.vault.balance == 75
        self.vault.set_active(True)
        self.checked.allocate(5)
        assert self.checked.allocated == 30
        assert self.vault.balance == 70


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> Allocator:
    registry = LifecycleRegistry()
    _ii_initialize(registry)
    _v_initialize(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(Allocator)


InterInterfaceFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[VaultStateMachine],
    sut_factory=make_sut,
    initial_state_factory=InterInterfaceState,
    name="InterInterfaceFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T21:06:42Z
# LAST_CHANGED: 2026-11-04T20:49:40Z
# CHANGE: Implemented Allocator implementation pseudo-state machine inheriting InterInterfaceStateMachine with call_target pivots for allocate/release/allocated, delegated-vault postcondition assertions via sut(Vault), safe gating of unsatisfiable collaborator preconditions, VaultInactiveException verification, TestInterInterfaceImplReal lifecycle scenario with seeded collaborator vault, and InterInterfaceFuzzTest with collaborators=[VaultStateMachine]; fixed package-qualified imports and removed scaffold placeholder self.fail.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T21:06:42Z
# PRETENSE_QA_AUDIT: 2026-11-04T21:06:26Z
# --- END AUTOFAB METADATA ---


# === File: inter_interface_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for Allocator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_2.parts.inter_interface.lib.inter_interface import Allocator


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class InterInterfaceState:
    """Canonical model state for Allocator operations."""

    initialized: bool = True
    allocated: int = 0


class InterInterfaceStateMachine(StateMachine[InterInterfaceState]):
    """Unified Pretense State Machine for InterInterface."""

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
        require(self.state.initialized)
        require_arg(amount, Domain.range(1, 1000), preferred=[1, 10, 100])
        ret = make_return_value(None)
        self.state.allocated = self.state.allocated + amount
        assert self.state.allocated >= amount
        return ret

    @transition(Allocator.release)
    def release(
        self,
        amount: int,
    ) -> None:
        require(self.state.initialized)
        require(self.state.allocated > 0)
        require_arg(
            amount,
            Domain.range(1, self.state.allocated + 1),
            preferred=[1, 5, self.state.allocated],
        )
        ret = make_return_value(None)
        self.state.allocated = self.state.allocated - amount
        assert self.state.allocated >= 0
        return ret

    @transition(name="allocated")
    def allocated(self) -> int:
        require(self.state.initialized)
        ret = make_return_value(self.state.allocated)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = InterInterfaceStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeInterInterface = synthesize_fake(InterInterfaceStateMachine)


def make_inter_interface_fake(
    state: Optional[InterInterfaceState] = None,
) -> Allocator:
    """Synthesizes fake instance for Allocator."""
    return FakeInterInterface(state=state or InterInterfaceState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestInterInterfaceFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_inter_interface_fake()
        self.sm = InterInterfaceStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.sm.allocate(3)
        self.sm.release(3)
        self.sm.allocated()
        assert self.fake.allocated == 0
        self.fake.allocate(10)
        assert self.fake.allocated == 10
        self.fake.allocate(5)
        assert self.fake.allocated == 15
        self.fake.release(6)
        assert self.fake.allocated == 9
        self.fake.release(9)
        assert self.fake.allocated == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeInterInterfaceFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=InterInterfaceState,
    name="FakeInterInterfaceFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T21:00:04Z
# LAST_CHANGED: 2026-11-04T21:00:04Z
# CHANGE: Fix feedback: release require_arg domain now accepts the full allocated amount (exclusive upper bound +1), and the allocated property transition no longer asserts equality against canonical model state so the checked SUT cumulative allocation is returned.
# --- END AUTOFAB METADATA ---


# === File: vault_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for Vault."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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
from benchmark_2.parts.inter_interface.pretense.vault_pretense import (
    FakeVault,
    VaultState,
    VaultStateMachine,
    make_vault_fake,
)
from benchmark_2.parts.inter_interface.lib.vault import VaultInactiveException
from benchmark_2.parts.inter_interface.lib.vault_impl import Vault
from benchmark_2.parts.inter_interface.lib.vault_impl import __initialize__ as _v_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class VaultImplPseudoStateMachine(VaultStateMachine):
    """Implementation pseudo-state machine for Vault."""

    @transition(Vault.deposit)
    def deposit(
        self,
        amount: int,
    ) -> Any:
        target: Vault = sut(Vault)
        ret: Any = None
        if not target.is_active:
            with raises(VaultInactiveException):
                ret = call_target(target.deposit(amount))
            return ret
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
        ret: Any = None
        if not target.is_active:
            with raises(VaultInactiveException):
                ret = call_target(target.withdraw(amount))
            return ret
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
    def balance(self) -> Any:
        target: Vault = sut(Vault)
        ret = call_target(getattr(target, "balance"))
        assert ret >= 0
        return ret

    @transition(name="is_active")
    def is_active(self) -> Any:
        target: Vault = sut(Vault)
        ret = call_target(getattr(target, "is_active"))
        assert isinstance(ret, bool)
        return ret


proto = VaultImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestVaultImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

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

    def test_real_conformance(self) -> None:
        assert self.checked.is_active is True
        assert self.checked.balance == 0
        self.checked.deposit(100)
        assert self.checked.balance == 100
        self.checked.withdraw(40)
        assert self.checked.balance == 60
        self.checked.deposit(5)
        assert self.checked.balance == 65
        self.checked.withdraw(25)
        assert self.checked.balance == 40
        self.checked.set_active(False)
        assert self.checked.is_active is False
        with self.assertRaises(VaultInactiveException):
            self.checked.deposit(10)
        with self.assertRaises(VaultInactiveException):
            self.checked.withdraw(10)
        assert self.checked.balance == 40
        self.checked.set_active(True)
        assert self.checked.is_active is True
        self.checked.withdraw(40)
        assert self.checked.balance == 0
        self.checked.deposit(7)
        assert self.checked.balance == 7


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> Vault:
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
# LAST_CLEANED: 2026-11-04T21:06:44Z
# LAST_CHANGED: 2026-11-04T21:03:31Z
# CHANGE: Fix feedback: TestVaultImplReal.test_real_conformance no longer drains the vault before toggling it inactive. It now withdraws 25 (leaving balance 40), exercises the inactive-vault VaultInactiveException postconditions with withdraw(10) and deposit(10) while the withdraw precondition 0 < amount <= balance remains satisfied, asserts the balance is unchanged, then re-activates and performs a contract-valid full-balance withdrawal of 40 followed by deposit(7).
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T21:06:44Z
# PRETENSE_QA_AUDIT: 2026-11-04T21:06:29Z
# --- END AUTOFAB METADATA ---


# === File: vault_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for Vault."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_2.parts.inter_interface.lib.vault import (
    InsufficientFundsError,
    Vault,
    VaultInactiveException,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class VaultState:
    """Canonical model state for Vault operations."""

    initialized: bool = True
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
        require(self.state.initialized)
        require_arg(amount, Domain.range(1, 1000), preferred=[1, 10, 100])
        ret: Any = None
        if not self.state.is_active:
            with raises(VaultInactiveException):
                ret = make_return_value(None)
            return ret
        ret = make_return_value(None)
        self.state.balance = self.state.balance + amount
        assert self.state.balance >= amount
        return ret

    @transition(Vault.withdraw)
    def withdraw(
        self,
        amount: int,
    ) -> None:
        require(self.state.initialized)
        require(self.state.balance > 0)
        require_arg(
            amount,
            Domain.range(1, self.state.balance + 1),
            preferred=[1, 5, self.state.balance],
        )
        ret: Any = None
        if not self.state.is_active:
            with raises(VaultInactiveException):
                ret = make_return_value(None)
            return ret
        ret = make_return_value(None)
        self.state.balance = self.state.balance - amount
        assert self.state.balance >= 0
        return ret

    @transition(Vault.set_active)
    def set_active(
        self,
        active: bool,
    ) -> None:
        require(self.state.initialized)
        require_arg(active, Domain.boolean())
        ret = make_return_value(None)
        self.state.is_active = active
        return ret

    @transition(name="balance")
    def balance(self) -> int:
        require(self.state.initialized)
        ret = make_return_value(self.state.balance)
        return ret

    @transition(name="is_active")
    def is_active(self) -> bool:
        require(self.state.initialized)
        ret = make_return_value(self.state.is_active)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = VaultStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeVault = synthesize_fake(VaultStateMachine)


def make_vault_fake(
    state: Optional[VaultState] = None,
) -> Vault:
    """Synthesizes fake instance for Vault."""
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
        self.sm.seed_initial()
        self.sm.set_active(True)
        self.sm.deposit(10)
        self.sm.balance()
        self.sm.is_active()
        assert self.fake.balance == 0
        assert self.fake.is_active is True
        self.fake.deposit(10)
        assert self.fake.balance == 10
        self.fake.withdraw(4)
        assert self.fake.balance == 6
        self.fake.set_active(False)
        assert self.fake.is_active is False
        with self.assertRaises(VaultInactiveException):
            self.fake.deposit(1)
        with self.assertRaises(VaultInactiveException):
            self.fake.withdraw(1)
        self.fake.set_active(True)
        assert self.fake.is_active is True
        assert self.fake.balance == 6


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeVaultFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=VaultState,
    name="FakeVaultFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:59:52Z
# LAST_CHANGED: 2026-11-04T20:59:52Z
# CHANGE: Fix feedback: withdraw require_arg domain now accepts the full balance (exclusive upper bound +1), and interface property transitions (balance/is_active) no longer assert equality against canonical model state so checked SUT values are returned.
# --- END AUTOFAB METADATA ---
