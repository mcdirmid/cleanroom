"""Comprehensive verification of Pretense 1 Next architecture.

Tests 1:1 transitions, inner transitions, single-argument assert,
concentric onion execution pipeline, synthesized fakes, and Hypothesis fuzzing.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple
import unittest
from hypothesis.stateful import run_state_machine_as_test
from pretense import (
    Domain,
    StateMachine,
    call_target,
    compile_hypothesis_test_case,
    raises,
    require_arg,
    requires,
    sut,
    synthesize_fake,
    transition,
    unreachable,
)


class CacheKeyNotFoundError(Exception):
    """Raised when key is missing."""


class LRUProtocol:
    @property
    def capacity(self) -> int: ...
    @property
    def size(self) -> int: ...
    def configure(self, capacity: int) -> None: ...
    def get(self, key: str, default: Optional[Any] = None) -> Any: ...
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]: ...
    def remove(self, key: str) -> Any: ...


@dataclass
class LRUState:
    capacity: int = 10
    items: OrderedDict[str, Any] = field(default_factory=OrderedDict)
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class LRUStateMachine(StateMachine[LRUState]):
    def __init__(self, state: Optional[LRUState] = None) -> None:
        super().__init__(state=state or LRUState())

    @transition.seeding
    def seed(self, capacity: int, items: dict[str, Any]) -> None:
        require_arg(capacity, Domain.integers(min_value=1), preferred=[10])
        require_arg(items, Domain.mapping_of(Domain.text(), Domain.any()))
        self.state.capacity = capacity
        self.state.items = OrderedDict(list(items.items())[:capacity])

    @transition(LRUProtocol.capacity)
    def capacity(self) -> int:
        ret = self.inner_capacity()
        assert ret > 0
        return ret

    def inner_capacity(self) -> int:
        return self.state.capacity

    @transition(LRUProtocol.configure)
    def configure(self, capacity: int) -> None:
        require_arg(capacity, Domain.integers(min_value=1))
        self.inner_configure(capacity)
        self.state.capacity = capacity
        while len(self.state.items) > self.state.capacity:
            self.state.items.popitem(last=False)
            self.state.evictions += 1
        assert sut(LRUProtocol).capacity == capacity
        assert sut(LRUProtocol).size <= capacity

    def inner_configure(self, capacity: int) -> None:
        return None

    @transition(LRUProtocol.get)
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        require_arg(key, Domain.text())
        require_arg(default, Domain.any(), preferred=[None])
        assert sut(LRUProtocol).size == len(self.state.items)
        ret = self.inner_get(key, default)
        if key in self.state.items:
            self.state.hits += 1
            self.state.items.move_to_end(key)
            assert ret == self.state.items[key]
        else:
            self.state.misses += 1
            assert ret == default
        return ret

    def inner_get(self, key: str, default: Optional[Any] = None) -> Any:
        return self.state.items.get(key, default)

    @transition(LRUProtocol.put)
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        require_arg(key, Domain.text())
        require_arg(value, Domain.any())
        evicted = self.inner_put(key, value)
        if evicted is not None:
            ev_k, _ = evicted
            if ev_k in self.state.items:
                del self.state.items[ev_k]
                self.state.evictions += 1
        self.state.items[key] = value
        self.state.items.move_to_end(key)
        assert sut(LRUProtocol).size == len(self.state.items)
        return evicted

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        if key not in self.state.items and len(self.state.items) >= self.state.capacity:
            fake_evicted = next(iter(self.state.items.items()))
        else:
            fake_evicted = None
        return fake_evicted

    @transition(LRUProtocol.remove)
    def remove(self, key: str) -> Any:
        require_arg(key, Domain.text())
        if key in self.state.items:
            ret = self.inner_remove(key)
            expected = self.state.items.pop(key)
            assert ret == expected
            assert sut(LRUProtocol).size == len(self.state.items)
            return ret
        else:
            with raises(CacheKeyNotFoundError):
                self.inner_remove(key)
            raise CacheKeyNotFoundError()

    def inner_remove(self, key: str) -> Any:
        if key in self.state.items:
            return self.state.items.get(key)
        return None


# Real implementation for verification testing
class ConcreteLRU:
    def __init__(self, capacity: int = 10) -> None:
        self._capacity = capacity
        self._dict: OrderedDict[str, Any] = OrderedDict()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def size(self) -> int:
        return len(self._dict)

    def configure(self, capacity: int) -> None:
        self._capacity = capacity
        while len(self._dict) > self._capacity:
            self._dict.popitem(last=False)

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        if key in self._dict:
            self._dict.move_to_end(key)
            return self._dict[key]
        return default

    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        evicted = None
        if key not in self._dict and len(self._dict) >= self._capacity:
            ev_k, ev_v = self._dict.popitem(last=False)
            evicted = (ev_k, ev_v)
        self._dict[key] = value
        self._dict.move_to_end(key)
        return evicted

    def remove(self, key: str) -> Any:
        if key in self._dict:
            return self._dict.pop(key)
        raise CacheKeyNotFoundError(f"Key {key} not found")


# Implementation pseudo state machine overriding inner transitions to drive target and check private state
class LRUImplPseudoStateMachine(LRUStateMachine):
    def inner_capacity(self) -> Any:
        target = sut(ConcreteLRU)
        ret = target.capacity
        assert ret == target._capacity
        return ret

    def inner_configure(self, capacity: int) -> None:
        super().inner_configure(capacity)
        target = sut(ConcreteLRU)
        target.configure(capacity)

    def inner_get(self, key: str, default: Optional[Any] = None) -> Any:
        super().inner_get(key, default)
        target = sut(ConcreteLRU)
        return target.get(key, default)

    def inner_put(self, key: str, value: Any) -> Any:
        super().inner_put(key, value)
        target = sut(ConcreteLRU)
        # Pre-call snapshot on private target state
        old_count = len(target._dict)
        is_update = key in target._dict
        ret = target.put(key, value)
        # Post-call differential check on private target state
        if is_update or ret is not None:
            assert len(target._dict) == old_count
        else:
            assert len(target._dict) == old_count + 1
        return ret

    def inner_remove(self, key: str) -> Any:
        target = sut(ConcreteLRU)
        return target.remove(key)


FakeLRU = synthesize_fake(LRUStateMachine)


class PretenseNextArchitectureTest(unittest.TestCase):
    def test_synthesized_fake_behavior(self) -> None:
        fake = FakeLRU()
        self.assertEqual(fake.capacity, 10)
        self.assertEqual(fake.size, 0)
        self.assertIsNone(fake.put("x", 42))
        self.assertEqual(fake.size, 1)
        self.assertEqual(fake.get("x"), 42)
        self.assertEqual(fake.remove("x"), 42)
        self.assertEqual(fake.size, 0)
        with self.assertRaises(CacheKeyNotFoundError):
            fake.remove("nonexistent")

    def test_checked_adapter_verification_and_concentric_onion(self) -> None:
        real = ConcreteLRU(capacity=2)
        sm = LRUImplPseudoStateMachine()
        driver = sm.bind(real)

        self.assertEqual(driver.capacity, 2)
        self.assertEqual(driver.size, 0)

        self.assertIsNone(driver.put("k1", 100))
        self.assertIsNone(driver.put("k2", 200))
        self.assertEqual(driver.size, 2)

        # Eviction occurs
        evicted = driver.put("k3", 300)
        self.assertEqual(evicted, ("k1", 100))
        self.assertEqual(driver.size, 2)
        self.assertIsNone(driver.get("k1"))
        self.assertEqual(driver.get("k2"), 200)

        with self.assertRaises(CacheKeyNotFoundError):
            driver.remove("k1")

    def test_property_pivot_in_pseudo_state_machine(self) -> None:
        real = ConcreteLRU(capacity=5)
        sm = LRUImplPseudoStateMachine()
        driver = sm.bind(real)
        self.assertEqual(driver.capacity, 5)

    def test_hypothesis_fuzzing_on_fake(self) -> None:
        FuzzFake = compile_hypothesis_test_case(LRUStateMachine, FakeLRU)
        run_state_machine_as_test(FuzzFake)

    def test_hypothesis_fuzzing_on_real_impl(self) -> None:
        FuzzReal = compile_hypothesis_test_case(LRUImplPseudoStateMachine, ConcreteLRU)
        run_state_machine_as_test(FuzzReal)
