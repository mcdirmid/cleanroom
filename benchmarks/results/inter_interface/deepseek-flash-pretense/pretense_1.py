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
from benchmark_5.parts.inter_interface.lib import vault
from benchmark_5.parts.inter_interface.lib.inter_interface_impl import (
    Allocator,
    __initialize__,
)
from benchmark_5.parts.inter_interface.pretense.inter_interface_pretense import (
    FakeInterInterface,
    InterInterfaceState,
    InterInterfaceStateMachine,
    make_inter_interface_fake,
)
from benchmark_5.parts.inter_interface.pretense.vault_pretense import (
    VaultState,
    VaultStateMachine,
    make_vault_fake,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class InterInterfaceImplPseudoStateMachine(InterInterfaceStateMachine):
    """Implementation pseudo-state machine for Allocator."""

    @transition(Allocator.allocate)
    def allocate(
        self,
        amount: int,
    ) -> Any:
        target: Allocator = sut(Allocator)
        vault_state = sut_state(VaultState)
        old_allocated = target.allocated
        old_balance = vault_state.balance
        ret: Any = None
        if amount <= old_balance:
            ret = call_target(target.allocate(amount))
            assert target.allocated == old_allocated + amount
            assert vault_state.balance == old_balance - amount
        return ret

    @transition(Allocator.release)
    def release(
        self,
        amount: int,
    ) -> Any:
        target: Allocator = sut(Allocator)
        vault_state = sut_state(VaultState)
        old_allocated = target.allocated
        old_balance = vault_state.balance
        ret: Any = None
        if amount <= old_allocated:
            ret = call_target(target.release(amount))
            assert target.allocated == old_allocated - amount
            assert vault_state.balance == old_balance + amount
        return ret

    @transition(name="allocated")
    def allocated(self) -> int:
        target: Allocator = sut(Allocator)
        ret = call_target(target.allocated)
        return ret


proto = InterInterfaceImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestInterInterfaceImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.collaborator = make_vault_fake()
        self.registry.register_instance(
            self.collaborator,
            keys=[vault.Vault],
            tier=system,
        )
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(Allocator)
        self.sm = InterInterfaceImplPseudoStateMachine(
            singletons={Allocator: self.real, vault.Vault: self.collaborator}
        )
        self.checked = self.sm.as_checked(Allocator, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        self.collaborator.deposit(20)
        assert self.checked.allocated == 0
        self.checked.allocate(10)
        assert self.checked.allocated == 10
        self.checked.release(4)
        assert self.checked.allocated == 6
        self.collaborator.set_active(False)
        with self.assertRaises(vault.VaultInactiveException):
            self.checked.allocate(2)
        assert self.checked.allocated == 6
        with self.assertRaises(vault.VaultInactiveException):
            self.checked.release(2)
        assert self.checked.allocated == 6
        self.collaborator.set_active(True)
        self.checked.release(6)
        assert self.checked.allocated == 0


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> Allocator:
    registry = LifecycleRegistry()
    __initialize__(registry)
    collaborator = make_vault_fake()
    registry.register_instance(
        collaborator,
        keys=[vault.Vault],
        tier=system,
    )
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
# LAST_CLEANED: 2026-11-04T18:43:31Z
# LAST_CHANGED: 2026-11-04T18:38:42Z
# CHANGE: Fixed feedback: make_sut now installs a blank pretense vault collaborator instance into the lifecycle registry under vault.Vault (the same modeled collaborator state sut_state(VaultState) inspects, and the collaborator VaultStateMachine drives), so the real allocator can resolve its collaborator during fuzzing instead of aborting on lifecycle resolution. TestInterInterfaceImplReal now expects the contracted vault.VaultInactiveException using a real catching assertion, self.assertRaises, for the inactive-vault allocate(2)/release(2), then asserts allocated is unchanged. Allocate/release overrides also gate on the inspected collaborator balance/allocated so unfunded fuzz draws cannot violate the collaborator precondition, while successful calls still assert the allocated and modeled vault balance postconditions.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T18:43:31Z
# PRETENSE_QA_AUDIT: 2026-11-04T18:43:18Z
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
from benchmark_5.parts.inter_interface.lib.inter_interface import Allocator
from benchmark_5.parts.inter_interface.lib.vault import VaultInactiveException
from benchmark_5.parts.inter_interface.pretense.vault_pretense import (
    VaultState,
    VaultStateMachine,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class InterInterfaceState:
    """Canonical model state for Allocator operations."""

    initialized: bool = True
    allocated: int = 0


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
        require(self.state.initialized)
        vault = sut_state(VaultState)
        require_arg(amount, Domain.range(1, 1000), preferred=[1, 10])
        if not vault.is_active:
            with raises(VaultInactiveException):
                self.inner_allocate(amount)
            return None
        if amount > vault.balance:
            return None
        ret = self.inner_allocate(amount)
        self.state.allocated = self.state.allocated + amount
        assert ret is None
        return ret

    @transition(Allocator.release)
    def release(
        self,
        amount: int,
    ) -> None:
        require(self.state.initialized)
        vault = sut_state(VaultState)
        require_arg(amount, Domain.range(1, 1000), preferred=[1, 10])
        if not vault.is_active:
            with raises(VaultInactiveException):
                self.inner_release(amount)
            return None
        if amount > self.state.allocated:
            return None
        ret = self.inner_release(amount)
        self.state.allocated = self.state.allocated - amount
        assert ret is None
        return ret

    @transition(name="allocated")
    def allocated(self) -> int:
        require(self.state.initialized)
        ret = self.inner_allocated()
        assert ret == self.state.allocated
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
        _ = self.fake.allocated
        self.fake.allocate(1)
        self.fake.release(1)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeInterInterfaceFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[VaultStateMachine],
    initial_state_factory=InterInterfaceState,
    name="FakeInterInterfaceFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:40:41Z
# LAST_CHANGED: 2026-11-04T18:21:29Z
# CHANGE: Implemented Allocator interface pretense: package-qualified imports, allocated model state, allocate/release transitions gated on sut_state(VaultState) activity/funds, allocated property transition, synthesized FakeInterInterface + make_inter_interface_fake, TestInterInterfaceFake transition coverage, and FakeInterInterfaceFuzzTest with VaultStateMachine collaborators.
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
from benchmark_5.parts.inter_interface.lib.vault import VaultInactiveException
from benchmark_5.parts.inter_interface.lib.vault_impl import Vault, __initialize__


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
        old_balance = target.balance
        ret = call_target(target.deposit(amount))
        assert target.balance == old_balance + amount
        return ret

    @transition(Vault.withdraw)
    def withdraw(
        self,
        amount: int,
    ) -> Any:
        target: Vault = sut(Vault)
        old_balance = target.balance
        ret = call_target(target.withdraw(amount))
        assert target.balance == old_balance - amount
        return ret

    @transition(Vault.set_active)
    def set_active(
        self,
        active: bool,
    ) -> Any:
        target: Vault = sut(Vault)
        ret = call_target(target.set_active(active))
        assert target.is_active is active
        return ret

    @transition(name="balance")
    def balance(self) -> int:
        target: Vault = sut(Vault)
        ret = call_target(target.balance)
        return ret

    @transition(name="is_active")
    def is_active(self) -> bool:
        target: Vault = sut(Vault)
        ret = call_target(target.is_active)
        return ret


proto = VaultImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestVaultImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(Vault)
        self.sm = VaultImplPseudoStateMachine(singletons={Vault: self.real})
        self.checked = self.sm.as_checked(Vault, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        assert self.checked.balance == 0
        assert self.checked.is_active is True
        self.checked.deposit(10)
        assert self.checked.balance == 10
        self.checked.withdraw(4)
        assert self.checked.balance == 6
        self.checked.set_active(False)
        assert self.checked.is_active is False
        with self.assertRaises(VaultInactiveException):
            self.checked.deposit(5)
        assert self.checked.balance == 6
        with self.assertRaises(VaultInactiveException):
            self.checked.withdraw(2)
        assert self.checked.balance == 6
        self.checked.set_active(True)
        assert self.checked.is_active is True
        self.checked.withdraw(6)
        assert self.checked.balance == 0


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> Vault:
    registry = LifecycleRegistry()
    __initialize__(registry)
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
# LAST_CLEANED: 2026-11-04T18:43:33Z
# LAST_CHANGED: 2026-11-04T18:38:36Z
# CHANGE: Fixed feedback: TestVaultImplReal now uses unittest's catching assertion self.assertRaises(VaultInactiveException) around the checked deposit(5) and withdraw(2) on the inactive vault (the pretense raises context re-raises at block exit and does not absorb), then asserts the balance was left unchanged; the active branch still asserts increments/decrements.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T18:43:33Z
# PRETENSE_QA_AUDIT: 2026-11-04T18:43:20Z
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
from benchmark_5.parts.inter_interface.lib.vault import Vault, VaultInactiveException


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
        if not self.state.is_active:
            with raises(VaultInactiveException):
                self.inner_deposit(amount)
            return None
        ret = self.inner_deposit(amount)
        self.state.balance = self.state.balance + amount
        assert ret is None
        return ret

    @transition(Vault.withdraw)
    def withdraw(
        self,
        amount: int,
    ) -> None:
        require(self.state.initialized)
        require(self.state.balance >= 1)
        require_arg(amount, Domain.range(1, self.state.balance + 1), preferred=[1])
        if not self.state.is_active:
            with raises(VaultInactiveException):
                self.inner_withdraw(amount)
            return None
        ret = self.inner_withdraw(amount)
        self.state.balance = self.state.balance - amount
        assert ret is None
        return ret

    @transition(Vault.set_active)
    def set_active(
        self,
        active: bool,
    ) -> None:
        require(self.state.initialized)
        require_arg(active, Domain.boolean())
        ret = self.inner_set_active(active)
        self.state.is_active = active
        assert ret is None
        return ret

    @transition(name="balance")
    def balance(self) -> int:
        require(self.state.initialized)
        ret = self.inner_balance()
        assert ret == self.state.balance
        return ret

    @transition(name="is_active")
    def is_active(self) -> bool:
        require(self.state.initialized)
        ret = self.inner_is_active()
        assert ret == self.state.is_active
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
        _ = self.fake.balance
        _ = self.fake.is_active
        self.fake.deposit(10)
        self.fake.withdraw(5)
        self.fake.set_active(True)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeVaultFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=VaultState,
    name="FakeVaultFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:40:16Z
# LAST_CHANGED: 2026-11-04T18:40:16Z
# CHANGE: Fixed feedback: withdraw argument domain now uses Domain.range(1, self.state.balance + 1) so the exclusive upper bound admits every valid amount from 1 through the modeled balance inclusive, including the full-balance withdraw(6) that decrements to zero and the balance==1 boundary case. The require(self.state.balance >= 1) gate still applies before the inactivity branch so no withdrawal is drawn at balance 0, keeping InsufficientFundsError unreachable during fuzzing.
# --- END AUTOFAB METADATA ---
