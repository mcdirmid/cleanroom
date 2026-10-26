"""Hypothesis stateful test case generation for Pretense prototypes."""

from typing import Any, Callable, Dict, List, Optional, Type
import hypothesis
import hypothesis.strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule

from pretense.context import with_draw
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, PretenseSpecificationError, Raised, Value
from pretense.synthesis import TraceStep

# Active step journaling for diagnostic and timeout reporting
_ACTIVE_STEP: Optional[TraceStep] = None
_ACTIVE_TRACE: List[TraceStep] = []


def get_active_step() -> Optional[TraceStep]:
    """Returns the currently executing trace step, if any."""
    return _ACTIVE_STEP


def get_active_trace() -> List[TraceStep]:
    """Returns the trace of steps leading up to and including the current step."""
    return list(_ACTIVE_TRACE)


def format_active_step_diagnostic() -> Optional[str]:
    """Formats a diagnostic string detailing the active and preceding steps during a timeout."""
    global _ACTIVE_STEP, _ACTIVE_TRACE
    if _ACTIVE_STEP is None:
        return None
    lines = [
        f"Active Pretense Transition: '{_ACTIVE_STEP.transition_name}' (method: {_ACTIVE_STEP.target_name or '<seeding>'})",
        f"Arguments: {_ACTIVE_STEP.args!r}",
    ]
    if len(_ACTIVE_TRACE) > 1:
        lines.append(f"Preceding Steps ({len(_ACTIVE_TRACE) - 1}):")
        for i, step in enumerate(_ACTIVE_TRACE[:-1], 1):
            args_str = ", ".join(repr(a) for a in step.args)
            lines.append(f"  {i}. {step.transition_name}({args_str})")
    return "\n".join(lines)


def _invoke_target(sut: Any, target_fn: Any, args: tuple[Any, ...]) -> Any:
    target_name = getattr(target_fn, "__name__", "")
    candidates: List[Any] = []
    if isinstance(sut, dict):
        candidates.extend(sut.values())
    elif hasattr(sut, "__dict__"):
        candidates.append(sut)
        candidates.extend(vars(sut).values())
    else:
        candidates.append(sut)

    for cand in candidates:
        if cand is not None and hasattr(cand, target_name):
            attr = getattr(cand, target_name)
            if callable(attr):
                return attr(*args)

    return target_fn(sut, *args)


def compile_hypothesis_test_case(
    proto: StateMachineProto[Any],
    sut_factory: Callable[[], Any],
    initial_state_factory: Callable[[], Any],
    settings: Optional[Any] = None,
    name: Optional[str] = None,
) -> Type[RuleBasedStateMachine]:
    """Compile a StateMachineProto into a Hypothesis RuleBasedStateMachine."""
    class_name = name or f"TestPretense{proto.__class__.__name__}"

    def make_rule_method(t: Any) -> Callable[[Any, Any], None]:
        @rule(data=st.data())
        def rule_method(self: Any, data: Any) -> None:
            # 1. Evaluate declarative requirements
            if not all(req(self.sm.state, self.sm) for req in t.requirements):
                return

            with with_draw(data.draw):
                # 2. Generate arguments via NotBound
                if t.args_fn is not None:
                    import inspect
                    sig = inspect.signature(t.args_fn)
                    extra_params = [
                        p for p in list(sig.parameters.values())[2:]
                        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                    ]
                    nb_args = [NotBound] * len(extra_params)
                    args = t.args_fn(self.sm.state, self.sm, *nb_args)
                else:
                    args = ()

                if args is None:
                    raise PretenseSpecificationError(
                        f"Specification Defect: Transition '{t.name}' satisfied requirements "
                        f"but failed to generate valid arguments for state: {self.sm.state}"
                    )

                global _ACTIVE_STEP, _ACTIVE_TRACE
                if t.is_seeding:
                    # Execute seeding transition
                    current_step = TraceStep(t.name, None, True, args, {}, None)
                    self.trace.append(current_step)
                    type(self)._last_trace = list(self.trace)
                    _ACTIVE_STEP = current_step
                    _ACTIVE_TRACE = list(self.trace)

                    try:
                        res = None
                        if t.return_fn is not None:
                            res = t.return_fn(self.sm.state, self.sm, *args)
                        if t.provider is not None:
                            t.provider(self.sm.state, self.sm, *args, result=res)
                        current_step.outcome = res
                    finally:
                        _ACTIVE_STEP = None
                else:
                    # Execute real SUT method
                    current_step = TraceStep(t.name, getattr(t.target, "__name__", None), False, args, {}, None)
                    self.trace.append(current_step)
                    type(self)._last_trace = list(self.trace)
                    _ACTIVE_STEP = current_step
                    _ACTIVE_TRACE = list(self.trace)

                    sut_exc: Optional[Exception] = None
                    sut_res: Any = None
                    try:
                        sut_res = _invoke_target(self.sut, t.target, args)
                    except Exception as e:
                        sut_exc = e
                    finally:
                        _ACTIVE_STEP = None

                    sut_outcome = Raised(sut_exc) if sut_exc is not None else Value(sut_res)

                    # Recognize output and verify differential parity
                    if t.return_fn is not None:
                        recognized = t.return_fn(self.sm.state, self.sm, *args, outcome=sut_outcome)
                        if recognized is None and sut_outcome == Value(None):
                            valid_outcome = Value(None)
                        elif recognized is not None:
                            valid_outcome = recognized if isinstance(recognized, (Value, Raised)) else Value(recognized)
                        else:
                            assert False, (
                                f"Return Contract Violation: SUT produced invalid outcome {sut_outcome!r} "
                                f"which was rejected by the returns recognizer for '{t.name}'"
                            )
                    else:
                        assert sut_exc is None, (
                            f"Differential Parity Failure: SUT raised unexpected exception {sut_exc!r} "
                            f"for transition '{t.name}'"
                        )
                        valid_outcome = Value(sut_res)

                    current_step.outcome = valid_outcome

                    # If outcome was an expected exception, operation aborted: provide() is skipped!
                    if isinstance(valid_outcome, Raised):
                        return

                    # Mutate state & verify postconditions
                    actual_val = valid_outcome.val if isinstance(valid_outcome, Value) else valid_outcome
                    if t.provider is not None:
                        t.provider(self.sm.state, self.sm, *args, result=actual_val)

            # Check invariants after each step
            self.sm.check_invariants()

        rule_method.__name__ = f"step_{t.name}"
        return rule_method

    attrs: Dict[str, Any] = {}

    def __init__(self: Any) -> None:
        RuleBasedStateMachine.__init__(self)
        self.sut = sut_factory()
        self.sm = proto.make_state_machine(initial_state_factory())
        self.trace = []

    def teardown(self: Any) -> None:
        if hasattr(self.sut, "teardown"):
            self.sut.teardown()
        elif hasattr(self.sut, "close"):
            self.sut.close()
        elif isinstance(self.sut, dict) and "scope" in self.sut:
            try:
                self.sut["scope"].__exit__(None, None, None)
            except Exception:
                pass

    attrs["__init__"] = __init__
    attrs["teardown"] = teardown
    attrs["__test__"] = False

    for t in proto.transitions:
        attrs[f"step_{t.name}"] = make_rule_method(t)

    cls: Type[RuleBasedStateMachine] = type(class_name, (RuleBasedStateMachine,), attrs)
    if settings is not None:
        cls.TestCase.settings = settings
    return cls
