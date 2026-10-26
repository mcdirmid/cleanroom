"""State machine prototype and instance abstractions for Pretense."""

from typing import (
    Any,
    Callable,
    Concatenate,
    Generic,
    List,
    Optional,
    ParamSpec,
    Type,
    TypeVar,
)

from pretense.fake import FakeAdapter
from pretense.transition import Transition

StateT = TypeVar("StateT")
TargetSelf = TypeVar("TargetSelf")
P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


class StateMachine(Generic[StateT]):
    """An active instance of a state machine with concrete domain state."""

    def __init__(
        self,
        state: StateT,
        transitions: List[Transition[StateT, Any, Any, Any]],
        invariants: List[Callable[[StateT, Any], None]],
        proto: Optional["StateMachineProto[StateT]"] = None,
    ) -> None:
        self.state: StateT = state
        self.transitions: List[Transition[StateT, Any, Any, Any]] = transitions
        self.invariants: List[Callable[[StateT, Any], None]] = invariants
        self.proto: Optional["StateMachineProto[StateT]"] = proto

    def as_fake(self, protocol_type: Type[T]) -> T:
        """Synthesize an ephemeral Fake adapter satisfying the target protocol."""
        return FakeAdapter(  # type: ignore
            target_protocol=protocol_type,
            state=self.state,
            transitions=self.transitions,
            state_machine=self,
        )

    def check_invariants(self) -> None:
        """Evaluate all cross-cutting invariants against current state."""
        for inv in self.invariants:
            inv(self.state, self)

    def dispatch_transition(self, transition_name: str, *args: Any, **kwargs: Any) -> Any:
        """Dispatch a named transition (such as a seeding transition) directly."""
        matches = [t for t in self.transitions if t.name == transition_name]
        if not matches:
            raise KeyError(f"No transition named '{transition_name}' in state machine")
        t = matches[0]

        # Check requirements
        for req in t.requirements:
            assert req(self.state, self), f"Requirement failed for transition '{t.name}'"

        # Check args
        if t.args_fn is not None:
            parsed = t.args_fn(self.state, self, *args, **kwargs)
            assert parsed is not None, f"Argument generation/recognition failed for '{t.name}'"
            resolved_args = parsed
        else:
            resolved_args = args

        res = None
        if t.return_fn is not None:
            res = t.return_fn(self.state, self, *resolved_args)

        if t.provider is not None:
            t.provider(self.state, self, *resolved_args, result=res)

        self.check_invariants()
        return res

    def __getattr__(self, name: str) -> Any:
        # Check if attribute corresponds to a seeding transition
        for t in self.transitions:
            if t.is_seeding and t.name == name:
                def invoke_seeding(*args: Any, **kwargs: Any) -> Any:
                    return self.dispatch_transition(name, *args, **kwargs)
                return invoke_seeding
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


class StateMachineProto(Generic[StateT]):
    """Prototype definition holding declared transitions and invariants."""

    def __init__(self) -> None:
        self.transitions: List[Transition[StateT, Any, Any, Any]] = []
        self.invariants: List[Callable[[StateT, Any], None]] = []

    def transition(
        self,
        method: Optional[Any] = None,
        *,
        name: Optional[str] = None,
    ) -> Callable[[Callable[..., Any]], Transition[StateT, Any, Any, Any]]:
        """Declare an object method or property transition matching an interface Protocol."""
        def decorator(marker: Callable[..., Any]) -> Transition[StateT, Any, Any, Any]:
            tr_name = name or getattr(method, "__name__", marker.__name__)
            t = Transition[StateT, Any, Any, Any](
                name=tr_name,
                target=method if callable(method) else None,
                is_seeding=False,
            )
            self.transitions.append(t)
            return t

        return decorator

    def seeding(self) -> Callable[[Callable[..., Any]], Transition[StateT, Any, Any, Any]]:
        """Declare a seeding transition for environment and test configuration."""
        def decorator(marker: Callable[..., Any]) -> Transition[StateT, Any, Any, Any]:
            t = Transition[StateT, Any, Any, Any](
                name=marker.__name__,
                target=None,
                is_seeding=True,
            )
            self.transitions.append(t)
            return t

        return decorator

    def invariant(
        self, fn: Callable[[StateT, Any], None]
    ) -> Callable[[StateT, Any], None]:
        """Register a cross-cutting invariant."""
        self.invariants.append(fn)
        return fn

    def make_state_machine(self, initial_state: StateT) -> StateMachine[StateT]:
        """Instantiate an active state machine from this prototype."""
        return StateMachine[StateT](
            state=initial_state,
            transitions=list(self.transitions),
            invariants=list(self.invariants),
            proto=self,
        )

    def make_fake(self, protocol_type: Type[T], initial_state: StateT) -> T:
        """Instantiate a fake directly for the target protocol."""
        sm = self.make_state_machine(initial_state)
        return sm.as_fake(protocol_type)
