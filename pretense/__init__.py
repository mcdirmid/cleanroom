"""Pretense: Unified State-Machine Verification & Fake Synthesis Engine."""

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (_REPO_ROOT, _REPO_ROOT / "update_python_with_ai", _REPO_ROOT / "update_with_ai"):
    _str_p = str(_p)
    if _p.is_dir() and _str_p not in sys.path:
        sys.path.insert(0, _str_p)

from update_python_with_ai.parts.pretense.lib.pretense import (
    AmbiguousTransitionError,
    Domain,
    EnsuresCheck,
    FakeAdapter,
    NoMatchingTransitionError,
    NotBound,
    NotBoundType,
    Outcome,
    PretenseEngine,
    PretenseError,
    PretenseRunResult,
    PretenseRunnerConfig,
    PretenseSpecificationError,
    Raised,
    RequiresCheck,
    StateMachine,
    StateMachineProto,
    TraceStep,
    Transition,
    TransitionContext,
    Value,
    transition,
)
from pretense.collections import PretenseDict, PretenseSet, choose_weighted, make_tup
from pretense.context import get_current_draw, with_draw
from pretense.compiler import compile_hypothesis_test_case
from pretense.synthesis import synthesize_unit_test

__version__ = "0.2.0"

__all__ = [
    "AmbiguousTransitionError",
    "Domain",
    "EnsuresCheck",
    "FakeAdapter",
    "NoMatchingTransitionError",
    "NotBound",
    "NotBoundType",
    "Outcome",
    "PretenseDict",
    "PretenseEngine",
    "PretenseError",
    "PretenseRunResult",
    "PretenseRunnerConfig",
    "PretenseSet",
    "PretenseSpecificationError",
    "Raised",
    "RequiresCheck",
    "StateMachine",
    "StateMachineProto",
    "TraceStep",
    "Transition",
    "TransitionContext",
    "Value",
    "choose_weighted",
    "compile_hypothesis_test_case",
    "get_current_draw",
    "make_tup",
    "synthesize_unit_test",
    "transition",
    "with_draw",
]
