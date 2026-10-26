"""Sentinels and result wrappers for Pretense state machines."""

from typing import Any, Generic, TypeVar, Union

T = TypeVar("T")


class _NotBoundSentinel:
    """Sentinel indicating an unbound argument or return value to be generated."""

    _instance = None

    def __new__(cls) -> "_NotBoundSentinel":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "NotBound"

    def __bool__(self) -> bool:
        return False


NotBound: _NotBoundSentinel = _NotBoundSentinel()
NotBoundType = _NotBoundSentinel


class Outcome(Generic[T]):
    """Base class for Pretense transition outcomes (Value and Raised)."""


class Raised(Outcome[Any]):
    """Wraps an exception raised during method execution for recognition in returns."""

    def __init__(self, exc: Exception) -> None:
        self.exc: Exception = exc

    def __repr__(self) -> str:
        return f"Raised({self.exc!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Raised):
            return type(self.exc) is type(other.exc) and str(self.exc) == str(other.exc)
        return False


class Value(Outcome[T], Generic[T]):
    """Wraps a successful return value."""

    def __init__(self, val: T) -> None:
        self.val: T = val

    def __repr__(self) -> str:
        return f"Value({self.val!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Value):
            return self.val == other.val
        return False


class PretenseError(Exception):
    """Base exception for all Pretense errors."""


class NoMatchingTransitionError(PretenseError):
    """Raised when no transition's requirements and argument recognizers match a call."""


class AmbiguousTransitionError(PretenseError):
    """Raised when more than one candidate transition matches a call."""


class PretenseSpecificationError(PretenseError):
    """Raised when a specification defect is detected (e.g. generation returns None)."""
