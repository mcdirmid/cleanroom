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
from support.lib.lifecycle import (
    LifecycleRegistry,
    enter_phase,
    get_singleton,
    system,
)
from benchmark_5.parts.inter_interface.pretense.inter_interface_pretense import (
    FakeInterInterface,
    InterInterfaceState,
    InterInterfaceStateMachine,
    make_inter_interface_fake,
)
from benchmark_5.parts.inter_interface.pretense.vault_pretense import (
    FakeVault,
    VaultState,
    VaultStateMachine,
    make_vault_fake,
)
from benchmark_5.parts.inter_interface.lib import vault as vault_interface
from benchmark_5.parts.inter_interface.lib.vault import VaultInactiveException
from benchmark_5.parts.inter_interface.lib.inter_interface_impl import Allocator
from benchmark_5.parts.inter_interface.lib.vault_impl import Vault
from benchmark_5.parts.inter_interface.lib.inter_interface_impl import (
    __initialize__ as _ii_initialize,
)
from benchmark_5.parts.inter_interface.lib.vault_impl import (
    __initialize__ as _v_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class InterInterfaceImplPseudoStateMachine(InterInterfaceStateMachine):
    """Implementation pseudo-state machine for Allocator."""

    @transition(Allocator.allocate)
    def allocate(self, amount: int) -> Any:
        target: Allocator = sut(Allocator)
        reserves: vault_interface.Vault = sut(vault_interface.Vault)
        if reserves.is_active:
            old_allocated = target.allocated
            ret = call_target(target.allocate(amount))
            # POSTCONDITION: a successful allocation increments the allocated total.
            assert target.allocated == old_allocated + amount
            return ret
        # POSTCONDITION: an inactive collaborator vault raises VaultInactiveException.
        with raises(VaultInactiveException):
            call_target(target.allocate(amount))
        return None

    @transition(Allocator.release)
    def release(self, amount: int) -> Any:
        target: Allocator = sut(Allocator)
        reserves: vault_interface.Vault = sut(vault_interface.Vault)
        if reserves.is_active:
            old_allocated = target.allocated
            ret = call_target(target.release(amount))
            # POSTCONDITION: a successful release decrements the allocated total.
            assert target.allocated == old_allocated - amount
            return ret
        # POSTCONDITION: an inactive collaborator vault raises VaultInactiveException.
        with raises(VaultInactiveException):
            call_target(target.release(amount))
        return None

    @transition(name="allocated")
    def allocated(self) -> Any:
        target: Allocator = sut(Allocator)
        ret = call_target(getattr(target, "allocated"))
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
        self.vault_fake = make_vault_fake()
        self.sm = InterInterfaceImplPseudoStateMachine(
            singletons={
                Allocator: self.real,
                Vault: self.vault,
                vault_interface.Vault: self.vault_fake,
            }
        )
        self.checked = self.sm.as_checked(Allocator, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        # Seed the collaborator vault with reserves.
        self.vault.deposit(100)
        # A successful allocation reserves funds out of the vault.
        self.checked.allocate(30)
        assert self.checked.allocated == 30
        assert self.vault.balance == 70
        # A successful release returns funds to the vault.
        self.checked.release(10)
        assert self.checked.allocated == 20
        assert self.vault.balance == 80
        # An inactive collaborator vault rejects allocations and releases.
        self.vault.set_active(False)
        with self.assertRaises(VaultInactiveException):
            self.checked.allocate(10)
        with self.assertRaises(VaultInactiveException):
            self.checked.release(5)
        assert self.checked.allocated == 20
        # Re-activating the vault restores normal operation.
        self.vault.set_active(True)
        self.checked.allocate(10)
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
# LAST_CLEANED: 2026-11-04T20:53:21Z
# LAST_CHANGED: 2026-11-04T20:53:21Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 21f8076aeec9
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T20:53:21Z
# PRETENSE_QA_AUDIT: 2026-11-04T20:53:21Z
# --- END AUTOFAB METADATA ---


# === File: inter_interface_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for Allocator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import unittest

from pretense import (
    Domain,
    PretenseError,
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
from benchmark_5.parts.inter_interface.lib.inter_interface import Allocator
from benchmark_5.parts.inter_interface.lib.vault import VaultInactiveException
from benchmark_5.parts.inter_interface.pretense.vault_pretense import VaultState


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================


@dataclass
class InterInterfaceState:
    """Canonical model state for Allocator operations."""

    allocated: int = 0


def _available_reserves() -> int:
    """Returns the collaborator vault reserve bound for allocation inputs."""
    try:
        return sut_state(VaultState).balance
    except PretenseError:
        return 1000


class InterInterfaceStateMachine(StateMachine[InterInterfaceState]):
    """Unified Pretense State Machine for Allocator."""

    def __init__(
        self,
        state: Optional[InterInterfaceState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or InterInterfaceState(), singletons=singletons)

    @transition(Allocator.allocate)
    def allocate(self, amount: int) -> None:
        # PRECONDITION: positive allocation amount that fits within the collaborator reserves.
        require_arg(
            amount,
            Domain.range(1, _available_reserves() + 1),
            preferred=[10],
        )
        ret = make_return_value()
        # POSTCONDITION: a successful allocation increments the allocated total by amount.
        self.state.allocated += amount
        assert self.state.allocated >= amount
        return ret

    @transition(Allocator.release)
    def release(self, amount: int) -> None:
        # PRECONDITION: positive release amount that does not exceed the allocated total.
        require(self.state.allocated > 0)
        require_arg(
            amount,
            Domain.range(1, self.state.allocated + 1),
            preferred=[1],
        )
        ret = make_return_value()
        # POSTCONDITION: a successful release decrements the allocated total by amount.
        self.state.allocated -= amount
        assert self.state.allocated >= 0
        return ret

    @transition(name="allocated")
    def allocated(self) -> int:
        # POSTCONDITION: the current modelled allocation total is exposed.
        ret = make_return_value(self.state.allocated)
        assert ret == self.state.allocated
        return ret


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
    """Verifies that the synthesized fake satisfies all transitions."""

    def setUp(self) -> None:
        self.fake = make_inter_interface_fake()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions on the fake double."""
        self.fake.allocate(10)
        assert self.fake.allocated == 10
        self.fake.release(4)
        assert self.fake.allocated == 6


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeInterInterfaceFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=InterInterfaceState,
    name="FakeInterInterfaceFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:53:21Z
# LAST_CHANGED: 2026-11-04T20:53:21Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: b28046dc3bc0
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T20:53:21Z
# PRETENSE_QA_AUDIT: 2026-11-04T20:53:21Z
# --- END AUTOFAB METADATA ---


# === File: vault_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for Vault."""

from __future__ import annotations

from typing import Any, Optional

import unittest

from pretense import (
    call_target,
    sut,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    enter_phase,
    get_singleton,
    system,
)
from benchmark_5.parts.inter_interface.pretense.vault_pretense import (
    VaultState,
    VaultStateMachine,
)
from benchmark_5.parts.inter_interface.lib.vault import VaultInactiveException
from benchmark_5.parts.inter_interface.lib.vault_impl import Vault
from benchmark_5.parts.inter_interface.lib.inter_interface_impl import (
    __initialize__ as _ii_initialize,
)
from benchmark_5.parts.inter_interface.lib.vault_impl import (
    __initialize__ as _v_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class VaultImplPseudoStateMachine(VaultStateMachine):
    """Implementation pseudo-state machine for Vault."""

    @transition(Vault.deposit)
    def deposit(self, amount: int) -> Any:
        target: Vault = sut(Vault)
        old_balance = target.balance
        ret = call_target(target.deposit(amount))
        # POSTCONDITION: an active vault increments the balance by amount.
        assert target.balance == old_balance + amount
        return ret

    @transition(Vault.withdraw)
    def withdraw(self, amount: int) -> Any:
        target: Vault = sut(Vault)
        old_balance = target.balance
        ret = call_target(target.withdraw(amount))
        # POSTCONDITION: an active vault decrements the balance by amount.
        assert target.balance == old_balance - amount
        return ret

    @transition(Vault.set_active)
    def set_active(self, active: bool) -> Any:
        target: Vault = sut(Vault)
        ret = call_target(target.set_active(active))
        # POSTCONDITION: the availability flag is updated to the requested value.
        assert target.is_active == active
        return ret

    @transition(name="balance")
    def balance(self) -> Any:
        target: Vault = sut(Vault)
        ret = call_target(getattr(target, "balance"))
        return ret

    @transition(name="is_active")
    def is_active(self) -> Any:
        target: Vault = sut(Vault)
        ret = call_target(getattr(target, "is_active"))
        return ret


proto = VaultImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================


class TestVaultImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

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
        # A blank vault starts empty and active.
        assert self.checked.balance == 0
        assert self.checked.is_active is True
        # Depositing on an active vault increases the balance.
        self.checked.deposit(100)
        assert self.checked.balance == 100
        # Withdrawing on an active vault decreases the balance.
        self.checked.withdraw(40)
        assert self.checked.balance == 60
        # An inactive vault rejects deposits and withdrawals.
        self.checked.set_active(False)
        assert self.checked.is_active is False
        with self.assertRaises(VaultInactiveException):
            self.checked.deposit(10)
        with self.assertRaises(VaultInactiveException):
            self.checked.withdraw(10)
        # Re-activating the vault restores normal operation.
        self.checked.set_active(True)
        assert self.checked.is_active is True
        self.checked.deposit(5)
        assert self.checked.balance == 65


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================


def make_sut() -> Vault:
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
# LAST_CLEANED: 2026-11-04T20:53:21Z
# LAST_CHANGED: 2026-11-04T20:53:21Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 0ad903e36649
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T20:53:21Z
# PRETENSE_QA_AUDIT: 2026-11-04T20:53:21Z
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
from benchmark_5.parts.inter_interface.lib.vault import Vault, VaultInactiveException


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
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
        # PRECONDITION: positive deposit amount; non-positive is a caller contract violation.
        require_arg(amount, Domain.range(1, 1000), preferred=[10])
        if not self.state.is_active:
            # POSTCONDITION: an inactive vault raises VaultInactiveException.
            with raises(VaultInactiveException):
                make_return_value()
                raise VaultInactiveException("Vault is inactive")
            return None
        ret = make_return_value()
        # POSTCONDITION: an active vault increments the balance by amount.
        self.state.balance += amount
        assert self.state.balance >= amount
        return ret

    @transition(Vault.withdraw)
    def withdraw(self, amount: int) -> None:
        # PRECONDITION: positive amount that does not exceed the current balance.
        require(self.state.balance > 0)
        require_arg(amount, Domain.range(1, self.state.balance + 1), preferred=[1])
        if not self.state.is_active:
            # POSTCONDITION: an inactive vault raises VaultInactiveException.
            with raises(VaultInactiveException):
                make_return_value()
                raise VaultInactiveException("Vault is inactive")
            return None
        ret = make_return_value()
        # POSTCONDITION: an active vault decrements the balance by amount.
        self.state.balance -= amount
        assert self.state.balance >= 0
        return ret

    @transition(Vault.set_active)
    def set_active(self, active: bool) -> None:
        require_arg(active, Domain.boolean())
        ret = make_return_value()
        # POSTCONDITION: the availability flag is updated to the requested value.
        self.state.is_active = active
        assert self.state.is_active == active
        return ret

    @transition(name="balance")
    def balance(self) -> int:
        # POSTCONDITION: the current modelled balance is exposed.
        ret = make_return_value(self.state.balance)
        assert ret == self.state.balance
        return ret

    @transition(name="is_active")
    def is_active(self) -> bool:
        # POSTCONDITION: the current modelled availability flag is exposed.
        ret = make_return_value(self.state.is_active)
        assert ret == self.state.is_active
        return ret


proto = VaultStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeVault = synthesize_fake(VaultStateMachine)


def make_vault_fake(state: Optional[VaultState] = None) -> Vault:
    """Synthesizes fake instance for Vault."""
    return FakeVault(state=state or VaultState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestVaultFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions."""

    def setUp(self) -> None:
        self.fake = make_vault_fake()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions on the fake double."""
        self.fake.deposit(10)
        assert self.fake.balance == 10
        assert self.fake.is_active is True
        self.fake.withdraw(4)
        assert self.fake.balance == 6
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
# LAST_CLEANED: 2026-11-04T20:53:21Z
# LAST_CHANGED: 2026-11-04T20:53:21Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: b12537ac1ad5
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T20:53:21Z
# PRETENSE_QA_AUDIT: 2026-11-04T20:53:21Z
# --- END AUTOFAB METADATA ---
