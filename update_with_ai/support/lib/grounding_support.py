"""Grounding support infrastructure and static InTier capabilities."""

from __future__ import annotations
from typing import Iterable, Mapping, Protocol, overload, runtime_checkable


def key[K, V](m: Mapping[K, V]) -> K:
    """Returns an arbitrary representative key from the mapping."""
    return next(iter(m.keys()))


def value[K, V](m: Mapping[K, V]) -> V:
    """Returns an arbitrary representative value from the mapping."""
    return next(iter(m.values()))


def only_elem[T](c: Iterable[T]) -> T:
    """Returns an arbitrary representative element from the iterable collection."""
    return next(iter(c))


class SystemTier:
    """Marker type for system-level lifecycle tier."""
    pass


class AgentSessionTier:
    """Marker type for agent-session-level lifecycle tier."""
    pass


@runtime_checkable
class InTier[TierT](Protocol):
    """Static capability-checked tier membership protocol.

    Enforces that system services can only resolve system-tier singletons,
    while agent session services can resolve both system-tier and session-tier singletons.
    """

    @overload
    def get_singleton[S: InTier[SystemTier]](
        self: InTier[SystemTier], key: type[S]
    ) -> S: ...

    @overload
    def get_singleton[S: InTier[SystemTier] | InTier[AgentSessionTier]](
        self: InTier[AgentSessionTier], key: type[S]
    ) -> S: ...

    def get_singleton[S](self, key: type[S]) -> S:
        """Resolves a singleton service within capability permissions."""
        raise NotImplementedError(
            "Grounding proofs are verified statically by Pyright and are not executed dynamically."
        )
