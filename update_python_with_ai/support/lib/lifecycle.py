"""Cleanroom Lifecycle Management Architecture.

Provides hierarchically scoped lifecycle management rooted at 'system',
zero-argument singleton instantiation, topological/recursive initialization with
mutual dependency cycle detection, multi-protocol key aliasing, and Pyright static type safety.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
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

from dataclasses import dataclass

T = TypeVar("T")


class LifecycleError(Exception):
    """Base error for lifecycle management failures."""


class LifecycleIsolationError(LifecycleError):
    """Raised when accessing a scoped singleton outside of its lifecycle phase."""


class LifecycleResolutionError(LifecycleError):
    """Raised when a singleton cannot be resolved in the active phase or its ancestors."""


class LifecycleInitializationError(LifecycleError):
    """Raised when a mutual or circular dependency occurs during initialize()."""


@dataclass(frozen=True)
class LifecycleTier:
    """Represents a hierarchical lifecycle tier within Cleanroom's architecture."""

    name: str
    parent: Optional[LifecycleTier] = None

    def create_child(self, name: str) -> LifecycleTier:
        """Creates a child lifecycle tier under this tier."""
        child = LifecycleTier(name=name, parent=self)
        _known_tiers[name] = child
        return child

    def is_descendant_of(self, other: LifecycleTier) -> bool:
        """Checks if this tier is a descendant of another tier."""
        curr: Optional[LifecycleTier] = self.parent
        while curr is not None:
            if curr == other:
                return True
            curr = curr.parent
        return False

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        if self.parent is not None:
            return f"<LifecycleTier {self.name} parent={self.parent.name}>"
        return f"<LifecycleTier {self.name}>"


system: LifecycleTier = LifecycleTier("system")
_known_tiers: Dict[str, LifecycleTier] = {"system": system}


def _resolve_tier(val: LifecycleTier | str) -> LifecycleTier:
    if isinstance(val, LifecycleTier):
        return val
    if isinstance(val, str):
        if val in _known_tiers:
            return _known_tiers[val]
        child = system.create_child(val)
        return child
    raise TypeError(f"Expected LifecycleTier or str, got {type(val).__name__}")


class Singleton:
    """Base class for all singletons, combining tier declaration and lifecycle initialization."""

    tier: LifecycleTier

    def __init__(self, tier: Optional[LifecycleTier | str] = None) -> None:
        if tier is not None:
            self.tier = _resolve_tier(tier)

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
        phase: LifecycleTier | str,
        instance: Optional[Any] = None,
    ) -> None:
        self.impl = impl
        self.keys = tuple(keys)
        self.tier: LifecycleTier = _resolve_tier(phase)
        self.phase: str = self.tier.name
        self.instance = instance

    def __repr__(self) -> str:
        name = self.impl.__name__ if self.impl is not None else repr(self.instance)
        key_names = [getattr(k, "__name__", str(k)) for k in self.keys]
        return f"<SingletonDescriptor {name} keys={key_names} tier='{self.tier}'>"


class LifecyclePrototype:
    """Blueprint for a lifecycle phase defining registered singleton implementations."""

    def __init__(
        self, phase: LifecycleTier | str, parent: Optional[LifecyclePrototype] = None
    ) -> None:
        self.tier: LifecycleTier = _resolve_tier(phase)
        self.phase: str = self.tier.name
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
        desc = SingletonDescriptor(impl=impl, keys=keys, phase=self.tier)
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
        desc = SingletonDescriptor(
            impl=type(instance), keys=keys, phase=self.tier, instance=instance
        )
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

    def create_child_prototype(
        self, phase: LifecycleTier | str
    ) -> LifecyclePrototype:
        """Creates a child phase prototype inheriting from this prototype."""
        return LifecyclePrototype(phase=phase, parent=self)


class LifecycleRegistry:
    """Registry maintaining lifecycle prototypes for all system and session phases."""

    def __init__(self) -> None:
        self._prototypes: Dict[str, LifecyclePrototype] = {}
        # Pre-create system prototype
        self._system_proto = LifecyclePrototype(system)
        self._prototypes[system.name] = self._system_proto

    def get_prototype(self, phase: LifecycleTier | str) -> LifecyclePrototype:
        """Retrieves or creates the prototype for the specified phase."""
        t = _resolve_tier(phase)
        if t.name not in self._prototypes:
            parent_proto = (
                self.get_prototype(t.parent) if t.parent is not None else None
            )
            proto = LifecyclePrototype(phase=t, parent=parent_proto)
            self._prototypes[t.name] = proto
        return self._prototypes[t.name]

    def register(
        self,
        impl: type[Any],
        *,
        keys: Sequence[type[Any]],
        phase: LifecycleTier | str = system,
    ) -> SingletonDescriptor:
        """Registers a singleton implementation into the specified phase prototype."""
        proto = self.get_prototype(phase)
        return proto.register(impl, keys=keys)

    def register_singleton(
        self,
        impl: type[Any],
        *,
        keys: Sequence[type[Any]],
        tier: Optional[LifecycleTier | str] = None,
    ) -> SingletonDescriptor:
        """Registers a singleton implementation into its declared lifecycle tier."""
        declared_tier = getattr(impl, "tier", None)
        resolved_declared = (
            _resolve_tier(declared_tier) if declared_tier is not None else None
        )
        resolved_tier = _resolve_tier(tier) if tier is not None else None

        if (
            resolved_declared is not None
            and resolved_tier is not None
            and resolved_declared != resolved_tier
        ):
            raise LifecycleError(
                f"Class '{impl.__name__}' tier mismatch: declares tier='{resolved_declared.name}' but registered with tier='{resolved_tier.name}'"
            )
        final_tier = (
            resolved_tier
            if resolved_tier is not None
            else (resolved_declared or system)
        )
        return self.register(impl, keys=keys, phase=final_tier)

    def register_instance(
        self,
        instance: Any,
        *,
        keys: Sequence[type[Any]],
        phase: Optional[LifecycleTier | str] = None,
        tier: Optional[LifecycleTier | str] = None,
    ) -> SingletonDescriptor:
        """Registers a pre-constructed instance into the specified phase prototype."""
        p = tier if tier is not None else (phase if phase is not None else system)
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
_active_scope: ContextVar[Optional[LifecycleScope]] = ContextVar(
    "_active_scope", default=None
)

# Guarantee module identity across import alias variations
# (support.lib.lifecycle, update_python_with_ai.support.lib.lifecycle, update_with_ai.support.lib.lifecycle)
import types as _types

_MODULE_ALIASES = (
    "support.lib.lifecycle",
    "update_python_with_ai.support.lib.lifecycle",
    "update_with_ai.support.lib.lifecycle",
)

_this_module = sys.modules.get(__name__)
if _this_module is not None:

    def _ensure_module_tree(path_parts: Sequence[str], mod: _types.ModuleType) -> None:
        current: Optional[_types.ModuleType] = None
        accum = ""
        for part in path_parts[:-1]:
            accum = f"{accum}.{part}" if accum else part
            if accum in sys.modules:
                node = sys.modules[accum]
            else:
                try:
                    node = __import__(accum, fromlist=["__name__"])
                except Exception:
                    node = _types.ModuleType(accum)
                    node.__path__ = []
                sys.modules[accum] = node
            if current is not None and not hasattr(current, part):
                setattr(current, part, node)
            current = node
        if current is not None:
            setattr(current, path_parts[-1], mod)

    for _alias in _MODULE_ALIASES:
        if _alias not in sys.modules:
            sys.modules[_alias] = _this_module
        _ensure_module_tree(_alias.split("."), _this_module)


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
        _ambient_system_scope = LifecycleScope(system, registry=_global_registry)
    return _ambient_system_scope


def _get_caller_singleton_tier() -> Optional[Tuple[str, LifecycleTier]]:
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
                return (type(caller_self).__name__, _resolve_tier(tier))
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
        # Caller tier isolation check:
        # A caller in tier T cannot access singletons registered in any descendant tier of T.
        desc = scope.registry.find_descriptor(key)
        if desc is not None and desc.tier.is_descendant_of(caller_tier):
            key_name = getattr(key, "__name__", str(key))
            raise LifecycleIsolationError(
                f"{caller_tier.name.capitalize()} singleton '{caller_name}' cannot access '{key_name}' scoped to phase '{desc.phase}'"
            )
        # Find scope corresponding to caller_tier if in an active child scope
        target_scope: Optional[LifecycleScope] = scope
        while target_scope is not None and target_scope.tier != caller_tier:
            target_scope = target_scope.parent
        if target_scope is not None:
            return target_scope.get(key)
        if caller_tier == system:
            return get_ambient_system_scope().get(key)

    return scope.get(key)


class LifecycleScope:
    """Active runtime instance of a lifecycle phase."""

    def __init__(
        self,
        phase: LifecycleTier | str,
        registry: Optional[LifecycleRegistry] = None,
        parent: Optional[LifecycleScope] = None,
        setup: Optional[Callable[[LifecycleScope], None]] = None,
        defer_startup: bool = False,
    ) -> None:
        self.tier = _resolve_tier(phase)
        self.phase = self.tier.name
        self.registry = (
            registry
            if registry is not None
            else (parent.registry if parent else _global_registry)
        )
        self.prototype = self.registry.get_prototype(self.tier)
        self.parent = parent
        self._setup = setup
        self._defer_startup = defer_startup
        self._phase_started = False
        self._is_open = False
        self._is_closed = False
        self._instances_by_desc: Dict[SingletonDescriptor, Any] = {}
        self._init_states: Dict[SingletonDescriptor, _InitState] = {}
        self._token: Optional[Any] = None
        self._instantiated_order: List[Any] = []

    @property
    def is_open(self) -> bool:
        """Returns whether this lifecycle scope is open."""
        return self._is_open

    @property
    def is_closed(self) -> bool:
        """Returns whether this lifecycle scope has been closed."""
        return self._is_closed

    def get(self, key: type[T]) -> T:
        """Retrieves a singleton matching key from this scope or delegates to parent."""
        key_name = getattr(key, "__name__", str(key))
        if self._is_closed:
            raise LifecycleError(
                f"Cannot resolve '{key_name}' from closed phase '{self.phase}'"
            )

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

        raise LifecycleResolutionError(
            f"No singleton registered for '{key_name}' in phase '{self.phase}'"
        )

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
            impl_name = (
                desc.impl.__name__ if desc.impl is not None else repr(desc.instance)
            )
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
        """Creates and initializes all remaining uninitialized singletons registered in this phase prototype."""
        if self._phase_started:
            return
        self._phase_started = True
        for desc in self.prototype.descriptors:
            if self._init_states.get(desc) != _InitState.INITIALIZED:
                self._get_or_create_and_initialize(desc)

    @contextmanager
    def setup(self):
        """Context manager for lazy singleton configuration during phase setup."""
        yield self
        self._start_phase()

    def open(self) -> LifecycleScope:
        """Opens this lifecycle scope and runs startup initializations."""
        if self._is_closed:
            raise LifecycleError(f"Cannot reopen closed lifecycle scope '{self.phase}'")
        if self._is_open:
            return self
        self._is_open = True
        try:
            with self.activate():
                if self._setup is not None:
                    self._setup(self)
                if not self._defer_startup:
                    self._start_phase()
        except BaseException:
            self._is_open = False
            self.close()
            raise
        return self

    @contextmanager
    def activate(self):
        """Context manager temporarily activating this scope for singleton resolution."""
        if self._is_closed:
            raise LifecycleError(
                f"Cannot activate closed lifecycle scope '{self.phase}'"
            )
        token = _active_scope.set(self)
        try:
            yield self
        finally:
            _active_scope.reset(token)

    def close(self) -> None:
        """Tears down all instantiated singletons in reverse order of creation (LIFO)."""
        if self._is_closed:
            return
        self._is_closed = True
        self._is_open = False
        token = _active_scope.set(self)
        try:
            for inst in reversed(self._instantiated_order):
                if hasattr(inst, "teardown") and callable(inst.teardown):
                    inst.teardown()
                elif hasattr(inst, "close") and callable(inst.close):
                    inst.close()
        finally:
            _active_scope.reset(token)

    def enter_child_phase(
        self,
        phase: LifecycleTier | str,
        *,
        setup: Optional[Callable[[LifecycleScope], None]] = None,
        defer_startup: bool = False,
    ) -> LifecycleScope:
        """Creates a child LifecycleScope nested inside this scope."""
        return LifecycleScope(
            phase=phase,
            registry=self.registry,
            parent=self,
            setup=setup,
            defer_startup=defer_startup,
        )

    def begin_child_phase(
        self,
        phase: LifecycleTier | str,
        *,
        setup: Optional[Callable[[LifecycleScope], None]] = None,
        defer_startup: bool = False,
    ) -> LifecycleScope:
        """Begins a child LifecycleScope nested inside this scope without a context manager."""
        scope = LifecycleScope(
            phase=phase,
            registry=self.registry,
            parent=self,
            setup=setup,
            defer_startup=defer_startup,
        )
        return scope.open()

    def __enter__(self) -> LifecycleScope:
        if self._is_closed:
            raise LifecycleError(
                f"Cannot enter closed lifecycle scope '{self.phase}'"
            )
        self._is_open = True
        self._token = _active_scope.set(self)
        try:
            if self._setup is not None:
                self._setup(self)
            if not self._defer_startup:
                self._start_phase()
        except BaseException:
            if self._token is not None:
                _active_scope.reset(self._token)
                self._token = None
            self.close()
            raise
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            self.close()
        finally:
            if self._token is not None:
                _active_scope.reset(self._token)
                self._token = None


def singleton(
    *,
    keys: Sequence[type[Any]],
    phase: LifecycleTier | str = system,
    registry: Optional[LifecycleRegistry] = None,
) -> Callable[[type[T]], type[T]]:
    """Decorator registering an implementation class into a lifecycle prototype."""
    reg = registry if registry is not None else _global_registry

    def decorator(cls: type[T]) -> type[T]:
        reg.register(cls, keys=keys, phase=phase)
        return cls

    return decorator


def _create_scope(
    phase: LifecycleTier | str,
    *,
    parent: Optional[LifecycleScope] = None,
    registry: Optional[LifecycleRegistry] = None,
    setup: Optional[Callable[[LifecycleScope], None]] = None,
    defer_startup: bool = False,
) -> LifecycleScope:
    tier = _resolve_tier(phase)
    active = get_active_scope()
    if parent is not None:
        p = parent
    elif tier == system:
        p = None
    else:
        if active is not None:
            p = active
        elif registry is not None and registry is not _global_registry:
            p = LifecycleScope(system, registry=registry)
        else:
            p = get_ambient_system_scope()

    reg = (
        registry
        if registry is not None
        else (
            p.registry
            if p is not None
            else (active.registry if active is not None else _global_registry)
        )
    )

    return LifecycleScope(
        phase=tier,
        registry=reg,
        parent=p,
        setup=setup,
        defer_startup=defer_startup,
    )


def enter_phase(
    phase: LifecycleTier | str,
    *,
    parent: Optional[LifecycleScope] = None,
    registry: Optional[LifecycleRegistry] = None,
    setup: Optional[Callable[[LifecycleScope], None]] = None,
    defer_startup: bool = False,
) -> LifecycleScope:
    """Context manager entering a lifecycle phase scope."""
    return _create_scope(
        phase=phase,
        parent=parent,
        registry=registry,
        setup=setup,
        defer_startup=defer_startup,
    )


def begin_phase(
    phase: LifecycleTier | str,
    *,
    parent: Optional[LifecycleScope] = None,
    registry: Optional[LifecycleRegistry] = None,
    setup: Optional[Callable[[LifecycleScope], None]] = None,
    defer_startup: bool = False,
) -> LifecycleScope:
    """Begins a lifecycle phase without binding to a context manager.

    Creates the scope, executes setup and startup initializations (unless deferred),
    and leaves the scope open for activation via scope.activate().
    Call scope.close() when the phase is completed.
    """
    scope = _create_scope(
        phase=phase,
        parent=parent,
        registry=registry,
        setup=setup,
        defer_startup=defer_startup,
    )
    return scope.open()
