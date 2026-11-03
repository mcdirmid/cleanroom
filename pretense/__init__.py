"""Pretense: Unified State-Machine Verification & Fake Synthesis Engine."""

import os
import sys
from pathlib import Path

_curr = Path(__file__).resolve().parent.parent
_REPO_ROOT = _curr
while _curr and _curr != _curr.parent:
    if (_curr / "pyproject.toml").is_file():
        _REPO_ROOT = _curr
        break
    _curr = _curr.parent

for _p in (_REPO_ROOT, _REPO_ROOT / "autofab_python", _REPO_ROOT / "autofab"):
    _str_p = str(_p)
    if _p.is_dir() and _str_p not in sys.path:
        sys.path.insert(0, _str_p)

from pretense.parts.pretense.lib.pretense import (
    AmbiguousTransitionError,
    CheckedAdapter,
    Domain,
    EnsuresCheck,
    Expr,
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
    UnsatisfiedAntecedentError,
    Value,
    call_target,
    ensure,
    ensure_raises,
    ensure_ret,
    make_return_value,
    raises,
    require,
    requires,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    test_only,
    transition,
    unreachable,
)

from pretense.collection_utils import PretenseDict, PretenseSet, choose_weighted, make_tup
from pretense import collection_utils
import sys
sys.modules.setdefault("pretense.collections", collection_utils)
from pretense.context import get_current_draw, with_draw
from pretense.compiler import compile_hypothesis_test_case
from pretense.synthesis import synthesize_unit_test


__version__ = "0.2.0"

__all__ = [
    "AmbiguousTransitionError",
    "CheckedAdapter",
    "Domain",
    "EnsuresCheck",
    "Expr",
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
    "UnsatisfiedAntecedentError",
    "Value",
    "call_target",
    "choose_weighted",
    "compile_hypothesis_test_case",
    "ensure",
    "ensure_raises",
    "ensure_ret",
    "get_current_draw",
    "make_return_value",
    "make_tup",
    "raises",
    "require",
    "requires",
    "require_arg",
    "sut",
    "sut_state",
    "synthesize_fake",
    "synthesize_unit_test",
    "test_only",
    "transition",
    "unreachable",
    "with_draw",
]
