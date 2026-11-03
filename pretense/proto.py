"""State machine prototype and instance abstractions for Pretense."""

from pretense.parts.pretense.lib.pretense import (
    CheckedAdapter,
    FakeAdapter,
    StateMachine,
    StateMachineProto,
)

__all__ = ["CheckedAdapter", "FakeAdapter", "StateMachine", "StateMachineProto"]
