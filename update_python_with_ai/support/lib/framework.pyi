# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-04T02:03:40Z
# CHANGE: new file
# CODE_HASH: 3e6d52e0bd7e
# --- END CLEANROOM METADATA ---

"""Cleanroom Specification Framework Stubs: Structural markers for pure .pyi specifications.

Defines decorator annotations and structural types used in low-level specifications
(`low/<name>.pyi`) and grounding specifications (`grounding/<name>.gt`).

These annotations classify classes into Cleanroom ontological kinds and specify
lifecycle scoping:
- @singleton_type: Active stateful service or coordinator with lifecycle tier scoping.
- @poly_type: Open polymorphic multiton interface or stateless protocol.
- @data_type: Passive immutable value object, record, or sum-type base.
- @variant: Closed sum-type branch extending a @data_type or another @variant.
- @operation: Active callable member with state-transition contracts.
- @override: Specialized implementation or narrowing of a supertype member.
"""

from __future__ import annotations

from typing import Any, Callable, Literal, Optional, TypeVar, Union, overload, override

__all__ = [
    "LifecycleScope",
    "LifecycleTier",
    "singleton_type",
    "poly_type",
    "data_type",
    "variant",
    "operation",
    "override",
]

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])
LifecycleTier = Literal["system", "agent_session"]


class LifecycleScope:
    """Represents an active lifecycle scope managing singleton instances and cleanup."""
    ...


@overload
def singleton_type(target_cls: type[T], /) -> type[T]: ...


@overload
def singleton_type(
    tier: Optional[LifecycleTier | str] = ...,
    /,
) -> Callable[[type[T]], type[T]]: ...


def singleton_type(
    target_or_tier: Optional[Union[type[T], LifecycleTier, str]] = None,
    /,
) -> Union[type[T], Callable[[type[T]], type[T]]]:
    """Marks an active service or coordinator as a singleton.

    Singletons are stateful services, managers, or coordinators whose lifecycle
    and visibility are bound to a specific tier:
    - "system": Root system tier; singletons persist across the entire application.
    - "agent_session" (or custom subordinate tiers): Scoped to an active session phase.

    Subordinate services express their tier membership statically by inheriting
    `InTier[TierType]` (imported from `support.lib.lifecycle`).

    Can be used with or without arguments:
        @singleton_type
        class MyService(InTier[SystemTier]): ...

        @singleton_type("system")
        class MyService(InTier[SystemTier]): ...
    """
    ...


def poly_type(cls: type[T]) -> type[T]:
    """Marks an active service as an open polymorphic multiton interface.

    Poly types represent open capabilities or stateless interfaces that can have
    multiple implementations or dynamic resolution. Unlike @singleton_type,
    @poly_type classes do not declare tier membership via InTier.
    """
    ...


def data_type(cls: type[T]) -> type[T]:
    """Marks a passive structural value type with value equality.

    Data types represent records, value objects, immutable domain entities,
    and messages. They:
    - Declare fields directly as typed dataclass attributes.
    - Never inherit from active singleton services.
    - May serve as the base root of a closed sum-type hierarchy for @variant types.
    """
    ...


def variant(cls: type[T]) -> type[T]:
    """Marks a closed sum-type variant extending a base @data_type or another @variant.

    Variants represent discriminated alternative cases of a sum type (e.g., Success vs Failure,
    or different message types). A variant must always inherit from a @data_type or another
    @variant, never from an active service.
    """
    ...


def operation(func: F) -> F:
    """Marks a member as an active callable operation on a service or data type.

    In @singleton_type and @poly_type classes, every member method is either an @operation
    (performing an action or state transition) or a @property (exposing state or references).
    Operations define preconditions (PRECONDITIONS:) and postconditions (POSTCONDITIONS:).
    """
    ...


def override(func: F) -> F:
    """Marks a member as a specialized implementation or narrowing of a supertype member.

    Override is used to indicate that a method provides a more specific implementation
    of a supertype method, typically in subclass hierarchies.
    """
    ...
