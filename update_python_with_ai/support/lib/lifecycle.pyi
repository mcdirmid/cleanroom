'''
# Cleanroom Lifecycle Management Specification & Usage Guide

## Overview

Cleanroom modules use hierarchically scoped lifecycle management rooted at `system`,
zero-argument singleton construction, protocol key aliasing, and on-demand singleton access via `get_singleton`.

Lifecycle tiers form a strict hierarchy rooted at `system`. Subordinate tiers are defined by system interface
components (e.g. `session = system.create_child("session")`). Descendant tiers can access singletons in their
own tier and any ancestor tier, but ancestor tiers cannot access or retain references to descendant singletons.

## Defining Subordinate Lifecycle Tiers in Interface Components

An interface module (`<name>.py`) can define a new subordinate lifecycle tier under `system` (or another parent tier):

```python
# In interface module `my_session.py`:
from __future__ import annotations
from support.lib.lifecycle import LifecycleTier, system

# Declare an immutable LifecycleTier constant as a child of system:
my_session: LifecycleTier = system.create_child("my_session")
```
This is the sole exception where an interface component defines a runtime value.

## Usage in Implementation Modules (`<name>_impl.py`)

Implementation modules define concrete singleton classes realizing interface protocols.
Each singleton class subclasses `Singleton`, specifies its `tier: LifecycleTier`, defines a zero-argument `__init__`,
and registers itself and its realized protocols in `__initialize__`.

```python
from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTier,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)
from .my_session import my_session
from . import my_interface
from . import collaborator_interface


class MyServiceImpl(my_interface.MyService, Singleton):
    # Tier must be a typed LifecycleTier object (e.g. system or my_session)
    tier = my_session

    def __init__(self) -> None:
        # Zero-argument constructor
        ...

    def initialize(self) -> None:
        # Optional post-construction initialization hook
        pass

    def perform_action(self) -> None:
        # Access collaborator singletons on demand by protocol key.
        # Can access singletons in the same tier (my_session) or ancestor tiers (system).
        collab = get_singleton(collaborator_interface.Collaborator)
        collab.do_work()


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        MyServiceImpl,
        keys=[MyServiceImpl, my_interface.MyService],
        tier=MyServiceImpl.tier,
    )
```

## Usage in Assembly Modules (`<name>_asm.py`)

Assembly modules wire concrete implementations by recursively calling `__initialize__` on all constituent modules.

```python
from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from . import constituent_a_impl, constituent_b_asm

CONSTITUENTS = [constituent_a_impl, constituent_b_asm]


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    for constituent in CONSTITUENTS:
        constituent.__initialize__(reg)
```

## Usage in Unit Tests (`<name>_impl_test.py`)

Unit tests mock foreign collaborator singletons, initialize the target module, and resolve singletons within an active lifecycle phase scope.

### Registering Mock Instances with `register_instance` (Recommended for Mocks)

When tests create a mock object or configure mock state dynamically, register the instance directly with `register_instance`:

```python
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from lib.my_session import my_session
from lib.my_interface import MyService
from lib.collaborator_interface import Collaborator
from lib.my_impl import MyServiceImpl, __initialize__


class MockCollaborator:
    tier = my_session

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
            tier=my_session,
        )

    def test_perform_action(self) -> None:
        # Enter the scoped phase matching the target component's tier
        with enter_phase(my_session, registry=self.registry) as scope:
            service = scope.get_singleton(MyService)
            service.perform_action()
            self.assertTrue(self.mock_collab.called)
```

> **Warning**: Never pass a lambda or factory function (such as `lambda: self.mock_storage`) to `register_singleton`. `register_singleton` expects an implementation class (`type[Any]`). Use `register_instance(self.mock_storage, keys=[...], tier=...)` when registering pre-constructed mock instances.

### Registering Mock Classes with `register_singleton`

When the mock is a class with a zero-argument `__init__` that can be constructed directly by the lifecycle registry:

```python
class MockCollaborator(Singleton):
    tier = my_session

    def do_work(self) -> None:
        ...

# Register the class itself:
registry.register_singleton(
    MockCollaborator,
    keys=[Collaborator],
    tier=my_session,
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


class LifecycleTier:
    name: str
    parent: Optional[LifecycleTier]
    def __init__(self, name: str, parent: Optional[LifecycleTier] = None) -> None: ...
    def create_child(self, name: str) -> LifecycleTier: ...
    def is_descendant_of(self, other: LifecycleTier | str) -> bool: ...


system: LifecycleTier


class Singleton:
    tier: LifecycleTier
    def __init__(self, tier: Optional[LifecycleTier | str] = None) -> None: ...
    def initialize(self) -> None: ...


Initializable = Singleton


class SingletonDescriptor:
    impl: Optional[type[Any]]
    keys: Sequence[type[Any]]
    phase: str
    tier: LifecycleTier
    instance: Optional[Any]
    def __init__(
        self,
        impl: Optional[type[Any]],
        keys: Sequence[type[Any]],
        phase: LifecycleTier | str,
        instance: Optional[Any] = None,
    ) -> None: ...


class LifecycleScope:
    phase: str
    tier: LifecycleTier
    registry: LifecycleRegistry
    parent: Optional[LifecycleScope]
    def __init__(
        self,
        phase: LifecycleTier | str,
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
        phase: LifecycleTier | str = ...,
    ) -> SingletonDescriptor: ...
    def register_singleton(
        self,
        impl: type[Any],
        *,
        keys: Sequence[type[Any]],
        tier: Optional[LifecycleTier | str] = None,
    ) -> SingletonDescriptor: ...
    def register_instance(
        self,
        instance: Any,
        *,
        keys: Sequence[type[Any]],
        phase: Optional[LifecycleTier | str] = None,
        tier: Optional[LifecycleTier | str] = None,
    ) -> SingletonDescriptor: ...
    def find_descriptor(self, key: type[Any]) -> Optional[SingletonDescriptor]: ...


def get_default_registry() -> LifecycleRegistry: ...


def get_active_scope() -> Optional[LifecycleScope]: ...


def get_ambient_system_scope() -> LifecycleScope: ...


def get_singleton(key: type[T]) -> T: ...


def enter_phase(
    phase: LifecycleTier | str,
    *,
    parent: Optional[LifecycleScope] = None,
    registry: Optional[LifecycleRegistry] = None,
    setup: Optional[Callable[[LifecycleScope], None]] = None,
    defer_startup: bool = False,
) -> LifecycleScope: ...


def singleton(
    *,
    keys: Sequence[type[Any]],
    phase: LifecycleTier | str = ...,
    registry: Optional[LifecycleRegistry] = None,
) -> Callable[[type[T]], type[T]]: ...
