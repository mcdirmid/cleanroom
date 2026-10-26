"""In-memory Fake adapter synthesis with the Zero-Ambiguity Invariant."""

from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar
from pretense.sentinels import (
    AmbiguousTransitionError,
    NoMatchingTransitionError,
    NotBound,
    Raised,
    Value,
)
from pretense.transition import Transition

T = TypeVar("T")


class FakeAdapter:
    """Dynamic fake adapter implementing an interface Protocol via State Machine transitions."""

    def __init__(
        self,
        target_protocol: Type[Any],
        state: Any,
        transitions: List[Transition[Any, Any, Any, Any]],
        state_machine: Any = None,
    ) -> None:
        self._target_protocol = target_protocol
        self._state = state
        self._transitions = transitions
        self._state_machine = state_machine

    @property
    def state(self) -> Any:
        return self._state

    @property
    def state_machine(self) -> Any:
        return self._state_machine

    def _dispatch(self, method_name: str, *bound_args: Any, **bound_kwargs: Any) -> Any:
        candidate_transitions = [
            t
            for t in self._transitions
            if not t.is_seeding
            and (
                getattr(t.target, "__name__", None) == method_name
                or t.name == method_name
            )
        ]

        # Default no-op handling for lifecycle hooks when uncontracted by transitions
        if len(candidate_transitions) == 0 and method_name in (
            "initialize",
            "teardown",
            "close",
            "cleanup",
        ):
            return None

        matches: List[Tuple[Transition[Any, Any, Any, Any], Tuple[Any, ...]]] = []

        this = self._state_machine if self._state_machine is not None else self

        for t in candidate_transitions:
            # 1. Check requirements
            if not all(req(self._state, this) for req in t.requirements):
                continue

            # 2. Check arguments recognizer
            if t.args_fn is not None:
                parsed_args = t.args_fn(self._state, this, *bound_args, **bound_kwargs)
                if parsed_args is None:
                    continue
                matches.append((t, parsed_args))
            else:
                matches.append((t, bound_args))

        # 3. Enforce the Zero-Ambiguity Invariant
        if len(matches) == 0:
            raise NoMatchingTransitionError(
                f"No matching transition for '{method_name}' with args={bound_args}, "
                f"kwargs={bound_kwargs} in state: {self._state}"
            )
        if len(matches) > 1:
            matching_names = [t.name for t, _ in matches]
            raise AmbiguousTransitionError(
                f"Ambiguous transitions for '{method_name}' ({matching_names}) with "
                f"args={bound_args}, kwargs={bound_kwargs} in state: {self._state}"
            )

        t, resolved_args = matches[0]

        # 4. Resolve return value or raise domain exception
        if t.return_fn is not None:
            try:
                ret_val = t.return_fn(self._state, this, *resolved_args, outcome=NotBound)
            except Exception as e:
                # Direct domain exception raised by return_fn: provide() is skipped!
                raise e

            if isinstance(ret_val, Raised):
                # Wrapped domain exception: provide() is skipped!
                raise ret_val.exc

            actual_result = ret_val.val if isinstance(ret_val, Value) else ret_val

            # Mutate state & verify fake's internal postconditions
            if t.provider is not None:
                t.provider(self._state, this, *resolved_args, result=actual_result)
            return actual_result
        else:
            # Void method
            if t.provider is not None:
                t.provider(self._state, this, *resolved_args, result=None)
            return None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        # Allow standard lifecycle methods
        lifecycle_methods = {"initialize", "teardown", "close", "cleanup"}

        # Check if method exists on transitions or protocol
        has_transition = any(
            (getattr(t.target, "__name__", None) == name or t.name == name)
            for t in self._transitions
        )
        has_protocol_attr = hasattr(self._target_protocol, name) or name in dir(self._target_protocol)

        if not (has_transition or has_protocol_attr or name in lifecycle_methods):
            raise AttributeError(
                f"'{self._target_protocol.__name__}' fake has no attribute or transition '{name}'"
            )

        proto_attr = getattr(self._target_protocol, name, None)
        if isinstance(proto_attr, property):
            return self._dispatch(name)

        # Check if method exists on target protocol
        def method_proxy(*args: Any, **kwargs: Any) -> Any:
            return self._dispatch(name, *args, **kwargs)

        return method_proxy
