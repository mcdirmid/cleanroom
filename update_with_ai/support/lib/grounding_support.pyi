"""Stub specification for grounding support infrastructure and static InTier capabilities."""

from __future__ import annotations
from typing import Iterable, Mapping, Protocol, overload, runtime_checkable


def key[K, V](m: Mapping[K, V]) -> K: ...
def value[K, V](m: Mapping[K, V]) -> V: ...
def only_elem[T](c: Iterable[T]) -> T: ...


class SystemTier: ...
class AgentSessionTier: ...


class InTier[TierT]:
    """Static capability-checked tier membership protocol."""

    @overload
    def get_singleton[S: InTier[SystemTier]](
        self: InTier[SystemTier], key: type[S]
    ) -> S: ...

    @overload
    def get_singleton[S: InTier[SystemTier] | InTier[AgentSessionTier]](
        self: InTier[AgentSessionTier], key: type[S]
    ) -> S: ...

    def get_singleton[S](self, key: type[S]) -> S: ...
