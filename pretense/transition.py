"""Transition declaration and lifecycle blocks for Pretense state machines."""

from typing import (
    Any,
    Callable,
    Concatenate,
    Generic,
    List,
    Optional,
    ParamSpec,
    TypeVar,
    Union,
)

StateT = TypeVar("StateT")
TargetSelf = TypeVar("TargetSelf")
P = ParamSpec("P")
R = TypeVar("R")


class Transition(Generic[StateT, TargetSelf, P, R]):
    """Represents a state machine transition binding an interface target method or seeding hook."""

    def __init__(
        self,
        name: str,
        target: Optional[Callable[Concatenate[TargetSelf, P], R]] = None,
        is_seeding: bool = False,
    ) -> None:
        self.name: str = name
        self.target: Optional[Callable[Concatenate[TargetSelf, P], R]] = target
        self.is_seeding: bool = is_seeding
        self.requirements: List[Callable[[StateT, Any], bool]] = []
        self.args_fn: Any = None
        self.return_fn: Any = None
        self.provider: Any = None

    def require(
        self, fn: Callable[[StateT, Any], bool]
    ) -> Callable[[StateT, Any], bool]:
        """Register a precondition requirement block."""
        self.requirements.append(fn)
        return fn

    def arguments(
        self, fn: Callable[..., Optional[tuple[Any, ...]]]
    ) -> Callable[..., Optional[tuple[Any, ...]]]:
        """Register a bidirectional input recognizer / generator block."""
        self.args_fn = fn
        return fn

    def returns(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Register a bidirectional output recognizer / generator block."""
        self.return_fn = fn
        return fn

    def provide(self, fn: Callable[..., None]) -> Callable[..., None]:
        """Register a state mutation and postcondition verification block."""
        self.provider = fn
        return fn

    def __repr__(self) -> str:
        target_name = getattr(self.target, "__name__", "None")
        return f"<Transition {self.name} target={target_name} is_seeding={self.is_seeding}>"
