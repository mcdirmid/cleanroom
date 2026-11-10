# === File: lru_cache_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for LRUCache."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple
import unittest

from pretense import (
    call_target,
    sut,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_3.parts.lru_cache.pretense.lru_cache_pretense import (
    LruCacheState,
    LruCacheStateMachine,
)
from benchmark_3.parts.lru_cache.lib.lru_cache import CacheCapacityError, CacheKeyNotFoundError
from benchmark_3.parts.lru_cache.lib.lru_cache_impl import LRUCache, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class LruCacheImplPseudoStateMachine(LruCacheStateMachine):
    """Implementation pseudo-state machine observing the real LRUCache SUT.

    Model state (entries, capacity, and telemetry) is maintained by the
    inherited interface transitions; every override below only observes the
    real target and records its pivot through ``call_target``.
    """

    @transition(LRUCache.configure)
    def configure(
        self,
        capacity: int,
    ) -> None:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.configure(capacity))
        assert target.capacity == capacity
        assert target.size <= capacity
        return ret

    @transition(LRUCache.get)
    def get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.get(key, default))
        assert target.size <= target.capacity
        return ret

    @transition(LRUCache.put)
    def put(
        self,
        key: str,
        value: Any,
    ) -> Optional[Tuple[str, Any]]:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.put(key, value))
        assert target.size <= target.capacity
        if ret is not None:
            assert len(ret) == 2
        return ret

    @transition(LRUCache.peek)
    def peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.peek(key, default))
        assert target.size <= target.capacity
        return ret

    @transition(LRUCache.remove)
    def remove(
        self,
        key: str,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.remove(key))
        assert target.size <= target.capacity
        return ret

    @transition(LRUCache.clear)
    def clear(
        self,
    ) -> None:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.clear())
        assert target.size == 0
        assert target.is_empty
        return ret

    @transition(LRUCache.get_stats)
    def get_stats(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.get_stats())
        assert ret.hits >= 0
        assert ret.misses >= 0
        assert ret.evictions >= 0
        return ret

    @transition(LRUCache.reset_stats)
    def reset_stats(
        self,
    ) -> None:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.reset_stats())
        assert target.size <= target.capacity
        return ret

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(
        self,
    ) -> List[str]:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.keys_in_lru_order())
        assert len(ret) == target.size
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "capacity"))
        assert ret >= 1
        return ret

    @transition(name="size")
    def size(self) -> int:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "size"))
        assert ret >= 0
        assert ret <= target.capacity
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "is_empty"))
        assert ret == (target.size == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "is_full"))
        assert ret == (target.size >= target.capacity)
        return ret


proto = LruCacheImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================


class TestLruCacheImplReal(unittest.TestCase):
    """Verifies that the concrete LRUCache implementation satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(LRUCache)
        self.sm = LruCacheImplPseudoStateMachine(singletons={LRUCache: self.real})
        self.checked = self.sm.as_checked(LRUCache, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_defaults_and_lookup(self) -> None:
        assert self.checked.capacity == 100
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert not self.checked.is_full
        assert self.checked.keys_in_lru_order() == []
        assert self.checked.get("alpha", None) is None
        assert self.checked.peek("alpha", "fallback") == "fallback"
        assert self.checked.put("alpha", 1) is None
        assert self.checked.size == 1
        assert not self.checked.is_empty
        assert self.checked.get("alpha", None) == 1
        assert self.checked.peek("alpha", None) == 1
        assert self.checked.keys_in_lru_order() == ["alpha"]

    def test_recency_promotion_and_eviction(self) -> None:
        self.checked.configure(2)
        assert self.checked.capacity == 2
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.is_full
        assert self.checked.get("a", None) == 1
        assert self.checked.keys_in_lru_order() == ["b", "a"]
        assert self.checked.put("c", 3) == ("b", 2)
        assert self.checked.keys_in_lru_order() == ["a", "c"]
        assert self.checked.put("a", 10) is None
        assert self.checked.keys_in_lru_order() == ["c", "a"]
        stats = self.checked.get_stats()
        assert stats.evictions == 1
        assert stats.hits == 1

    def test_downsize_remove_and_telemetry(self) -> None:
        self.checked.configure(3)
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.put("c", 3) is None
        self.checked.configure(1)
        assert self.checked.size == 1
        assert self.checked.keys_in_lru_order() == ["c"]
        assert self.checked.get("c", None) == 3
        assert self.checked.get("missing", "fallback") == "fallback"
        stats = self.checked.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.evictions == 2
        assert self.checked.remove("c") == 3
        assert self.checked.is_empty
        self.checked.reset_stats()
        stats = self.checked.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0

    def test_clear_preserves_telemetry(self) -> None:
        self.checked.put("x", 1)
        self.checked.put("y", 2)
        assert self.checked.get("x", None) == 1
        self.checked.clear()
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert self.checked.keys_in_lru_order() == []
        stats = self.checked.get_stats()
        assert stats.hits == 1
        assert stats.misses == 0

    def test_non_positive_capacity_rejected(self) -> None:
        # Rejection inputs violate the checked caller obligations, so the raw
        # target is exercised directly to observe the real rejection branch.
        with self.assertRaises(CacheCapacityError):
            self.real.configure(0)
        assert self.real.capacity == 100
        assert self.real.size == 0

    def test_absent_key_removal_rejected(self) -> None:
        with self.assertRaises(CacheKeyNotFoundError):
            self.real.remove("absent")
        assert self.real.size == 0
        assert self.real.is_empty


# ==============================================================================
# 3. Real Hypothesis Fuzzing
# ==============================================================================


def make_sut() -> LRUCache:
    registry = LifecycleRegistry()
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(LRUCache)


LruCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=LruCacheState,
    name="LruCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:50:01Z
# LAST_CHANGED: 2026-11-08T17:49:39Z
# CHANGE: Resolve transition facet starvation by adding real rejection scenarios: non-positive capacity configure(0) now empirically exercises the CacheCapacityError rejection branch (with capacity/size unchanged afterwards), and absent-key remove('absent') exercises the CacheKeyNotFoundError rejection branch (cache left empty). Error inputs bypass the checked domain gates since they are caller-obligation violations, so the raw SUT is exercised directly and both branches are covered under --cov.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:50:01Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:49:49Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for LRUCache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple
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
from benchmark_3.parts.lru_cache.lib.lru_cache import CacheStats, LRUCache


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================


@dataclass
class LruCacheState:
    """Canonical model state for bounded least-recently-used cache operations.

    Entries are stored in a plain dict whose iteration order is the access
    recency order (oldest first, most-recently-used last). Telemetry counters
    mirror the observable operational statistics of the target interface.
    """

    entries: dict[str, Any] = field(default_factory=dict)
    capacity: int = 100
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class LruCacheStateMachine(StateMachine[LruCacheState]):
    """Pretense model state machine for the LRUCache interface."""

    def __init__(
        self,
        state: Optional[LruCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or LruCacheState(), singletons=singletons)

    @property
    def _oldest_key(self) -> str:
        """Least-recently-used key (the first entry in recency order)."""
        return next(iter(self.state.entries))

    @transition(LRUCache.configure)
    def configure(
        self,
        capacity: int,
    ) -> None:
        require_arg(capacity, Domain.range(1, 100), preferred=[2, 5])
        excess = len(self.state.entries) - capacity
        victims: List[str] = list(self.state.entries)[:excess] if excess > 0 else []
        ret = make_return_value()
        if excess > 0:
            for victim in victims:
                del self.state.entries[victim]
            self.state.evictions += excess
        self.state.capacity = capacity
        assert ret is None
        return ret

    @transition(LRUCache.get)
    def get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require_arg(key, Domain.type(str), preferred=["alpha", "beta"])
        require_arg(default, Domain.optional(Domain.any()), preferred=[None])
        expected = self.state.entries.get(key, default)
        ret = make_return_value(expected)
        if key in self.state.entries:
            value = self.state.entries.pop(key)
            self.state.entries[key] = value
            self.state.hits += 1
        else:
            self.state.misses += 1
        assert ret == expected
        return ret

    @transition(LRUCache.put)
    def put(
        self,
        key: str,
        value: Any,
    ) -> Optional[Tuple[str, Any]]:
        require_arg(key, Domain.type(str), preferred=["alpha", "beta"])
        require_arg(value, Domain.any(), preferred=[1, "value"])
        expected: Optional[Tuple[str, Any]] = None
        if key not in self.state.entries and len(self.state.entries) >= self.state.capacity:
            victim = self._oldest_key
            expected = (victim, self.state.entries[victim])
        ret = make_return_value(expected)
        if key in self.state.entries:
            del self.state.entries[key]
            self.state.entries[key] = value
        elif expected is not None:
            del self.state.entries[expected[0]]
            self.state.evictions += 1
            self.state.entries[key] = value
        else:
            self.state.entries[key] = value
        assert ret == expected
        return ret

    @transition(LRUCache.peek)
    def peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require_arg(key, Domain.type(str), preferred=["alpha", "beta"])
        require_arg(default, Domain.optional(Domain.any()), preferred=[None])
        expected = self.state.entries.get(key, default)
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(LRUCache.remove)
    def remove(
        self,
        key: str,
    ) -> Any:
        require_arg(key, Domain.in_set(self.state.entries))
        expected = self.state.entries[key]
        ret = make_return_value(expected)
        del self.state.entries[key]
        assert ret == expected
        return ret

    @transition(LRUCache.clear)
    def clear(
        self,
    ) -> None:
        ret = make_return_value()
        self.state.entries.clear()
        assert ret is None
        return ret

    @transition(LRUCache.get_stats)
    def get_stats(
        self,
    ) -> CacheStats:
        expected = CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        )
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(LRUCache.reset_stats)
    def reset_stats(
        self,
    ) -> None:
        ret = make_return_value()
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        assert ret is None
        return ret

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(
        self,
    ) -> List[str]:
        expected = list(self.state.entries)
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        expected = self.state.capacity
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="size")
    def size(self) -> int:
        expected = len(self.state.entries)
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        expected = not self.state.entries
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        expected = len(self.state.entries) >= self.state.capacity
        ret = make_return_value(expected)
        assert ret == expected
        return ret


proto = LruCacheStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeLruCache = synthesize_fake(LruCacheStateMachine)


def make_lru_cache_fake(state: Optional[LruCacheState] = None) -> LRUCache:
    """Synthesizes an in-memory fake double of the LRUCache interface."""
    return FakeLruCache(state=state or LruCacheState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestLruCacheFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies every declared transition."""

    def setUp(self) -> None:
        self.fake = make_lru_cache_fake()

    def test_initial_properties(self) -> None:
        assert self.fake.capacity == 100
        assert self.fake.size == 0
        assert self.fake.is_empty
        assert not self.fake.is_full
        assert self.fake.keys_in_lru_order() == []

    def test_put_get_peek_remove(self) -> None:
        assert self.fake.put("alpha", 1) is None
        assert self.fake.put("beta", 2) is None
        assert self.fake.size == 2
        assert self.fake.get("alpha", None) == 1
        assert self.fake.get("missing", "fallback") == "fallback"
        assert self.fake.peek("beta", None) == 2
        assert self.fake.peek("missing", None) is None
        assert self.fake.keys_in_lru_order() == ["beta", "alpha"]
        assert self.fake.remove("alpha") == 1
        assert self.fake.size == 1
        assert self.fake.keys_in_lru_order() == ["beta"]

    def test_configure_and_eviction(self) -> None:
        self.fake.configure(2)
        assert self.fake.capacity == 2
        assert self.fake.put("a", 1) is None
        assert self.fake.put("b", 2) is None
        assert self.fake.is_full
        assert self.fake.put("c", 3) == ("a", 1)
        assert self.fake.keys_in_lru_order() == ["b", "c"]
        assert self.fake.put("b", 22) is None
        assert self.fake.keys_in_lru_order() == ["c", "b"]
        self.fake.configure(1)
        assert self.fake.size == 1
        assert self.fake.keys_in_lru_order() == ["b"]

    def test_stats_clear_and_reset(self) -> None:
        self.fake.put("alpha", 1)
        assert self.fake.get("alpha", None) == 1
        assert self.fake.get("missing", None) is None
        stats = self.fake.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.evictions == 0
        self.fake.clear()
        assert self.fake.is_empty
        assert self.fake.size == 0
        stats = self.fake.get_stats()
        assert stats.hits == 1
        self.fake.reset_stats()
        stats = self.fake.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0


# ==============================================================================
# 4. Fake Hypothesis Fuzzing
# ==============================================================================

FakeLruCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=LruCacheState,
    name="FakeLruCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:45:14Z
# LAST_CHANGED: 2026-11-08T17:45:14Z
# CHANGE: Initialized interface pretense module: LruCacheState model (entries order, capacity, telemetry), 1:1 transitions for all 13 LRUCache members with Domain-based precondition gating (configure capacity>0, remove key-in-state), synthesized FakeLruCache + make_lru_cache_fake factory, fixed fake scenario tests covering 100% of transitions, and FakeLruCacheFuzzTest hypothesis compilation.
# --- END AUTOFAB METADATA ---
