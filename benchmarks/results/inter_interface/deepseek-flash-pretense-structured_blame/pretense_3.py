# === File: inter_interface_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    Env,
    StateMachine,
    require,
    require_env,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from inter_interface_deepseek_flash_1.parts.inter_interface.lib.inter_interface import (
    AllocationLimitError,
    Allocator,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.lib.inter_interface_impl import (
    Allocator as AllocatorImpl,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.lib.vault import (
    Vault,
    VaultInactiveException,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.lib.vault_impl import (
    Vault as VaultImpl,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.pretense.inter_interface_pretense import (
    AllocatorState,
    AllocatorStateMachine,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.pretense.vault_pretense import (
    VaultState,
    VaultStateMachine,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.pretense.vault_impl_pretense import (
    VaultImplPseudoStateMachine,
)

# ==============================================================================
# 1. Implementation Pseudo State Machine (Allocator Implementation)
# ==============================================================================


class AllocatorImplPseudoStateMachine(AllocatorStateMachine):
    """Implementation pseudo-state machine binding the concrete Allocator SUT."""

    def __init__(
        self,
        state: Optional[AllocatorState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state, singletons=singletons)
        self.bind("vault_active", lambda: sut(Vault).is_active)

    def inner_allocated(self) -> int:
        target: Allocator = sut(Allocator)
        return target.allocated

    def inner_allocate(self, amount: int) -> None:
        target: Allocator = sut(Allocator)
        before_allocated = target.allocated
        target.allocate(amount)
        assert target.allocated == before_allocated + amount
        return None

    def inner_release(self, amount: int) -> None:
        target: Allocator = sut(Allocator)
        before_allocated = target.allocated
        target.release(amount)
        assert target.allocated == before_allocated - amount
        return None


proto = AllocatorImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests (Allocator Implementation)
# ==============================================================================


class TestAllocatorImplReal(LifecycleTestCase):
    """Verifies the concrete allocator implementation against the real vault."""

    target = AllocatorImpl

    def setUp(self) -> None:
        super().setUp()
        self.vault = VaultImpl()
        self.register_mock(self.vault, key=Vault, tier=system)
        self.vault_sm = VaultImplPseudoStateMachine(singletons={Vault: self.vault})
        self.vault_checked = self.vault_sm.as_checked(Vault, self.vault)
        self.allocator = self.sut
        self.sm = AllocatorImplPseudoStateMachine(
            state=AllocatorState(reserves=1000),
            singletons={Allocator: self.allocator, Vault: self.vault_checked},
        )
        self.checked = self.sm.as_checked(Allocator, self.allocator)

    def test_allocate_release_success(self) -> None:
        self.vault_checked.deposit(100)
        self.checked.allocate(30)
        self.checked.release(10)

    def test_allocated_property(self) -> None:
        assert self.checked.allocated == 0
        self.vault_checked.deposit(10)
        self.checked.allocate(5)
        assert self.checked.allocated == 5

    def test_allocate_invalid_amount(self) -> None:
        self.checked.violating(AllocationLimitError).allocate(0)

    def test_allocate_exceeds_reserves(self) -> None:
        self.vault_checked.deposit(5)
        self.checked.violating(AllocationLimitError).allocate(6)

    def test_release_invalid_amount(self) -> None:
        self.checked.violating(AllocationLimitError).release(0)

    def test_release_exceeds_allocated(self) -> None:
        self.vault_checked.deposit(10)
        self.checked.allocate(4)
        self.checked.violating(AllocationLimitError).release(5)

    def test_allocate_inactive_vault(self) -> None:
        self.vault_checked.deposit(5)
        self.vault_checked.set_active(False)
        with self.assertRaises(VaultInactiveException):
            self.checked.allocate(1)

    def test_release_inactive_vault(self) -> None:
        self.vault_checked.deposit(10)
        self.checked.allocate(4)
        self.vault_checked.set_active(False)
        with self.assertRaises(VaultInactiveException):
            self.checked.release(2)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real Implementation (Allocator Impl)
# ==============================================================================


def make_sut() -> Allocator:
    registry = LifecycleRegistry()
    registry.register_singleton(VaultImpl, keys=[Vault])
    registry.register_singleton(AllocatorImpl, keys=[Allocator])
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(Allocator)


AllocatorFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[VaultStateMachine],
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="AllocatorFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:04:11Z
# LAST_CHANGED: 2026-11-13T00:03:36Z
# CHANGE: Updated for the reserve-model change: the real test's AllocatorImplPseudoStateMachine is constructed with state=AllocatorState(reserves=1000) so the inherited allocate gate (Domain.integers(1, self.state.reserves)) is usable during fixed scenarios, while the real vault enforces the true reserve contract. Verified static checks.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:04:11Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:03:47Z
# --- END AUTOFAB METADATA ---


# === File: inter_interface_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
    Env,
    StateMachine,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from inter_interface_deepseek_flash_1.parts.inter_interface.lib.inter_interface import (
    AllocationLimitError,
    Allocator,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.lib.vault import (
    Vault,
    VaultInactiveException,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.pretense.vault_pretense import (
    VaultState,
    make_vault_fake,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Allocator Interface)
# ==============================================================================


@dataclass
class AllocatorState:
    """Model state tracking allocated funds and visible vault reserves."""

    allocated: int = 0
    reserves: int = 0
    vault_active: Env[bool] = True


class AllocatorStateMachine(StateMachine[AllocatorState]):
    """Pretense state machine modeling the Allocator interface 1:1."""

    def __init__(
        self,
        state: Optional[AllocatorState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> AllocatorState:
        """Constructs the blank initial model state."""
        return AllocatorState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the blank allocator model state with reserves before fuzzing."""
        self.state.allocated = 0
        self.state.reserves = 100

    @transition(name="allocated")
    def allocated(self) -> int:
        """Observes the cumulative amount of allocated funds."""
        ret = self.inner_allocated()
        assert ret == self.state.allocated
        return ret

    def inner_allocated(self) -> int:
        """Computes the fake allocation total strictly from model state."""
        return self.state.allocated

    @transition(Allocator.allocate)
    def allocate(self, amount: int) -> None:
        """Reserves a positive amount not exceeding the visible vault reserves."""
        require_arg(
            amount,
            Domain.integers(min_value=1, max_value=self.state.reserves),
            preferred=[1],
            error=AllocationLimitError,
        )
        require_env(self.state.vault_active, VaultInactiveException, amount)
        self.inner_allocate(amount)
        self.state.allocated += amount
        self.state.reserves -= amount
        assert sut(Allocator).allocated == self.state.allocated

    def inner_allocate(self, amount: int) -> None:
        """Computes the fake allocation outcome strictly from model state."""
        return None

    @transition(Allocator.release)
    def release(self, amount: int) -> None:
        """Releases a positive amount not exceeding the allocated funds."""
        require_arg(
            amount,
            Domain.in_set(range(1, self.state.allocated + 1)),
            preferred=[1],
            error=AllocationLimitError,
        )
        require_env(self.state.vault_active, VaultInactiveException, amount)
        self.inner_release(amount)
        self.state.allocated -= amount
        self.state.reserves += amount
        assert sut(Allocator).allocated == self.state.allocated

    def inner_release(self, amount: int) -> None:
        """Computes the fake release outcome strictly from model state."""
        return None


proto = AllocatorStateMachine()


# ==============================================================================
# 2. Synthesized Fake (Allocator Interface)
# ==============================================================================

FakeAllocator = synthesize_fake(AllocatorStateMachine)


def make_allocator_fake(
    state: Optional[AllocatorState] = None,
    vault: Optional[Vault] = None,
) -> Allocator:
    """Synthesizes a fake allocator with a fake vault collaborator."""
    collaborator = vault if vault is not None else make_vault_fake()
    return FakeAllocator(
        state=state or AllocatorState(reserves=100),
        singletons={Vault: collaborator},
    )


# Fake fuzzing exercises the synthesized fake against the model contracts.
FakeAllocatorFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeAllocatorFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Allocator Interface)
# ==============================================================================


class TestAllocatorFake(unittest.TestCase):
    """Verifies the synthesized fake satisfies every declared transition."""

    def setUp(self) -> None:
        self.vault_fake = make_vault_fake(VaultState(balance=100))
        self.fake = make_allocator_fake(vault=self.vault_fake)
        self.sm = AllocatorStateMachine(singletons={Vault: self.vault_fake})

    def test_transitions_coverage(self) -> None:
        self.sm.seed_initial()
        assert self.fake.allocated == 0
        self.fake.allocate(10)
        assert self.fake.allocated == 10
        self.fake.release(4)
        assert self.fake.allocated == 6
        self.fake.allocate(1)
        assert self.fake.allocated == 7

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:03:29Z
# LAST_CHANGED: 2026-11-13T00:03:29Z
# CHANGE: Resolved [from:pretense_qa] collaborator model dependency outside dispatch context (PretenseError from sut_state(VaultState) in the allocate domain): removed sut_state from the domain and modeled visible vault reserves on AllocatorState.reserves instead. allocate now gates with Domain.integers(min_value=1, max_value=self.state.reserves) and decrements reserves; release restores reserves. seed_initial and the fake factory seed positive reserves (100) so the lazy interval is never degenerate during fuzzing. Verified static checks and fake fuzzing.
# --- END AUTOFAB METADATA ---


# === File: vault_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    Env,
    StateMachine,
    require,
    require_env,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from inter_interface_deepseek_flash_1.parts.inter_interface.lib.vault import (
    InsufficientFundsError,
    Vault,
    VaultInactiveException,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.lib.vault_impl import (
    Vault as VaultImpl,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.pretense.vault_pretense import (
    VaultState,
    VaultStateMachine,
)

# ==============================================================================
# 1. Implementation Pseudo State Machine (Vault Implementation)
# ==============================================================================


class VaultImplPseudoStateMachine(VaultStateMachine):
    """Implementation pseudo-state machine binding the concrete Vault SUT."""

    def __init__(
        self,
        state: Optional[VaultState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state, singletons=singletons)
        self.bind("is_active", lambda: sut(Vault).is_active)

    def inner_balance(self) -> int:
        target: Vault = sut(Vault)
        return target.balance

    def inner_is_active(self) -> bool:
        target: Vault = sut(Vault)
        return target.is_active

    def inner_deposit(self, amount: int) -> None:
        target: Vault = sut(Vault)
        before = target.balance
        target.deposit(amount)
        assert target.balance == before + amount
        return None

    def inner_withdraw(self, amount: int) -> None:
        target: Vault = sut(Vault)
        before = target.balance
        target.withdraw(amount)
        assert target.balance == before - amount
        return None

    def inner_set_active(self, active: bool) -> None:
        target: Vault = sut(Vault)
        target.set_active(active)
        return None


proto = VaultImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests (Vault Implementation)
# ==============================================================================


class TestVaultImplReal(LifecycleTestCase):
    """Verifies the concrete vault implementation satisfies every contract."""

    target = VaultImpl

    def setUp(self) -> None:
        super().setUp()
        self.real = self.sut
        self.sm = VaultImplPseudoStateMachine(singletons={Vault: self.real})
        self.checked = self.sm.as_checked(Vault, self.real)

    def test_deposit_withdraw_success(self) -> None:
        self.checked.deposit(10)
        self.checked.withdraw(4)

    def test_balance_and_active_properties(self) -> None:
        self.checked.set_active(False)
        assert self.checked.is_active is False
        self.checked.set_active(True)
        assert self.checked.is_active is True
        assert self.checked.balance == 0

    def test_deposit_invalid_amount(self) -> None:
        self.checked.violating(InsufficientFundsError).deposit(0)

    def test_withdraw_invalid_amount(self) -> None:
        self.checked.violating(InsufficientFundsError).withdraw(0)

    def test_withdraw_exceeds_balance(self) -> None:
        self.checked.deposit(3)
        self.checked.violating(InsufficientFundsError).withdraw(4)

    def test_deposit_inactive(self) -> None:
        self.checked.set_active(False)
        with self.assertRaises(VaultInactiveException):
            self.checked.deposit(1)

    def test_withdraw_inactive(self) -> None:
        self.checked.deposit(5)
        self.checked.set_active(False)
        with self.assertRaises(VaultInactiveException):
            self.checked.withdraw(1)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real Implementation (Vault Implementation)
# ==============================================================================


def make_sut() -> Vault:
    registry = LifecycleRegistry()
    registry.register_singleton(VaultImpl, keys=[Vault])
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(Vault)


VaultFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="VaultFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:04:13Z
# LAST_CHANGED: 2026-11-12T23:47:28Z
# CHANGE: Resolved [from:pretense_qa] vault.withdraw.inactive_vault precondition overlap: test_withdraw_inactive now funds the vault (deposit 5) before deactivating, so the withdrawal amount is valid and only the inactive-vault postcondition can fire, yielding VaultInactiveException instead of the overlapping InsufficientFundsError. Verified static checks.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:04:13Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:03:50Z
# --- END AUTOFAB METADATA ---


# === File: vault_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
    Env,
    StateMachine,
    require,
    require_arg,
    require_env,
    sut,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from inter_interface_deepseek_flash_1.parts.inter_interface.lib.vault import (
    InsufficientFundsError,
    Vault,
    VaultInactiveException,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Vault Interface)
# ==============================================================================


@dataclass
class VaultState:
    """Model state tracking the vault balance and availability."""

    balance: int = 0
    is_active: Env[bool] = True


class VaultStateMachine(StateMachine[VaultState]):
    """Pretense state machine modeling the Vault interface 1:1."""

    def __init__(
        self,
        state: Optional[VaultState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> VaultState:
        """Constructs the blank initial model state."""
        return VaultState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the blank vault model state with positive reserves before fuzzing."""
        self.state.balance = 100

    @transition(name="balance")
    def balance(self) -> int:
        """Observes the current vault balance."""
        ret = self.inner_balance()
        assert ret == self.state.balance
        return ret

    def inner_balance(self) -> int:
        """Computes the fake balance strictly from model state."""
        return self.state.balance

    @transition(name="is_active")
    def is_active(self) -> bool:
        """Observes whether the vault is currently active."""
        ret = self.inner_is_active()
        assert ret == self.state.is_active
        return ret

    def inner_is_active(self) -> bool:
        """Computes the fake availability strictly from model state."""
        return self.state.is_active

    @transition(Vault.deposit)
    def deposit(self, amount: int) -> None:
        """Deposits a positive amount into the active vault."""
        require_arg(
            amount,
            Domain.integers(min_value=1),
            preferred=[1, 10],
            error=InsufficientFundsError,
        )
        require_env(self.state.is_active, VaultInactiveException, amount)
        self.inner_deposit(amount)
        self.state.balance += amount
        assert sut(Vault).balance == self.state.balance

    def inner_deposit(self, amount: int) -> None:
        """Computes the fake deposit outcome strictly from model state."""
        return None

    @transition(Vault.withdraw)
    def withdraw(self, amount: int) -> None:
        """Withdraws a positive amount not exceeding the current balance."""
        require_arg(
            amount,
            Domain.integers(min_value=1, max_value=self.state.balance),
            preferred=[1],
            error=InsufficientFundsError,
        )
        require_env(self.state.is_active, VaultInactiveException, amount)
        self.inner_withdraw(amount)
        self.state.balance -= amount
        assert sut(Vault).balance == self.state.balance

    def inner_withdraw(self, amount: int) -> None:
        """Computes the fake withdrawal outcome strictly from model state."""
        return None

    @transition(Vault.set_active)
    def set_active(self, active: bool) -> None:
        """Toggles vault availability through the test-only hook."""
        require_arg(active, Domain.sampled_from([True, False]), preferred=[True])
        self.inner_set_active(active)
        self.state.is_active = active
        assert sut(Vault).is_active == active

    def inner_set_active(self, active: bool) -> None:
        """Computes the fake availability update strictly from model state."""
        return None


proto = VaultStateMachine()


# ==============================================================================
# 2. Synthesized Fake (Vault Interface)
# ==============================================================================

FakeVault = synthesize_fake(VaultStateMachine)


def make_vault_fake(state: Optional[VaultState] = None) -> Vault:
    """Synthesizes a fake vault sharing the model state."""
    return FakeVault(state=state or VaultState())


# Fake fuzzing exercises the synthesized fake against the model contracts.
FakeVaultFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeVaultFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Vault Interface)
# ==============================================================================


class TestVaultFake(unittest.TestCase):
    """Verifies the synthesized fake satisfies every declared transition."""

    def setUp(self) -> None:
        self.fake = make_vault_fake()
        self.sm = VaultStateMachine(singletons={Vault: self.fake})

    def test_transitions_coverage(self) -> None:
        self.sm.seed_initial()
        assert self.fake.balance == 0
        assert self.fake.is_active is True
        self.fake.deposit(10)
        assert self.fake.balance == 10
        self.fake.withdraw(4)
        assert self.fake.balance == 6
        self.fake.set_active(False)
        assert self.fake.is_active is False
        self.fake.set_active(True)
        assert self.fake.is_active is True

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:00:42Z
# LAST_CHANGED: 2026-11-13T00:00:42Z
# CHANGE: Resolved [from:pretense_qa] unbounded balance range materialization (in_set(range(1,balance+1)) timed out): replaced the materialized set with a lazy Domain.integers(min_value=1, max_value=self.state.balance) interval, which enforces the exact 1..balance contract without enumerating, and still raises InsufficientFundsError for non-positive or over-balance amounts (including the empty domain at zero balance on concrete calls). Also seeded seed_initial with positive reserves so fuzz generation never constructs an empty withdraw domain. Verified static checks and fake fuzzing.
# --- END AUTOFAB METADATA ---
