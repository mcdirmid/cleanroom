'''
# Cleanroom Lifecycle Management Specification & Usage Guide

## Overview

Cleanroom modules use hierarchically scoped lifecycle management (`"system"` and `"agent_session"` tiers), zero-argument singleton construction, protocol key aliasing, and on-demand singleton access via `get_singleton`.

## Module Import

```python
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
```

## Usage in Implementation Modules (`<name>_impl.py`)

Implementation modules define concrete singleton classes realizing interface protocols.
Each singleton class subclasses `Singleton`, specifies its lifecycle tier, defines a zero-argument `__init__`, and registers in `__initialize__`.

```python
from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from . import my_interface
from . import collaborator_interface


class MyServiceImpl(my_interface.MyService, Singleton):
    # Tier must match grounding spec @singleton_type ('system' or 'agent_session')
    tier = "agent_session"

    def __init__(self) -> None:
        # Zero-argument constructor
        ...

    def initialize(self) -> None:
        # Optional post-construction initialization hook
        pass

    def perform_action(self) -> None:
        # Access collaborator singletons on demand by protocol key
        collab = get_singleton(collaborator_interface.Collaborator)
        collab.do_work()


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        MyServiceImpl,
        keys=[MyServiceImpl, my_interface.MyService],
        tier="agent_session",
    )
```

## Usage in Assembly Modules (`<name>_asm.py`)

Assembly modules wire concrete implementations by recursively calling `__initialize__` on all constituent modules.

```python
from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import alpha_impl, beta_impl

CONSTITUENTS = (
    alpha_impl,
    beta_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)
```

## Usage in Unit Tests (`<name>_impl_test.py`)

Unit tests instantiate a fresh `LifecycleRegistry` per test case in `setUp`, register mock dependencies, initialize the implementation under test, and enter the appropriate lifecycle phase scope.

### Registering Mock Instances with `register_instance` (Recommended for Mocks)

When tests create a mock object or configure mock state dynamically, register the instance directly with `register_instance`:

```python
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from lib.my_interface import MyService
from lib.collaborator_interface import Collaborator
from lib.my_impl import MyServiceImpl, __initialize__


class MockCollaborator:
    tier = "agent_session"

    def __init__(self) -> None:
        self.called = False

    def do_work(self) -> None:
        self.called = True


class MyServiceImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        # 1. Initialize target module into test registry
        __initialize__(self.registry)
        # 2. Register mock collaborator instance for Collaborator protocol key
        self.mock_collab = MockCollaborator()
        self.registry.register_instance(
            self.mock_collab,
            keys=[Collaborator],
            tier="agent_session",
        )

    def test_perform_action(self) -> None:
        with enter_phase("agent_session", registry=self.registry) as scope:
            service = scope.get_singleton(MyService)
            service.perform_action()
            self.assertTrue(self.mock_collab.called)
```

> **Warning**: Never pass a lambda or factory function (such as `lambda: self.mock_storage`) to `register_singleton`. `register_singleton` expects an implementation class (`type[Any]`). Use `register_instance(self.mock_storage, keys=[...], tier=...)` when registering pre-constructed mock instances.

### Registering Mock Classes with `register_singleton`

When the mock is a class with a zero-argument `__init__` that can be constructed directly by the lifecycle registry:

```python
class MockCollaborator(Singleton):
    tier = "agent_session"

    def do_work(self) -> None:
        ...

# Register the class itself:
registry.register_singleton(
    MockCollaborator,
    keys=[Collaborator],
    tier="agent_session",
)
```
'''

from typing import (
    Any,
    Callable,
    Optional,
    Sequence,
    TypeVar,
)

T = TypeVar("T")


class Singleton:
    tier: str
    def __init__(self, tier: Optional[str] = None) -> None: ...
    def initialize(self) -> None: ...


Initializable = Singleton


class SingletonDescriptor:
    impl: Optional[type[Any]]
    keys: Sequence[type[Any]]
    phase: str
    instance: Optional[Any]
    def __init__(
        self,
        impl: Optional[type[Any]],
        keys: Sequence[type[Any]],
        phase: str,
        instance: Optional[Any] = None,
    ) -> None: ...


class LifecycleScope:
    phase: str
    registry: LifecycleRegistry
    parent: Optional[LifecycleScope]
    def __init__(
        self,
        phase: str,
        registry: Optional[LifecycleRegistry] = None,
        parent: Optional[LifecycleScope] = None,
        setup: Optional[Callable[[LifecycleScope], None]] = None,
        defer_startup: bool = False,
    ) -> None: ...
    def get(self, key: type[T]) -> T: ...
    def get_singleton(self, key: type[T]) -> T: ...
    def __call__(self, key: type[T]) -> T: ...
    def __enter__(self) -> LifecycleScope: ...
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...


class LifecycleRegistry:
    def register(
        self,
        impl: type[Any],
        *,
        keys: Sequence[type[Any]],
        phase: str = "agent_session",
    ) -> SingletonDescriptor: ...
    def register_singleton(
        self,
        impl: type[Any],
        *,
        keys: Sequence[type[Any]],
        tier: Optional[str] = None,
    ) -> SingletonDescriptor: ...
    def register_instance(
        self,
        instance: Any,
        *,
        keys: Sequence[type[Any]],
        phase: str = "agent_session",
        tier: Optional[str] = None,
    ) -> SingletonDescriptor: ...
    def find_descriptor(self, key: type[Any]) -> Optional[SingletonDescriptor]: ...


def get_default_registry() -> LifecycleRegistry: ...


def get_active_scope() -> Optional[LifecycleScope]: ...


def get_ambient_system_scope() -> LifecycleScope: ...


def get_singleton(key: type[T]) -> T: ...


def enter_phase(
    phase: str,
    *,
    parent: Optional[LifecycleScope] = None,
    registry: Optional[LifecycleRegistry] = None,
    setup: Optional[Callable[[LifecycleScope], None]] = None,
    defer_startup: bool = False,
) -> LifecycleScope: ...


def singleton(
    *,
    keys: Sequence[type[Any]],
    phase: str = "agent_session",
    registry: Optional[LifecycleRegistry] = None,
) -> Callable[[type[T]], type[T]]: ...
