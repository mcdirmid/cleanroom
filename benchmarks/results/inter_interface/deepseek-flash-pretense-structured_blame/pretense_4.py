# === File: inter_interface_impl_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Set, Tuple
import unittest

from pretense import (
    sut,
    sut_state,
)
from support.lib.lifecycle import LifecycleTestCase

from inter_interface_deepseek_flash_1.parts.inter_interface.lib.inter_interface import (
    AllocationLimitError,
    Allocator,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.lib.inter_interface_impl import (
    Allocator as AllocatorImpl,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.lib.vault import (
    VaultInactiveException,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.lib.vault_impl import (
    Vault as VaultImpl,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.pretense.inter_interface_pretense import (
    AllocatorState,
    AllocatorStateMachine,
)

# Funds deposited into the collaborator vault by the real test harness before
# each scenario; the model initial reserves must stay in sync with this fixture.
INITIAL_RESERVES = 100

# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class AllocatorImplPseudoStateMachine(AllocatorStateMachine):
    """Implementation pseudo-state machine binding the concrete allocator SUT.

    Domain constraints and model state mutations are inherited from
    ``AllocatorStateMachine``; only the inner transitions are overridden so that
    preconditions and environment guards stay active.
    """

    def __init__(
        self,
        state: Optional[AllocatorState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state, singletons=singletons)
        self.bind("vault_active", lambda: sut(VaultImpl).is_active)

    @property
    def initial_reserves(self) -> int:
        """The harness pre-funds the real vault with the same starting reserves."""
        return INITIAL_RESERVES

    def inner_allocated(self) -> int:
        target = sut(AllocatorImpl)
        ret = target.allocated
        assert ret == self.state.allocated
        return ret

    def inner_allocate(self, amount: int) -> None:
        target = sut(AllocatorImpl)
        vault = sut(VaultImpl)
        old_allocated = target.allocated
        old_reserves = vault.balance
        target.allocate(amount)
        assert target.allocated == old_allocated + amount
        assert vault.balance == old_reserves - amount

    def inner_release(self, amount: int) -> None:
        target = sut(AllocatorImpl)
        vault = sut(VaultImpl)
        old_allocated = target.allocated
        old_reserves = vault.balance
        target.release(amount)
        assert target.allocated == old_allocated - amount
        assert vault.balance == old_reserves + amount


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestAllocatorImplReal(LifecycleTestCase):
    """Verifies that the concrete allocator implementation satisfies its contracts."""

    target = AllocatorImpl

    def setUp(self) -> None:
        super().setUp()
        self.real = self.sut
        self.vault = self.get_singleton(VaultImpl)
        self.vault.deposit(INITIAL_RESERVES)
        self.sm = AllocatorImplPseudoStateMachine(
            singletons={AllocatorImpl: self.real, VaultImpl: self.vault}
        )
        self.checked = self.sm.as_checked(Allocator, self.real)

    def test_allocate_and_release(self) -> None:
        self.checked.allocate(30)
        self.checked.allocate(10)
        assert self.checked.allocated == 40
        self.checked.release(15)
        assert self.checked.allocated == 25

    def test_allocate_when_vault_inactive(self) -> None:
        self.vault.set_active(False)
        with self.assertRaises(VaultInactiveException):
            self.checked.allocate(10)

    def test_release_when_vault_inactive(self) -> None:
        self.checked.allocate(10)
        self.vault.set_active(False)
        with self.assertRaises(VaultInactiveException):
            self.checked.release(5)

    def test_allocate_invalid_amount(self) -> None:
        self.checked.violating(AllocationLimitError).allocate(0)

    def test_allocate_exceeding_reserves(self) -> None:
        self.checked.violating(AllocationLimitError).allocate(INITIAL_RESERVES + 1)

    def test_release_invalid_amount(self) -> None:
        self.checked.allocate(10)
        self.checked.violating(AllocationLimitError).release(0)

    def test_release_exceeding_allocated(self) -> None:
        self.checked.allocate(10)
        self.checked.violating(AllocationLimitError).release(11)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:11:54Z
# LAST_CHANGED: 2026-11-13T00:11:31Z
# CHANGE: Initial allocator implementation pretense: AllocatorImplPseudoStateMachine overriding inner_allocated/inner_allocate/inner_release to drive the concrete Allocator singleton while asserting collaborator vault balance deltas, binds vault_active Env to the real vault availability, and TestAllocatorImplReal covers allocate/release flows, inactive-vault VaultInactiveException paths, and violating() AllocationLimitError scenarios.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:11:54Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:11:51Z
# --- END AUTOFAB METADATA ---


# === File: inter_interface_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from inter_interface_deepseek_flash_1.parts.inter_interface.lib.inter_interface import (
    AllocationLimitError,
    Allocator,
)
from inter_interface_deepseek_flash_1.parts.inter_interface.lib.vault import (
    VaultInactiveException,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class AllocatorState:
    """Canonical model state for a resource allocator.

    ``allocated`` tracks cumulative reservations, ``reserves`` models the
    abstract funds still held in the collaborator vault, and ``vault_active``
    is the virtual environment condition for collaborator availability.
    """

    allocated: int = 0
    reserves: int = 0
    vault_active: Env[bool] = True


class AllocatorStateMachine(StateMachine[AllocatorState]):
    """Unified pretense state machine for the resource allocator interface."""

    def __init__(
        self,
        state: Optional[AllocatorState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    @property
    def initial_reserves(self) -> int:
        """Overridable default for the funds available in the collaborator vault."""
        return 100

    def make_initial_state(self) -> AllocatorState:
        """Constructs initial model state: nothing allocated and a funded vault."""
        return AllocatorState(reserves=self.initial_reserves)

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds a blank allocator with a funded, active collaborator vault."""
        self.state.allocated = 0
        self.state.reserves = self.initial_reserves
        self.state.vault_active = True

    @transition(name="allocated")
    def allocated(self) -> int:
        """Observes the cumulative amount of allocated funds."""
        ret = self.inner_allocated()
        assert ret >= 0
        assert ret == self.state.allocated
        return ret

    def inner_allocated(self) -> int:
        """Computes the fake allocation total strictly from model state."""
        return self.state.allocated

    @transition(Allocator.allocate)
    def allocate(self, amount: int) -> None:
        """Allocates a strictly positive amount covered by vault reserves."""
        require(self.state.reserves >= 1)
        require_arg(
            amount,
            Domain.integers(min_value=1, max_value=self.state.reserves),
            preferred=[1, 10],
            error=AllocationLimitError,
        )
        require_env(self.state.vault_active, VaultInactiveException)
        old_allocated = self.state.allocated
        old_reserves = self.state.reserves
        self.inner_allocate(amount)
        self.state.allocated = old_allocated + amount
        self.state.reserves = old_reserves - amount
        assert self.state.allocated > old_allocated
        assert self.state.reserves < old_reserves

    def inner_allocate(self, amount: int) -> None:
        """Computes the fake allocation result (no return value)."""
        return None

    @transition(Allocator.release)
    def release(self, amount: int) -> None:
        """Releases a strictly positive amount no greater than allocated funds."""
        require(self.state.allocated >= 1)
        require_arg(
            amount,
            Domain.integers(min_value=1, max_value=self.state.allocated),
            preferred=[1],
            error=AllocationLimitError,
        )
        require_env(self.state.vault_active, VaultInactiveException)
        old_allocated = self.state.allocated
        old_reserves = self.state.reserves
        self.inner_release(amount)
        self.state.allocated = old_allocated - amount
        self.state.reserves = old_reserves + amount
        assert self.state.allocated < old_allocated
        assert self.state.allocated >= 0
        assert self.state.reserves > old_reserves

    def inner_release(self, amount: int) -> None:
        """Computes the fake release result (no return value)."""
        return None


proto = AllocatorStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeAllocator = synthesize_fake(AllocatorStateMachine)


def make_allocator_fake(state: Optional[AllocatorState] = None) -> Allocator:
    """Synthesizes a fake allocator instance for the given model state."""
    return FakeAllocator(state=state or proto.make_initial_state())


FakeAllocatorFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeAllocatorFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestAllocatorFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all allocator transitions."""

    def setUp(self) -> None:
        self.fake = make_allocator_fake()
        self.sm = AllocatorStateMachine(singletons={Allocator: self.fake})

    def test_transitions_coverage(self) -> None:
        """Exercises every declared transition and seeding transition on the fake."""
        self.sm.seed_initial()
        self.fake.allocate(30)
        self.fake.allocate(10)
        assert self.fake.allocated == 40
        self.fake.release(15)
        assert self.fake.allocated == 25

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:11:27Z
# LAST_CHANGED: 2026-11-13T00:11:27Z
# CHANGE: Initial allocator interface pretense: AllocatorState with allocated/reserves plus Env[bool] vault availability, 1:1 transitions for allocated/allocate/release with dynamic reserve and allocation domains, seeding transition, synthesized FakeAllocator, TestAllocatorFake coverage, and FakeAllocatorFuzzTest hypothesis fuzzing.
# --- END AUTOFAB METADATA ---


# === File: vault_impl_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Set, Tuple
import unittest

from pretense import (
    Env,
    StateMachine,
    require,
    require_env,
    sut,
    sut_state,
)
from support.lib.lifecycle import LifecycleTestCase

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
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class VaultImplPseudoStateMachine(VaultStateMachine):
    """Implementation pseudo-state machine binding the concrete vault SUT.

    Domain constraints and model state mutations are inherited from
    ``VaultStateMachine``; only the inner transitions are overridden so that
    preconditions and environment guards stay active.
    """

    def __init__(
        self,
        state: Optional[VaultState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state, singletons=singletons)
        self.bind("active", lambda: sut(VaultImpl).is_active)

    def inner_balance(self) -> int:
        target = sut(VaultImpl)
        ret = target.balance
        assert ret == self.state.balance
        return ret

    def inner_is_active(self) -> bool:
        target = sut(VaultImpl)
        ret = target.is_active
        assert ret == bool(self.state.active)
        return ret

    def inner_deposit(self, amount: int) -> None:
        target = sut(VaultImpl)
        old_balance = target.balance
        target.deposit(amount)
        assert target.balance == old_balance + amount

    def inner_withdraw(self, amount: int) -> None:
        target = sut(VaultImpl)
        old_balance = target.balance
        target.withdraw(amount)
        assert target.balance == old_balance - amount

    def inner_set_active(self, active: bool) -> None:
        target = sut(VaultImpl)
        target.set_active(active)
        assert target.is_active is active


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestVaultImplReal(LifecycleTestCase):
    """Verifies that the concrete vault implementation satisfies its contracts."""

    target = VaultImpl

    def setUp(self) -> None:
        super().setUp()
        self.real = self.sut
        self.sm = VaultImplPseudoStateMachine(singletons={VaultImpl: self.real})
        self.checked = self.sm.as_checked(Vault, self.real)

    def test_deposit_and_withdraw(self) -> None:
        self.checked.deposit(10)
        self.checked.deposit(5)
        self.checked.withdraw(4)
        assert self.checked.balance == 11
        assert self.checked.is_active is True

    def test_set_active(self) -> None:
        self.checked.set_active(False)
        assert self.checked.is_active is False
        self.checked.set_active(True)
        assert self.checked.is_active is True

    def test_deposit_when_inactive(self) -> None:
        self.checked.set_active(False)
        with self.assertRaises(VaultInactiveException):
            self.checked.deposit(5)

    def test_withdraw_when_inactive(self) -> None:
        self.checked.deposit(5)
        self.checked.set_active(False)
        with self.assertRaises(VaultInactiveException):
            self.checked.withdraw(2)

    def test_deposit_invalid_amount(self) -> None:
        self.checked.violating(InsufficientFundsError).deposit(0)

    def test_withdraw_invalid_amount(self) -> None:
        self.checked.deposit(5)
        self.checked.violating(InsufficientFundsError).withdraw(0)

    def test_withdraw_exceeding_balance(self) -> None:
        self.checked.deposit(5)
        self.checked.violating(InsufficientFundsError).withdraw(6)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:11:57Z
# LAST_CHANGED: 2026-11-13T00:10:28Z
# CHANGE: Initial vault implementation pretense: VaultImplPseudoStateMachine overriding inner_balance/inner_is_active/inner_deposit/inner_withdraw/inner_set_active to drive the concrete Vault singleton, binds the active Env field to the real vault availability, and TestVaultImplReal scenarios cover deposit/withdraw flow, inactive *Exception paths, and violating() scenarios for InsufficientFundsError.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:11:57Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:10:46Z
# --- END AUTOFAB METADATA ---


# === File: vault_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from inter_interface_deepseek_flash_1.parts.inter_interface.lib.vault import (
    InsufficientFundsError,
    Vault,
    VaultInactiveException,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class VaultState:
    """Canonical model state for a bounded asset vault.

    ``balance`` tracks the abstract asset count and ``active`` is the virtual
    environment condition describing whether the vault service is operational.
    """

    balance: int = 0
    active: Env[bool] = True


class VaultStateMachine(StateMachine[VaultState]):
    """Unified pretense state machine for the resource vault interface."""

    def __init__(
        self,
        state: Optional[VaultState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> VaultState:
        """Constructs initial model state: an empty but active vault."""
        return VaultState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds a blank vault so fuzzing can start from a known state."""
        self.state.balance = 0
        self.state.active = True

    @transition(name="balance")
    def balance(self) -> int:
        """Observes the current asset balance."""
        ret = self.inner_balance()
        assert ret >= 0
        assert ret == self.state.balance
        return ret

    def inner_balance(self) -> int:
        """Computes the fake balance strictly from model state."""
        return self.state.balance

    @transition(name="is_active")
    def is_active(self) -> bool:
        """Observes whether the vault service is currently operational."""
        ret = self.inner_is_active()
        assert ret == bool(self.state.active)
        return ret

    def inner_is_active(self) -> bool:
        """Computes the fake availability strictly from model state."""
        return bool(self.state.active)

    @transition(Vault.deposit)
    def deposit(self, amount: int) -> None:
        """Deposits a strictly positive amount into the vault."""
        require_arg(amount, Domain.integers(min_value=1), preferred=[1, 10], error=InsufficientFundsError)
        require_env(self.state.active, VaultInactiveException)
        old_balance = self.state.balance
        self.inner_deposit(amount)
        self.state.balance = old_balance + amount
        assert self.state.balance > old_balance

    def inner_deposit(self, amount: int) -> None:
        """Computes the fake deposit result (no return value)."""
        return None

    @transition(Vault.withdraw)
    def withdraw(self, amount: int) -> None:
        """Withdraws a strictly positive amount no greater than the balance."""
        require(self.state.balance >= 1)
        require_arg(
            amount,
            Domain.integers(min_value=1, max_value=self.state.balance),
            preferred=[1],
            error=InsufficientFundsError,
        )
        require_env(self.state.active, VaultInactiveException)
        old_balance = self.state.balance
        self.inner_withdraw(amount)
        self.state.balance = old_balance - amount
        assert self.state.balance < old_balance
        assert self.state.balance >= 0

    def inner_withdraw(self, amount: int) -> None:
        """Computes the fake withdrawal result (no return value)."""
        return None

    @transition(Vault.set_active)
    def set_active(self, active: bool) -> None:
        """Test-only hook toggling vault availability."""
        require_arg(active, Domain.sampled_from([True, False]), preferred=[True])
        self.inner_set_active(active)
        self.state.active = active
        assert bool(self.state.active) == active

    def inner_set_active(self, active: bool) -> None:
        """Computes the fake availability update (no return value)."""
        return None


proto = VaultStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeVault = synthesize_fake(VaultStateMachine)


def make_vault_fake(state: Optional[VaultState] = None) -> Vault:
    """Synthesizes a fake vault instance for the given model state."""
    return FakeVault(state=state or VaultState())


FakeVaultFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeVaultFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestVaultFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all vault transitions."""

    def setUp(self) -> None:
        self.fake = make_vault_fake()
        self.sm = VaultStateMachine(singletons={Vault: self.fake})

    def test_transitions_coverage(self) -> None:
        """Exercises every declared transition and seeding transition on the fake."""
        self.sm.seed_initial()
        self.fake.deposit(10)
        self.fake.deposit(5)
        assert self.fake.balance == 15
        self.fake.withdraw(4)
        assert self.fake.balance == 11
        assert self.fake.is_active is True
        self.fake.set_active(False)
        assert self.fake.is_active is False

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:10:24Z
# LAST_CHANGED: 2026-11-13T00:10:24Z
# CHANGE: Initial vault interface pretense: VaultState with balance + Env[bool] availability, 1:1 transitions for balance/is_active/deposit/withdraw/set_active, seeding transition, synthesized FakeVault with TestVaultFake transition coverage and FakeVaultFuzzTest hypothesis fuzzing.
# --- END AUTOFAB METADATA ---
