# === File: lru_cache_impl_pretense.py ===
from __future__ import annotations

from typing import Any, List, Optional, Tuple
import unittest

from pretense import (
    StateMachine,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_2.parts.lru_cache.lib import lru_cache_impl
from benchmark_2.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache as LRUCacheInterface,
)
from benchmark_2.parts.lru_cache.pretense.lru_cache_pretense import (
    LRUCacheState,
    LRUCacheStateMachine,
)


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class LRUCacheImplPseudoStateMachine(LRUCacheStateMachine):
    """Implementation pseudo-state machine for LRUCache."""

    def inner_capacity(self) -> int:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        return target.capacity

    def inner_size(self) -> int:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        return target.size

    def inner_is_empty(self) -> bool:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        return target.is_empty

    def inner_is_full(self) -> bool:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        return target.is_full

    def inner_configure(self, capacity: int) -> None:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        target.configure(capacity)

    def inner_get(self, key: str, default: Optional[Any]) -> Any:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        return target.get(key, default)

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        return target.put(key, value)

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        return target.peek(key, default)

    def inner_remove(self, key: str) -> Any:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        return target.remove(key)

    def inner_clear(self) -> None:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        target.clear()

    def inner_get_stats(self) -> CacheStats:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        return target.get_stats()

    def inner_reset_stats(self) -> None:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        target.reset_stats()

    def inner_keys_in_lru_order(self) -> List[str]:
        target: LRUCacheInterface = sut(LRUCacheInterface)
        return target.keys_in_lru_order()


proto = LRUCacheImplPseudoStateMachine()


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestLRUCacheImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        lru_cache_impl.__initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(lru_cache_impl.LRUCache)
        self.sm = LRUCacheImplPseudoStateMachine(singletons={
            LRUCacheInterface: self.real,
            lru_cache_impl.LRUCache: self.real,
        })
        self.checked: Any = self.sm.as_checked(LRUCacheInterface, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_basic_lifecycle(self) -> None:
        """Tests basic get, put, peek, clear, and telemetry behavior."""
        _ = self.checked.is_empty
        _ = self.checked.is_full
        _ = self.checked.size
        _ = self.checked.capacity
        self.checked.peek("nonexistent", "def")
        self.checked.get("nonexistent", "miss")
        self.checked.put("a", 1)
        _ = self.checked.is_empty
        _ = self.checked.size
        self.checked.peek("a", None)
        self.checked.get("a", None)
        self.checked.put("a", 10)
        self.checked.put("b", 2)
        _ = self.checked.keys_in_lru_order()
        _ = self.checked.get_stats()
        self.checked.reset_stats()
        self.checked.remove("a")
        self.checked.clear()
        _ = self.checked.keys_in_lru_order()

    def test_capacity_eviction(self) -> None:
        """Tests eviction when capacity limit is reached."""
        self.checked.configure(2)
        self.checked.put("k1", "v1")
        self.checked.put("k2", "v2")
        _ = self.checked.is_full
        self.checked.put("k3", "v3")
        self.checked.get("k1", "missing")
        self.checked.get("k2", None)
        self.checked.put("k4", "v4")
        _ = self.checked.keys_in_lru_order()

    def test_downsize_eviction(self) -> None:
        """Tests eviction when cache is downsized to smaller capacity."""
        self.checked.configure(5)
        self.checked.put("1", "a")
        self.checked.put("2", "b")
        self.checked.put("3", "c")
        self.checked.configure(2)
        _ = self.checked.keys_in_lru_order()

    def test_invalid_capacity_error(self) -> None:
        """Verifies CacheCapacityError when capacity is zero."""
        self.checked.violating(CacheCapacityError).configure(0)

    def test_negative_capacity_error(self) -> None:
        """Verifies CacheCapacityError when capacity is negative."""
        self.checked.violating(CacheCapacityError).configure(-5)

    def test_remove_not_found_error(self) -> None:
        """Verifies CacheKeyNotFoundError when removing absent key."""
        self.checked.violating(CacheKeyNotFoundError).remove("absent_key")


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

def make_sut() -> LRUCacheInterface:
    registry = LifecycleRegistry()
    lru_cache_impl.__initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(lru_cache_impl.LRUCache)


LRUCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="LRUCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:20:47Z
# LAST_CHANGED: 2026-11-09T22:19:52Z
# CHANGE: Implement LRUCache pseudo-state machine, real scenario tests, and Hypothesis fuzzing
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T22:20:47Z
# PRETENSE_QA_AUDIT: 2026-11-09T22:20:22Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple
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
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_2.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class LRUCacheState:
    """Canonical model state tracking cache entries, capacity, and telemetry."""
    capacity: int = 100
    items: dict[str, Any] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class LRUCacheStateMachine(StateMachine[LRUCacheState]):
    """Unified Pretense State Machine for LRUCache."""

    def __init__(
        self,
        state: Optional[LRUCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> LRUCacheState:
        """Constructs initial model state. Open parameters may be specialized by pseudo-state machines."""
        return LRUCacheState()

    @transition(name="capacity")
    def capacity(self) -> int:
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    def inner_capacity(self) -> int:
        return self.state.capacity

    @transition(name="size")
    def size(self) -> int:
        ret = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    def inner_size(self) -> int:
        return len(self.state.items)

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_empty(self) -> bool:
        return len(self.state.items) == 0

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    def inner_is_full(self) -> bool:
        return len(self.state.items) >= self.state.capacity

    @transition(LRUCache.configure)
    def configure(self, capacity: int) -> None:
        require_arg(capacity, Domain.range(1, 100), preferred=[1, 10, 100])
        self.inner_configure(capacity)
        self.state.capacity = capacity
        excess = len(self.state.items) - capacity
        if excess > 0:
            for _ in range(excess):
                lru_key = next(iter(self.state.items))
                del self.state.items[lru_key]
                self.state.evictions += 1
        assert self.state.capacity == capacity
        assert len(self.state.items) <= capacity

    def inner_configure(self, capacity: int) -> None:
        if capacity <= 0:
            raise CacheCapacityError(f"Capacity must be positive, got {capacity}")

    @transition(LRUCache.get)
    def get(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, Domain.type(str), preferred=["k1", "k2", "k3"])
        require_arg(default, Domain.any(), preferred=[None, "default"])
        ret = self.inner_get(key, default)
        if key in self.state.items:
            val = self.state.items.pop(key)
            self.state.items[key] = val
            self.state.hits += 1
            assert ret == val
        else:
            self.state.misses += 1
            assert ret == default
        return ret

    def inner_get(self, key: str, default: Optional[Any]) -> Any:
        return self.state.items.get(key, default)

    @transition(LRUCache.put)
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        require_arg(key, Domain.type(str), preferred=["k1", "k2", "k3"])
        require_arg(value, Domain.any(), preferred=["v1", "v2", 100])
        ret = self.inner_put(key, value)
        if key in self.state.items:
            del self.state.items[key]
            self.state.items[key] = value
            assert ret is None
        elif len(self.state.items) >= self.state.capacity:
            lru_key = next(iter(self.state.items))
            lru_val = self.state.items.pop(lru_key)
            self.state.evictions += 1
            self.state.items[key] = value
            assert ret == (lru_key, lru_val)
        else:
            self.state.items[key] = value
            assert ret is None
        return ret

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        if key in self.state.items:
            return None
        if len(self.state.items) >= self.state.capacity:
            lru_key = next(iter(self.state.items))
            return (lru_key, self.state.items[lru_key])
        return None

    @transition(LRUCache.peek)
    def peek(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, Domain.type(str), preferred=["k1", "k2", "k3"])
        require_arg(default, Domain.any(), preferred=[None, "default"])
        ret = self.inner_peek(key, default)
        if key in self.state.items:
            assert ret == self.state.items[key]
        else:
            assert ret == default
        return ret

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        return self.state.items.get(key, default)

    @transition(LRUCache.remove)
    def remove(self, key: str) -> Any:
        require(len(self.state.items) > 0)
        require_arg(key, Domain.in_set(set(self.state.items.keys())))
        ret = self.inner_remove(key)
        old_val = self.state.items.pop(key)
        assert ret == old_val
        return ret

    def inner_remove(self, key: str) -> Any:
        if key not in self.state.items:
            raise CacheKeyNotFoundError(f"Key {key!r} not found in cache")
        return self.state.items[key]

    @transition(LRUCache.clear)
    def clear(self) -> None:
        self.inner_clear()
        self.state.items.clear()
        assert len(self.state.items) == 0

    def inner_clear(self) -> None:
        pass

    @transition(LRUCache.get_stats)
    def get_stats(self) -> CacheStats:
        ret = self.inner_get_stats()
        assert ret.hits == self.state.hits
        assert ret.misses == self.state.misses
        assert ret.evictions == self.state.evictions
        return ret

    def inner_get_stats(self) -> CacheStats:
        return CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        )

    @transition(LRUCache.reset_stats)
    def reset_stats(self) -> None:
        self.inner_reset_stats()
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        assert self.state.hits == 0
        assert self.state.misses == 0
        assert self.state.evictions == 0

    def inner_reset_stats(self) -> None:
        pass

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(self) -> List[str]:
        ret = self.inner_keys_in_lru_order()
        assert ret == list(self.state.items.keys())
        return ret

    def inner_keys_in_lru_order(self) -> List[str]:
        return list(self.state.items.keys())


proto = LRUCacheStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeLRUCache = synthesize_fake(LRUCacheStateMachine)


def make_lru_cache_fake(state: Optional[LRUCacheState] = None) -> LRUCache:
    """Synthesizes fake instance for LRUCache."""
    return FakeLRUCache(state=state or proto.make_initial_state())


FakeLRUCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeLRUCacheFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestLRUCacheFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_lru_cache_fake()
        self.sm = LRUCacheStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        _ = self.fake.capacity
        _ = self.fake.size
        _ = self.fake.is_empty
        _ = self.fake.is_full
        self.fake.configure(10)
        self.fake.put("k1", "v1")
        self.fake.get("k1", None)
        self.fake.peek("k1", None)
        _ = self.fake.keys_in_lru_order()
        _ = self.fake.get_stats()
        self.fake.reset_stats()
        self.fake.remove("k1")
        self.fake.clear()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:18:25Z
# LAST_CHANGED: 2026-11-09T22:18:25Z
# CHANGE: Implement LRUCache interface state machine, fake synthesis, and fake tests
# --- END AUTOFAB METADATA ---
