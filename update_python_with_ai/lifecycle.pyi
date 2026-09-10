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
'''

from typing import (
    Any,
    ContextManager,
    Optional,
    Sequence,
    TypeVar,
)

T = TypeVar("T")


class Singleton:
    tier: str
    def __init__(self, tier: Optional[str] = None) -> None: ...
    def initialize(self) -> None: ...


class LifecycleRegistry:
    def register_singleton(
        self,
        impl: type[Any],
        *,
        keys: Sequence[type[Any]],
        tier: Optional[str] = None,
    ) -> Any: ...


def get_default_registry() -> LifecycleRegistry: ...


def get_singleton(key: type[T]) -> T: ...


def enter_phase(phase: str, name: Optional[str] = None) -> ContextManager[Any]: ...
