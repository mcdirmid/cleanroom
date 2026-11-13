"""Cleanroom Lifecycle Management Architecture.

Provides hierarchically scoped lifecycle management rooted at 'system',
zero-argument singleton instantiation, topological/recursive initialization with
mutual dependency cycle detection, multi-protocol key aliasing, and Pyright static type safety.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
import unittest
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
    Union,
    cast,
    get_args,
    get_origin,
    overload,
    runtime_checkable,
)

from dataclasses import dataclass

T = TypeVar("T")


class LifecycleError(Exception):
    """Base error for lifecycle management failures."""


class LifecycleResolutionError(LifecycleError):
    """Raised when a singleton cannot be resolved in the active phase or its ancestors."""


class LifecycleIsolationError(LifecycleResolutionError):
    """Raised when accessing a scoped singleton outside of its lifecycle phase."""


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


class RootTier(LifecycleTier):
    """Base class for root lifecycle tiers in Cleanroom's hierarchy."""

    pass


class ChildTierOf[ParentTier: LifecycleTier](LifecycleTier):
    """Generic base class declaring a subordinate tier under ParentTier.

    Subordinate tiers inherit from ChildTierOf[ParentTier] to establish
    static type-level hierarchy relationships.
    """

    pass


class SystemTier(RootTier):
    """Root system tier for singleton services spanning the entire process lifecycle."""

    def __init__(self, name: str = "system") -> None:
        super().__init__(name=name, parent=None)


@runtime_checkable
class Singleton[T: LifecycleTier](Protocol):
    """Protocol representing a singleton service scoped to a lifecycle tier.

    Active services inheriting Singleton[TierType] statically declare that they belong
    to TierType (e.g. Singleton[SystemTier]), allowing static analysis, IDEs, and Cleanroom
    tools to reason about singleton visibility and collaborator reachability.
    """

    pass


# Backwards compatibility alias during migration
InTier = Singleton
Initializable = Singleton


system: SystemTier = SystemTier("system")
_known_tiers: Dict[str, LifecycleTier] = {"system": system}


def _to_snake_case(name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()


def get_tier[T: LifecycleTier](tier_type: type[T]) -> T:
    """Retrieves the singleton instance of the specified lifecycle tier type."""
    if issubclass(tier_type, SystemTier):
        return cast(T, system)
    raw_name = getattr(tier_type, "name", tier_type.__name__)
    candidates = [
        raw_name,
        raw_name.lower(),
        _to_snake_case(raw_name),
    ]
    snake = _to_snake_case(raw_name)
    if snake.endswith("_tier"):
        candidates.append(snake[:-5])
    for cand in candidates:
        if cand in _known_tiers:
            return cast(T, _known_tiers[cand])
    chosen = candidates[-1]
    child = system.create_child(chosen)
    return cast(T, child)


def _resolve_tier(val: LifecycleTier | str) -> LifecycleTier:
    if isinstance(val, LifecycleTier):
        return val
    if isinstance(val, str):
        if val in _known_tiers:
            return _known_tiers[val]
        child = system.create_child(val)
        return child
    raise TypeError(f"Expected LifecycleTier or str, got {type(val).__name__}")


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

    def create_child_prototype(self, phase: LifecycleTier | str) -> LifecyclePrototype:
        """Creates a child phase prototype inheriting from this prototype."""
        return LifecyclePrototype(phase=phase, parent=self)


def infer_singleton_keys(impl: type[Any]) -> Sequence[type[Any]]:
    """Infers protocol and implementation keys from a singleton class's MRO."""
    keys: list[type[Any]] = [impl]
    for base in getattr(impl, "__mro__", ()):
        if (
            isinstance(base, type)
            and issubclass(base, Protocol)
            and base not in (Protocol, Singleton, InTier, Initializable)
        ):
            if base not in keys:
                keys.append(cast(type[Any], base))
    # Check if explicit keys were attached via decorator metadata
    meta = getattr(impl, "__singleton_metadata__", None)
    if meta and "keys" in meta and meta["keys"]:
        for k in meta["keys"]:
            if k not in keys:
                keys.append(cast(type[Any], k))
    return tuple(keys)


def infer_singleton_tier(impl_or_key: type[Any]) -> LifecycleTier:
    """Infers the LifecycleTier from class attribute, generic base Singleton[Tier], or defaults to system."""
    if hasattr(impl_or_key, "tier") and impl_or_key.tier is not None:
        return _resolve_tier(impl_or_key.tier)
    meta = getattr(impl_or_key, "__singleton_metadata__", None)
    if meta and "tier" in meta and meta["tier"] is not None:
        return _resolve_tier(meta["tier"])
    mro = getattr(impl_or_key, "__mro__", (impl_or_key,))
    for base in mro:
        for orig in getattr(base, "__orig_bases__", ()):
            origin = get_origin(orig)
            if origin in (Singleton, InTier, Initializable):
                args = get_args(orig)
                if (
                    args
                    and isinstance(args[0], type)
                    and issubclass(args[0], LifecycleTier)
                ):
                    return get_tier(args[0])
    return system


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
        keys: Optional[Sequence[type[Any]]] = None,
        tier: Optional[LifecycleTier | str] = None,
    ) -> SingletonDescriptor:
        """Registers a singleton implementation into its declared lifecycle tier.

        If keys is omitted, keys are reflectively inferred from impl and all implemented protocols.
        If tier is omitted, tier is reflectively inferred from impl.tier or Singleton[Tier].
        """
        resolved_keys = tuple(keys) if keys is not None else infer_singleton_keys(impl)
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
            else (resolved_declared or infer_singleton_tier(impl))
        )
        return self.register(impl, keys=resolved_keys, phase=final_tier)

    def register_instance(
        self,
        instance: Any,
        *,
        keys: Optional[Sequence[type[Any]]] = None,
        phase: Optional[LifecycleTier | str] = None,
        tier: Optional[LifecycleTier | str] = None,
    ) -> SingletonDescriptor:
        """Registers a pre-constructed instance into the specified phase prototype."""
        resolved_keys = (
            tuple(keys) if keys is not None else infer_singleton_keys(type(instance))
        )
        resolved_tier = tier or phase
        if resolved_tier is None:
            resolved_tier = infer_singleton_tier(type(instance))
        p = _resolve_tier(resolved_tier)
        proto = self.get_prototype(p)
        return proto.register_instance(instance, keys=resolved_keys)

    def register_mock(
        self,
        mock_or_cls: Any,
        key: Optional[type[Any]] = None,
        *,
        tier: Optional[LifecycleTier | str] = None,
    ) -> SingletonDescriptor:
        """Registers a mock instance or mock class, automatically inferring keys and tier."""
        if isinstance(mock_or_cls, type):
            resolved_keys = (
                [key] if key is not None else infer_singleton_keys(mock_or_cls)
            )
            resolved_tier = tier or (
                infer_singleton_tier(key)
                if key is not None
                else infer_singleton_tier(mock_or_cls)
            )
            return self.register_singleton(
                mock_or_cls, keys=resolved_keys, tier=resolved_tier
            )
        else:
            resolved_keys = (
                [key] if key is not None else infer_singleton_keys(type(mock_or_cls))
            )
            resolved_tier = tier or (
                infer_singleton_tier(key)
                if key is not None
                else infer_singleton_tier(type(mock_or_cls))
            )
            return self.register_instance(
                mock_or_cls, keys=resolved_keys, tier=resolved_tier
            )

    def register_module(
        self,
        module: Any,
    ) -> Sequence[SingletonDescriptor]:
        """Registers all singletons defined in module and recurses through CONSTITUENTS if present."""
        if isinstance(module, str):
            module = importlib.import_module(module)

        descriptors: list[SingletonDescriptor] = []

        # 1. Recurse through CONSTITUENTS for assembly modules
        if hasattr(module, "CONSTITUENTS"):
            constituents = getattr(module, "CONSTITUENTS")
            if isinstance(constituents, (list, tuple)):
                for constituent in constituents:
                    descriptors.extend(self.register_module(constituent))

        # 2. Inspect classes defined in the module
        mod_name = getattr(module, "__name__", "")
        for attr_name, val in list(getattr(module, "__dict__", {}).items()):
            if isinstance(val, type) and getattr(val, "__module__", "") == mod_name:
                is_proto = getattr(val, "_is_protocol", False) or val is Protocol
                is_fake = getattr(val, "__cleanroom_fake__", False)
                has_tier = getattr(val, "tier", None) is not None
                is_singleton = (
                    getattr(val, "__cleanroom_singleton__", False)
                    or has_tier
                    or any(
                        getattr(b, "__origin__", b) is Singleton
                        or getattr(b, "_name", "") == "Singleton"
                        for b in getattr(val, "__mro__", ())
                    )
                    or any(
                        getattr(b, "__origin__", b) is Singleton
                        or getattr(b, "_name", "") == "Singleton"
                        for b in getattr(val, "__orig_bases__", ())
                    )
                )
                if is_singleton and not is_proto and not is_fake:
                    desc = self.register_singleton(cast(type[Any], val))
                    descriptors.append(desc)

        # 3. Call legacy __initialize__ if defined and not auto_initialize
        legacy_init = getattr(module, "__initialize__", None)
        if (
            legacy_init is not None
            and callable(legacy_init)
            and getattr(legacy_init, "_is_cleanroom_auto_init", False) is False
        ):
            try:
                legacy_init(self)
            except TypeError:
                legacy_init()

        return tuple(descriptors)

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
# (support.lib.lifecycle, autofab_py.support.lib.lifecycle)
import types as _types

_MODULE_ALIASES = (
    "lifecycle",
    "support.lib.lifecycle",
    "autofab_py.support.lib.lifecycle",
    "autofab.support.lib.lifecycle",
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
        sys.modules[_alias] = _this_module
        if "." in _alias:
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

    def register_mock(
        self,
        mock_or_cls: Any,
        key: Optional[type[Any]] = None,
        *,
        tier: Optional[LifecycleTier | str] = None,
    ) -> SingletonDescriptor:
        """Registers a mock instance or mock class directly into this scope's registry."""
        return self.registry.register_mock(mock_or_cls, key=key, tier=tier or self.tier)

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

        with self.activate():
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
            raise LifecycleError(f"Cannot enter closed lifecycle scope '{self.phase}'")
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


@overload
def singleton(cls: type[T], /) -> type[T]: ...


@overload
def singleton(
    *,
    keys: Optional[Sequence[type[Any]]] = None,
    tier: Optional[LifecycleTier | str] = None,
    phase: Optional[LifecycleTier | str] = None,
    registry: Optional[LifecycleRegistry] = None,
) -> Callable[[type[T]], type[T]]: ...


@overload
def singleton(
    keys_or_tier: Union[Sequence[type[Any]], LifecycleTier, str],
    /,
    *,
    keys: Optional[Sequence[type[Any]]] = None,
    tier: Optional[LifecycleTier | str] = None,
    phase: Optional[LifecycleTier | str] = None,
    registry: Optional[LifecycleRegistry] = None,
) -> Callable[[type[T]], type[T]]: ...


def singleton(
    target_or_arg: Optional[Any] = None,
    /,
    *,
    keys: Optional[Sequence[type[Any]]] = None,
    tier: Optional[LifecycleTier | str] = None,
    phase: Optional[LifecycleTier | str] = None,
    registry: Optional[LifecycleRegistry] = None,
) -> Any:
    """Decorator marking a class as a lifecycle singleton with reflective key and tier discovery.

    Can be used bare (@singleton), with parentheses (@singleton()), or with explicit keys/tier.
    """
    if isinstance(target_or_arg, type) and not issubclass(target_or_arg, LifecycleTier):
        cls = target_or_arg
        setattr(cls, "__cleanroom_singleton__", True)
        reg = registry if registry is not None else _global_registry
        reg.register_singleton(cls, keys=keys, tier=tier or phase)
        return cls

    pos_keys: Optional[Sequence[type[Any]]] = None
    pos_tier: Optional[LifecycleTier | str] = None
    if target_or_arg is not None:
        if isinstance(target_or_arg, (LifecycleTier, str)):
            pos_tier = target_or_arg
        elif isinstance(target_or_arg, (list, tuple)):
            pos_keys = target_or_arg

    final_keys = keys or pos_keys
    final_tier = tier or phase or pos_tier

    def decorator(cls: type[T]) -> type[T]:
        setattr(cls, "__cleanroom_singleton__", True)
        setattr(
            cls,
            "__singleton_metadata__",
            {"keys": final_keys, "tier": final_tier},
        )
        reg = registry if registry is not None else _global_registry
        reg.register_singleton(cls, keys=final_keys, tier=final_tier)
        return cls

    return decorator


@overload
def fake(target_or_key: type[T], /) -> Any: ...


@overload
def fake(
    target_or_key: Optional[type[Any]] = None,
    *,
    tier: Optional[LifecycleTier | str] = None,
) -> Callable[[type[T]], type[T]]: ...


def fake(
    target_or_key: Optional[Any] = None,
    *,
    tier: Optional[LifecycleTier | str] = None,
) -> Any:
    """Decorator declaring a test double or fake for a protocol key.

    Usage:
        @fake(TaskWorker)
        class FakeWorker: ...

        @fake
        class FakeWorker(TaskWorker): ...
    """
    if isinstance(target_or_key, type):
        if issubclass(target_or_key, Protocol) and target_or_key not in (
            Protocol,
            Singleton,
            InTier,
            Initializable,
        ):
            proto_key = target_or_key

            def _fake_proto_decorator(cls: type[T]) -> type[T]:
                setattr(cls, "__cleanroom_fake__", True)
                setattr(cls, "__fake_protocol__", proto_key)
                setattr(cls, "__fake_tier__", tier)
                return cls

            return _fake_proto_decorator

        cls = target_or_key
        setattr(cls, "__cleanroom_fake__", True)
        setattr(cls, "__fake_protocol__", None)
        setattr(cls, "__fake_tier__", tier)
        return cls

    def _fake_decorator(cls: type[T]) -> type[T]:
        setattr(cls, "__cleanroom_fake__", True)
        setattr(cls, "__fake_protocol__", target_or_key)
        setattr(cls, "__fake_tier__", tier)
        return cls

    return _fake_decorator


def auto_initialize(
    registry_or_module: Optional[Any] = None,
    *,
    registry: Optional[LifecycleRegistry] = None,
) -> Any:
    """Reflective auto-initializer for implementation and assembly modules.

    Can be used as:
        __initialize__ = auto_initialize
        __initialize__ = auto_initialize()
        auto_initialize(registry)
    """
    # 1. Used as factory: __initialize__ = auto_initialize()
    if registry_or_module is None and registry is None:
        caller_frame = sys._getframe(1)
        mod_name = caller_frame.f_globals.get("__name__")

        def _bound_init(reg: Optional[LifecycleRegistry] = None) -> None:
            active = get_active_scope()
            r = reg or (active.registry if active is not None else get_default_registry())
            if mod_name and mod_name in sys.modules:
                mod = sys.modules[mod_name]
                r.register_module(mod)

        setattr(_bound_init, "_is_cleanroom_auto_init", True)
        return _bound_init

    # 2. Called with registry: auto_initialize(registry) or __initialize__(self.registry)
    reg: LifecycleRegistry
    mod_to_reg: Optional[Any] = None
    if isinstance(registry_or_module, LifecycleRegistry):
        reg = registry_or_module
    else:
        active = get_active_scope()
        r_default = active.registry if active is not None else get_default_registry()
        reg = registry or r_default
        if registry_or_module is not None and not isinstance(
            registry_or_module, LifecycleRegistry
        ):
            mod_to_reg = registry_or_module

    if mod_to_reg is None:
        caller_frame = sys._getframe(1)
        mod_name = caller_frame.f_globals.get("__name__")
        if mod_name and mod_name in sys.modules:
            mod_to_reg = sys.modules[mod_name]

    if mod_to_reg is not None:
        reg.register_module(mod_to_reg)


setattr(auto_initialize, "_is_cleanroom_auto_init", True)


class LifecycleTestCase(unittest.TestCase):
    """Base test case providing automatic singleton target registration, fake auto-wiring, and scope management."""

    target: Optional[Any] = None
    tier: Optional[LifecycleTier | str] = None
    registry: LifecycleRegistry
    scope: LifecycleScope
    fakes: Dict[type[Any], Any]
    sut: Any = None

    def setUp(self) -> None:
        super().setUp()
        self.registry = LifecycleRegistry()
        self.fakes = {}

        # 1. Resolve target module or class under test
        target_mod: Optional[Any] = None
        target_cls: Optional[type[Any]] = None
        extra_impl_mods: list[Any] = []

        explicit_target = getattr(self.__class__, "target", None)
        if explicit_target is not None:
            if isinstance(explicit_target, type):
                target_cls = explicit_target
                target_mod = sys.modules.get(explicit_target.__module__)
            elif isinstance(explicit_target, str):
                try:
                    target_mod = importlib.import_module(explicit_target)
                except Exception:
                    pass
            elif hasattr(explicit_target, "__name__"):
                target_mod = explicit_target

        test_mod_name = self.__class__.__module__
        test_mod = sys.modules.get(test_mod_name)
        if test_mod is not None:
            for val in list(test_mod.__dict__.values()):
                if isinstance(val, type):
                    v_mod = getattr(val, "__module__", "")
                    if ".lib." in v_mod and (v_mod.endswith("_impl") or v_mod.endswith("_asm")):
                        cand_mod = sys.modules.get(v_mod)
                        if cand_mod is not None:
                            if target_mod is None and target_cls is None:
                                target_mod = cand_mod
                            elif cand_mod is not target_mod and cand_mod not in extra_impl_mods:
                                extra_impl_mods.append(cand_mod)

        if target_mod is None and target_cls is None:

            if target_mod is None and test_mod_name.endswith("_test"):
                target_stem = test_mod_name[:-5]
                candidates = [
                    target_stem.replace(".tests.", ".lib."),
                    target_stem.replace("tests.", "lib."),
                    target_stem,
                ]
                more_cands = []
                for c in candidates:
                    for prefix in ("autofab.", "pretense.", "autofab_py."):
                        if not c.startswith(prefix):
                            more_cands.append(prefix + c)
                candidates.extend(more_cands)
                for cand in candidates:
                    try:
                        target_mod = importlib.import_module(cand)
                        break
                    except Exception:
                        pass
                if target_mod is None:
                    # Also try inspecting test module file path if available
                    test_file = getattr(sys.modules.get(test_mod_name), "__file__", None)
                    if test_file:
                        from pathlib import Path
                        tf = Path(test_file).resolve()
                        if tf.name.endswith("_test.py"):
                            impl_name = tf.name[:-8] + ".py"
                            # Check sibling or parallel lib directory
                            lib_file = tf.parent.parent / "lib" / impl_name
                            if not lib_file.exists():
                                lib_file = tf.parent / impl_name
                            if lib_file.exists():
                                for mod in sys.modules.values():
                                    if getattr(mod, "__file__", None) == str(lib_file):
                                        target_mod = mod
                                        break
                                if target_mod is None:
                                    # Import by path spec
                                    spec = importlib.util.spec_from_file_location(lib_file.stem, lib_file)
                                    if spec and spec.loader:
                                        target_mod = importlib.util.module_from_spec(spec)
                                        spec.loader.exec_module(target_mod)

        if target_cls is None and target_mod is not None:
            mod_singletons: list[type[Any]] = []
            for val in target_mod.__dict__.values():
                if isinstance(val, type) and getattr(val, "__module__", "") == getattr(target_mod, "__name__", ""):
                    is_proto = getattr(val, "_is_protocol", False) or val is Protocol
                    is_fake = getattr(val, "__cleanroom_fake__", False)
                    has_tier = getattr(val, "tier", None) is not None
                    is_singleton = (
                        getattr(val, "__cleanroom_singleton__", False)
                        or has_tier
                        or any(
                            getattr(b, "__origin__", b) is Singleton
                            or getattr(b, "_name", "") == "Singleton"
                            for b in getattr(val, "__mro__", ())
                        )
                        or any(
                            getattr(b, "__origin__", b) is Singleton
                            or getattr(b, "_name", "") == "Singleton"
                            for b in getattr(val, "__orig_bases__", ())
                        )
                    )
                    if is_singleton and not is_proto and not is_fake:
                        mod_singletons.append(cast(type[Any], val))

            test_cls_name = self.__class__.__name__
            cleaned_test_name = test_cls_name
            for prefix in ("Test_", "Test"):
                if cleaned_test_name.startswith(prefix):
                    cleaned_test_name = cleaned_test_name[len(prefix):]
                    break
            for suffix in ("TestCase", "Tests", "Test"):
                if cleaned_test_name.endswith(suffix):
                    cleaned_test_name = cleaned_test_name[:-len(suffix)]
                    break

            # 1. Exact match against normalized class name
            for s in mod_singletons:
                if s.__name__.lower() == cleaned_test_name.lower():
                    target_cls = s
                    break

            # 2. Longest candidate matching substring (prevents shorter names like 'DAG' falsely capturing 'DAGRunnerTest')
            if target_cls is None:
                sorted_cands = sorted(mod_singletons, key=lambda c: len(c.__name__), reverse=True)
                for s in sorted_cands:
                    if s.__name__.lower() in test_cls_name.lower():
                        target_cls = s
                        break

            # 3. Fallback to sole singleton if only one exists in module
            if target_cls is None and len(mod_singletons) == 1:
                target_cls = mod_singletons[0]

        # 2. Register target and imported collaborator singletons into registry
        if target_mod is not None and getattr(target_mod, "__name__", "") != self.__class__.__module__:
            self.registry.register_module(target_mod)
        elif target_cls is not None:
            self.registry.register_singleton(target_cls)

        for extra_mod in extra_impl_mods:
            if getattr(extra_mod, "__name__", "") != self.__class__.__module__:
                self.registry.register_module(extra_mod)

        # 3. Discover and wire @fake declarations
        self._wire_fakes()

        # 4. Determine scope tier and begin phase
        scope_tier: LifecycleTier
        if self.tier is not None:
            scope_tier = _resolve_tier(self.tier)
        elif target_cls is not None:
            scope_tier = infer_singleton_tier(target_cls)
        else:
            scope_tier = system

        self.scope = begin_phase(scope_tier, registry=self.registry)
        self._scope_activation = self.scope.activate()
        self._scope_activation.__enter__()

        def _cleanup_scope():
            if hasattr(self, "_scope_activation") and self._scope_activation is not None:
                self._scope_activation.__exit__(None, None, None)
                self._scope_activation = None
            if hasattr(self, "scope") and self.scope.is_open:
                self.scope.close()

        self.addCleanup(_cleanup_scope)

        # 5. Populate self.sut if target class is defined or discovered
        if target_cls is not None:
            try:
                self.sut = self.scope.get_singleton(target_cls)
            except Exception:
                pass

    def _wire_fakes(self) -> None:
        """Discovers and instantiates @fake classes from test class and test module."""
        fake_classes: list[type[Any]] = []

        # Check nested classes on self.__class__
        for attr_name, val in self.__class__.__dict__.items():
            if isinstance(val, type) and getattr(val, "__cleanroom_fake__", False):
                fake_classes.append(val)

        # Check module-level classes
        mod = sys.modules.get(self.__class__.__module__)
        if mod is not None:
            for attr_name, val in mod.__dict__.items():
                if isinstance(val, type) and getattr(val, "__cleanroom_fake__", False):
                    if val not in fake_classes:
                        fake_classes.append(val)

        for fake_cls in fake_classes:
            instance = fake_cls()
            proto = getattr(fake_cls, "__fake_protocol__", None)
            if proto is None:
                protos = [
                    b
                    for b in fake_cls.__mro__
                    if isinstance(b, type)
                    and issubclass(b, Protocol)
                    and b not in (Protocol, Singleton, InTier, Initializable)
                ]
                proto = protos[0] if protos else fake_cls
            fake_tier = getattr(fake_cls, "__fake_tier__", None)
            resolved_proto = cast(type[Any], proto)
            self.registry.register_mock(instance, key=resolved_proto, tier=fake_tier)

            snake_name = _to_snake_case(fake_cls.__name__)
            setattr(self, snake_name, instance)
            self.fakes[resolved_proto] = instance

    def tearDown(self) -> None:
        try:
            if hasattr(self, "_scope_activation") and self._scope_activation is not None:
                self._scope_activation.__exit__(None, None, None)
                self._scope_activation = None
            if hasattr(self, "scope") and self.scope.is_open:
                self.scope.close()
        finally:
            super().tearDown()

    def get_singleton(self, key: type[T]) -> T:
        """Retrieves a singleton from the active test lifecycle scope."""
        return self.scope.get_singleton(key)

    def get_fake(self, key: type[T]) -> T:
        """Retrieves an instantiated fake collaborator registered for the given protocol or class."""
        if key in self.fakes:
            return cast(T, self.fakes[key])
        for proto, inst in self.fakes.items():
            if (isinstance(proto, type) and issubclass(proto, key)) or isinstance(inst, key):
                return cast(T, inst)
        raise KeyError(
            f"No fake registered for protocol '{getattr(key, '__name__', str(key))}'"
        )

    def register_mock(
        self,
        mock_or_cls: Any,
        key: Optional[type[Any]] = None,
        *,
        tier: Optional[LifecycleTier | str] = None,
    ) -> SingletonDescriptor:
        """Registers a mock instance or class into this test's registry."""
        return self.registry.register_mock(mock_or_cls, key=key, tier=tier)


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
        if active is not None and (registry is None or active.registry is registry):
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
