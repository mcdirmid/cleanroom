"""Pretense: Unified State-Machine Verification & Fake Synthesis Engine."""

from pretense.collections import PretenseDict, PretenseSet, choose_weighted, make_tup
from pretense.context import get_current_draw, with_draw
from pretense.fake import FakeAdapter
from pretense.compiler import compile_hypothesis_test_case
from pretense.proto import StateMachine, StateMachineProto
from pretense.sentinels import (
    AmbiguousTransitionError,
    NoMatchingTransitionError,
    NotBound,
    NotBoundType,
    Outcome,
    PretenseError,
    PretenseSpecificationError,
    Raised,
    Value,
)
from pretense.synthesis import TraceStep, synthesize_unit_test
from pretense.transition import Transition

__version__ = "0.1.0"

__all__ = [
    "AmbiguousTransitionError",
    "FakeAdapter",
    "NoMatchingTransitionError",
    "NotBound",
    "NotBoundType",
    "Outcome",
    "PretenseDict",
    "PretenseError",
    "PretenseSet",
    "PretenseSpecificationError",
    "Raised",
    "StateMachine",
    "StateMachineProto",
    "TraceStep",
    "Transition",
    "Value",
    "choose_weighted",
    "compile_hypothesis_test_case",
    "get_current_draw",
    "make_tup",
    "synthesize_unit_test",
    "with_draw",
]
