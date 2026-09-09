"""Cleanroom Lifecycle Management Architecture.

Provides hierarchically scoped lifecycle management ('system' and 'agent_session'),
zero-argument singleton instantiation, topological/recursive initialization with
mutual dependency cycle detection, multi-protocol key aliasing, and Pyright static type safety.
"""

from __future__ import annotations

import sys
from contextvars import ContextVar
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypeVar,
    cast,
    runtime_checkable,
)

T = TypeVar("T")


class LifecycleError(Exception):
    """Base error for lifecycle management failures."""


class LifecycleIsolationError(LifecycleError):
    """Raised when accessing a scoped singleton outside of its lifecycle phase."""


class LifecycleResolutionError(LifecycleError):
    """Raised when a singleton cannot be resolved in the active phase or its ancestors."""


class LifecycleInitializationError(LifecycleError):
    """Raised when a mutual or circular dependency occurs during initialize()."""


class Singleton:
    """Base class for all singletons, combining tier declaration and lifecycle initialization."""

    tier: str = "agent_session"

    def __init__(self, tier: Optional[str] = None) -> None:
        if tier is not None:
            self.tier = tier

    def initialize(self) -> None:
        """Initializes the singleton instance after zero-argument creation. Default is empty."""
        pass


Initializable = Singleton


class _InitState(Enum):
    UNINITIALIZED = auto()
    INITIALIZING = auto()
    INITIALIZED = auto()


class SingletonDescriptor:
    """Descriptor recording singleton implementation class, protocol keys, and lifecycle phase."""

    def __init__(
        self,
        impl: Optional[type[Any]],
        keys: Sequence[type[Any]],
        phase: str,
        instance: Optional[Any] = None,
    ) -> None:
        self.impl = impl
        self.keys = tuple(keys)
        self.phase = phase
        self.instance = instance

    def __repr__(self) -> str:
        name = self.impl.__name__ if self.impl is not None else repr(self.instance)
        key_names = [getattr(k, "__name__", str(k)) for k in self.keys]
        return f"<SingletonDescriptor {name} keys={key_names} phase='{self.phase}'>"


class LifecyclePrototype:
    """Blueprint for a lifecycle phase defining registered singleton implementations."""

    def __init__(self, phase: str, parent: Optional[LifecyclePrototype] = None) -> None:
        self.phase = phase
        self.parent = parent
        self._descriptors: List[SingletonDescriptor] = []
        self._key_to_desc: Dict[type[Any], SingletonDescriptor] = {}

    def register(
        self,
        impl: type[Any],
        *,
        keys: Sequence[type[Any]],
    ) -> SingletonDescriptor:
        """Registers an implementation class against all its keyed protocol types."""
        desc = SingletonDescriptor(impl=impl, keys=keys, phase=self.phase)
        self._descriptors.append(desc)
        for k in keys:
            self._key_to_desc[k] = desc
        if impl not in self._key_to_desc:
            self._key_to_desc[impl] = desc
        return desc

    def register_instance(
        self,
        instance: Any,
        *,
        keys: Sequence[type[Any]],
    ) -> SingletonDescriptor:
        """Registers a pre-constructed instance against all its keyed protocol types."""
        desc = SingletonDescriptor(impl=type(instance), keys=keys, phase=self.phase, instance=instance)
        self._descriptors.append(desc)
        for k in keys:
            self._key_to_desc[k] = desc
        return desc

    def get_descriptor(self, key: type[Any]) -> Optional[SingletonDescriptor]:
        """Looks up the descriptor associated with key in this phase prototype."""
        return self._key_to_desc.get(key)

    @property
    def descriptors(self) -> Sequence[SingletonDescriptor]:
        """Sequence of all descriptors registered in this phase prototype."""
        return tuple(self._descriptors)

    def create_child_prototype(self, phase: str) -> LifecyclePrototype:
        """Creates a child phase prototype inheriting from this prototype."""
        return LifecyclePrototype(phase=phase, parent=self)


class LifecycleRegistry:
    """Registry maintaining lifecycle prototypes for all system and session phases."""

    def __init__(self) -> None:
        self._prototypes: Dict[str, LifecyclePrototype] = {}
        # Pre-create standard phase hierarchy
        self._system_proto = LifecyclePrototype("system")
        self._session_proto = LifecyclePrototype("agent_session", parent=self._system_proto)
        self._prototypes["system"] = self._system_proto
        self._prototypes["agent_session"] = self._session_proto

    def get_prototype(self, phase: str) -> LifecyclePrototype:
        """Retrieves or creates the prototype for the specified phase."""
        if phase not in self._prototypes:
            proto = LifecyclePrototype(phase=phase, parent=self._system_proto)
            self._prototypes[phase] = proto
        return self._prototypes[phase]

    def register(
        self,
        impl: type[Any],
        *,
        keys: Sequence[type[Any]],
        phase: str = "agent_session",
    ) -> SingletonDescriptor:
        """Registers a singleton implementation into the specified phase prototype."""
        proto = self.get_prototype(phase)
        return proto.register(impl, keys=keys)

    def register_singleton(
        self,
        impl: type[Any],
        *,
        keys: Sequence[type[Any]],
        tier: Optional[str] = None,
    ) -> SingletonDescriptor:
        """Registers a singleton implementation into its declared lifecycle tier."""
        declared_tier = getattr(impl, "tier", None)
        final_tier = tier if tier is not None else (declared_tier or "agent_session")
        if declared_tier is not None and tier is not None and declared_tier != tier:
            raise LifecycleError(
                f"Class '{impl.__name__}' tier mismatch: declares tier='{declared_tier}' but registered with tier='{tier}'"
            )
        return self.register(impl, keys=keys, phase=final_tier)

    def register_instance(
        self,
        instance: Any,
        *,
        keys: Sequence[type[Any]],
        phase: str = "agent_session",
        tier: Optional[str] = None,
    ) -> SingletonDescriptor:
        """Registers a pre-constructed instance into the specified phase prototype."""
        p = tier if tier is not None else phase
        proto = self.get_prototype(p)
        return proto.register_instance(instance, keys=keys)

    def find_descriptor(self, key: type[Any]) -> Optional[SingletonDescriptor]:
        """Finds any registered descriptor across all prototypes in this registry."""
        for proto in self._prototypes.values():
            desc = proto.get_descriptor(key)
            if desc is not None:
                return desc
        return None


_global_registry = LifecycleRegistry()
_ambient_system_scope: Optional[LifecycleScope] = None
_active_scope: ContextVar[Optional[LifecycleScope]] = ContextVar("_active_scope", default=None)


def get_default_registry() -> LifecycleRegistry:
    """Returns the process-wide default LifecycleRegistry."""
    return _global_registry


def get_active_scope() -> Optional[LifecycleScope]:
    """Returns the current active LifecycleScope from ambient context."""
    return _active_scope.get()


def get_ambient_system_scope() -> LifecycleScope:
    """Returns the ambient system-tier lifecycle scope, lazily initialized."""
    global _ambient_system_scope
    if _ambient_system_scope is None:
        _ambient_system_scope = LifecycleScope("system", registry=_global_registry)
    return _ambient_system_scope


def _get_caller_singleton_tier() -> Optional[Tuple[str, str]]:
    """Inspects the call stack to find if the calling frame belongs to a Singleton.
    Returns (caller_class_name, tier) or None.
    """
    try:
        frame = sys._getframe(2)
    except ValueError:
        return None
    while frame is not None:
        caller_self = frame.f_locals.get("self")
        if isinstance(caller_self, Singleton) or hasattr(caller_self, "tier"):
            tier = getattr(caller_self, "tier", None)
            if tier is not None:
                return (type(caller_self).__name__, str(tier))
        frame = frame.f_back
    return None


def get_singleton(key: type[T]) -> T:
    """Retrieves a singleton by type from the currently active lifecycle scope on demand.

    Pyright statically infers the return value as an instance of key.
    Enforces caller tier isolation: system singletons cannot access session-scoped singletons.
    """
    caller_info = _get_caller_singleton_tier()
    scope = get_active_scope() or get_ambient_system_scope()

    if caller_info is not None:
        caller_name, caller_tier = caller_info
        if caller_tier == "system":
            # Caller is a system singleton; strictly enforce system-only visibility
            desc = scope.registry.find_descriptor(key)
            if desc is not None and desc.phase != "system":
                key_name = getattr(key, "__name__", str(key))
                raise LifecycleIsolationError(
                    f"System singleton '{caller_name}' cannot access '{key_name}' scoped to phase '{desc.phase}'"
                )
            system_scope = scope if scope.phase == "system" else (scope.parent or get_ambient_system_scope())
            return system_scope.get(key)

    return scope.get(key)


class LifecycleScope:
    """Active runtime instance of a lifecycle phase."""

    def __init__(
        self,
        phase: str,
        registry: Optional[LifecycleRegistry] = None,
        parent: Optional[LifecycleScope] = None,
    ) -> None:
        self.phase = phase
        self.registry = registry if registry is not None else (parent.registry if parent else _global_registry)
        self.prototype = self.registry.get_prototype(phase)
        self.parent = parent
        self._instances_by_desc: Dict[SingletonDescriptor, Any] = {}
        self._init_states: Dict[SingletonDescriptor, _InitState] = {}
        self._token: Optional[Any] = None
        self._instantiated_order: List[Any] = []

    def get(self, key: type[T]) -> T:
        """Retrieves a singleton matching key from this scope or delegates to parent."""
        # 1. Check if descriptor is registered in this scope's phase prototype
        desc = self.prototype.get_descriptor(key)
        if desc is not None:
            instance = self._get_or_create_and_initialize(desc)
            return cast(T, instance)

        # 2. Check parent scope for ancestor singletons (e.g. system singletons accessed from session)
        if self.parent is not None:
            return self.parent.get(key)

        # 3. Check if key is registered in a child phase (tier isolation violation)
        key_name = getattr(key, "__name__", str(key))
        global_desc = self.registry.find_descriptor(key)
        if global_desc is not None:
            raise LifecycleIsolationError(
                f"Cannot resolve '{key_name}' from phase '{self.phase}': "
                f"singleton is scoped to phase '{global_desc.phase}'"
            )

        raise LifecycleResolutionError(f"No singleton registered for '{key_name}' in phase '{self.phase}'")

    def get_singleton(self, key: type[T]) -> T:
        """Retrieves a singleton matching key from this scope or delegates to ancestors."""
        return self.get(key)

    def __call__(self, key: type[T]) -> T:
        """Allows calling scope directly as a resolver: session(key)."""
        return self.get(key)

    def _get_or_create_and_initialize(self, desc: SingletonDescriptor) -> Any:
        state = self._init_states.get(desc, _InitState.UNINITIALIZED)
        if state == _InitState.INITIALIZED:
            return self._instances_by_desc[desc]

        if state == _InitState.INITIALIZING:
            impl_name = desc.impl.__name__ if desc.impl is not None else repr(desc.instance)
            raise LifecycleInitializationError(
                f"Mutual / circular dependency detected while initializing singleton '{impl_name}'"
            )

        # 1. Instantiate with zero-argument constructor or use pre-registered instance
        if desc.instance is not None:
            instance = desc.instance
        else:
            assert desc.impl is not None
            instance = desc.impl()
        self._instances_by_desc[desc] = instance
        self._instantiated_order.append(instance)

        # 2. Mark state as INITIALIZING
        self._init_states[desc] = _InitState.INITIALIZING

        # 3. Call initialize() if implemented
        if hasattr(instance, "initialize") and callable(instance.initialize):
            instance.initialize()

        # 4. Mark state as INITIALIZED
        self._init_states[desc] = _InitState.INITIALIZED
        return instance

    def _start_phase(self) -> None:
        """Creates and initializes all singletons registered in this phase prototype."""
        for desc in self.prototype.descriptors:
            if self._init_states.get(desc) != _InitState.INITIALIZED:
                self._get_or_create_and_initialize(desc)

    def enter_child_phase(self, phase: str) -> LifecycleScope:
        """Creates a child LifecycleScope nested inside this scope."""
        return LifecycleScope(
            phase=phase,
            registry=self.registry,
            parent=self,
        )

    def __enter__(self) -> LifecycleScope:
        self._token = _active_scope.set(self)
        self._start_phase()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Teardown in reverse order of instantiation (LIFO)
        for inst in reversed(self._instantiated_order):
            if hasattr(inst, "teardown") and callable(inst.teardown):
                inst.teardown()
            elif hasattr(inst, "close") and callable(inst.close):
                inst.close()

        if self._token is not None:
            _active_scope.reset(self._token)
            self._token = None


def singleton(
    *,
    keys: Sequence[type[Any]],
    phase: str = "agent_session",
    registry: Optional[LifecycleRegistry] = None,
) -> Callable[[type[T]], type[T]]:
    """Decorator registering an implementation class into a lifecycle prototype."""
    reg = registry if registry is not None else _global_registry

    def decorator(cls: type[T]) -> type[T]:
        reg.register(cls, keys=keys, phase=phase)
        return cls

    return decorator


def enter_phase(
    phase: str,
    *,
    parent: Optional[LifecycleScope] = None,
    registry: Optional[LifecycleRegistry] = None,
) -> LifecycleScope:
    """Context manager entering a lifecycle phase scope."""
    active = get_active_scope()
    if parent is not None:
        p = parent
    elif phase == "system":
        p = None
    else:
        if active is not None:
            p = active
        elif registry is not None and registry is not _global_registry:
            p = LifecycleScope("system", registry=registry)
        else:
            p = get_ambient_system_scope()

    reg = (
        registry
        if registry is not None
        else (p.registry if p is not None else (active.registry if active is not None else _global_registry))
    )

    return LifecycleScope(
        phase=phase,
        registry=reg,
        parent=p,
    )
