"""Sentinels and result wrappers for Pretense state machines."""

from pretense.parts.pretense.lib.pretense import (
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

__all__ = [
    "AmbiguousTransitionError",
    "NoMatchingTransitionError",
    "NotBound",
    "NotBoundType",
    "Outcome",
    "PretenseError",
    "PretenseSpecificationError",
    "Raised",
    "Value",
]
