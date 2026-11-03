"""Pretense core interfaces, models, and stateful testing primitives."""

from __future__ import annotations

import ast
import copy
import inspect
import textwrap
from contextlib import contextmanager

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Collection,
    Concatenate,
    Dict,
    Generator,
    Generic,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
    cast,
    overload,
    runtime_checkable,
)
from typing_extensions import ParamSpec, TypeVar

from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T", default=Any)
Target = TypeVar("Target", default=Any)
P = ParamSpec("P", default=...)
R = TypeVar("R", default=Any)
StateT = TypeVar("StateT", covariant=True, default=Any)
SelfT = TypeVar("SelfT", default=Any)
E = TypeVar("E", default=Any)
K = TypeVar("K", default=Any)
V = TypeVar("V", default=Any)


class NotBoundType:
    """Pretense sentinel distinguishing omitted parameters from explicit None values."""

    _instance = None

    def __new__(cls) -> NotBoundType:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "NotBound"

    def __bool__(self) -> bool:
        return False


NotBound: NotBoundType = NotBoundType()
_last_ensured_ret: ContextVar[Any] = ContextVar("_last_ensured_ret", default=NotBound)
_last_raised_exc: ContextVar[Optional[BaseException]] = ContextVar("_last_raised_exc", default=None)


@dataclass(frozen=True)
class Outcome(Generic[T]):
    """Encapsulates the result of evaluating an operation."""


@dataclass(frozen=True)
class Value(Outcome[T], Generic[T]):
    """Wraps a successful return value."""
    val: T

    def unwrap(self) -> T:
        return self.val

    def __repr__(self) -> str:
        return f"Value({self.val!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Value):
            return self.val == other.val
        return False


@dataclass(frozen=True)
class Raised(Outcome[Any]):
    """Wraps an expected or intercepted exception."""
    exc: BaseException
    message: str = ""

    def __post_init__(self) -> None:
        if not self.message and self.exc:
            object.__setattr__(self, "message", str(self.exc))

    def unwrap(self) -> Any:
        raise self.exc

    def __repr__(self) -> str:
        return f"Raised({self.exc!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Raised):
            return type(self.exc) is type(other.exc) and str(self.exc) == str(other.exc)
        return False


class PretenseError(Exception):
    """Base exception for all Pretense errors."""


class UnsatisfiedAntecedentError(PretenseError):
    """Raised when an argument domain cannot generate values in the current state."""


class NoMatchingTransitionError(PretenseError):
    """Raised when no transition's requirements and argument recognizers match a call."""


class AmbiguousTransitionError(PretenseError):
    """Raised when more than one candidate transition matches a call."""


_CURRENT_DRAW: ContextVar[Optional[Callable[..., Any]]] = ContextVar(
    "_CURRENT_DRAW", default=None
)
_ACTIVE_SUTS: ContextVar[Dict[Type[Any], Any]] = ContextVar(
    "_ACTIVE_SUTS", default={}
)
_current_sut: ContextVar[Any] = ContextVar("_current_sut", default=None)
_is_verification: ContextVar[bool] = ContextVar("_is_verification", default=False)
_current_target: ContextVar[Any] = ContextVar("_current_target", default=None)
_current_method: ContextVar[Optional[str]] = ContextVar("_current_method", default=None)
_current_args: ContextVar[Tuple[Any, ...]] = ContextVar("_current_args", default=())
_current_kwargs: ContextVar[Dict[str, Any]] = ContextVar("_current_kwargs", default={})
_expected_raises: ContextVar[Optional[Any]] = ContextVar("_expected_raises", default=None)
_current_sm: ContextVar[Optional[Any]] = ContextVar("_current_sm", default=None)
_last_contracted_exception_type: ContextVar[Optional[Type[BaseException]]] = ContextVar(
    "_last_contracted_exception_type", default=None
)
_in_make_return_value: ContextVar[bool] = ContextVar("_in_make_return_value", default=False)


class raises:
    """Context manager asserting that an operation under test raises a contracted exception."""

    def __init__(self, exc_type: Type[BaseException], match: str = "") -> None:
        self.exc_type = exc_type
        self.match = match
        self.caught: Optional[BaseException] = None
        self._token: Optional[Token[Any]] = None

    def __enter__(self) -> raises:
        self._token = _expected_raises.set(self)
        _last_contracted_exception_type.set(self.exc_type)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if self._token is not None:
            _expected_raises.reset(self._token)
        if exc_val is not None:
            if issubclass(exc_type, self.exc_type):
                if self.match and self.match not in str(exc_val):
                    raise AssertionError(f"Exception message '{exc_val}' does not match pattern '{self.match}'")
                self.caught = exc_val
                return False
            return False
        if _is_verification.get():
            raise AssertionError(f"Expected exception {self.exc_type.__name__} was not raised")
        else:
            try:
                raise self.exc_type()
            except TypeError:
                raise self.exc_type(f"Contracted {self.exc_type.__name__} raised by synthesized fake")


def make_return_value(fake_val: Any = None) -> Any:
    """Pivot in an interface state machine transition."""
    if _is_verification.get():
        target = _current_target.get()
        method_name = _current_method.get()
        args = _current_args.get()
        kwargs = _current_kwargs.get()
        sm = _current_sm.get()
        if target is None or method_name is None:
            _last_ensured_ret.set(fake_val)
            return fake_val

        # Check if implementation pseudo state machine overrides this method
        if sm is not None and type(sm) is not StateMachine and not _in_make_return_value.get():
            sm_cls = type(sm)
            base_cls = None
            for c in sm_cls.__mro__:
                if c is not sm_cls and issubclass(c, StateMachine) and hasattr(c, method_name):
                    base_cls = c
                    break
            if base_cls is not None:
                override_fn = getattr(sm_cls, method_name, None)
                base_fn = getattr(base_cls, method_name, None)
                if override_fn is not None and override_fn is not base_fn:
                    target_override = getattr(override_fn, "__target_fn__", override_fn)
                    tok = _in_make_return_value.set(True)
                    try:
                        res = target_override(sm, *args, **kwargs)
                        _last_ensured_ret.set(res)
                        return res
                    finally:
                        _in_make_return_value.reset(tok)

        method = getattr(target, method_name)
        res = method(*args, **kwargs) if callable(method) else method
        _last_ensured_ret.set(res)
        return res
    else:
        _last_ensured_ret.set(fake_val)
        return fake_val


@overload
def call_target(target_call: Type[R]) -> R: ...
@overload
def call_target(target_call: R) -> R: ...
def call_target(target_call: Union[R, Type[R]]) -> R:
    """Pivot in an implementation pseudo state machine transition."""
    if isinstance(target_call, type):
        target = _current_target.get()
        method_name = _current_method.get()
        args = _current_args.get()
        kwargs = _current_kwargs.get()
        if target is None or method_name is None:
            return cast(R, None)
        method = getattr(target, method_name)
        res = method(*args, **kwargs) if callable(method) else method
        _last_ensured_ret.set(res)
        return cast(R, res)
    _last_ensured_ret.set(target_call)
    return target_call


def sut(singleton_type: Type[T]) -> T:
    """Resolves a registered singleton under test or collaborator from dynamic context."""
    active = _current_sut.get()
    if active is not None:
        if isinstance(active, singleton_type) or getattr(active, "__class__", None) == singleton_type or getattr(type(active), "__name__", "") == getattr(singleton_type, "__name__", ""):
            return cast(T, active)
    suts = _ACTIVE_SUTS.get()
    if singleton_type in suts:
        return cast(T, suts[singleton_type])
    for s_type, s_inst in suts.items():
        if isinstance(s_type, type) and (
            issubclass(s_type, singleton_type)
            or getattr(s_type, "__name__", "") == getattr(singleton_type, "__name__", "")
        ):
            return cast(T, s_inst)
        if isinstance(s_inst, singleton_type):
            return cast(T, s_inst)
    try:
        from support.lib.lifecycle import get_singleton
        return cast(T, get_singleton(singleton_type))
    except Exception:
        pass
    if active is not None:
        return cast(T, active)
    raise KeyError(f"No singleton registered for type '{singleton_type.__name__}' in active context")


def sut_state(state_cls: Type[StateT]) -> StateT:
    """Resolves active state model for a collaborator or target."""
    active = _current_sut.get()
    if hasattr(active, "state") and (isinstance(active.state, state_cls) or getattr(type(active.state), "__name__", "") == state_cls.__name__):
        return cast(StateT, active.state)
    for c in _ACTIVE_SUTS.get().values():
        if hasattr(c, "state") and (isinstance(c.state, state_cls) or getattr(type(c.state), "__name__", "") == state_cls.__name__):
            return cast(StateT, c.state)
    raise PretenseError(f"No active state model of type {state_cls.__name__} found in context")


def test_only(fn: T) -> T:
    """Decorator marking an interface query method or property as test-only observability query."""
    setattr(fn, "__test_only__", True)
    return fn


def unreachable(reason: str = "Unreachable code executed") -> Any:
    """Marks an unreachable code path, impossible branch, or defensive dead-end."""
    raise AssertionError(f"Unreachable: {reason}")


def get_current_draw() -> Optional[Callable[..., Any]]:
    """Get the active draw function if running inside a Hypothesis rule."""
    return _CURRENT_DRAW.get()


@contextmanager
def with_draw(draw_fn: Optional[Callable[..., Any]]) -> Generator[None, None, None]:
    """Execute a block within dynamic scope bound to a draw function."""
    token: Token[Optional[Callable[..., Any]]] = _CURRENT_DRAW.set(draw_fn)
    try:
        yield
    finally:
        _CURRENT_DRAW.reset(token)


class DrawContext:
    """Manages dynamic scope binding for property-based test sampling."""

    @staticmethod
    def get_current_draw() -> Optional[Callable[..., Any]]:
        return get_current_draw()

    @staticmethod
    def with_draw(draw_fn: Optional[Callable[..., Any]]) -> Any:
        return with_draw(draw_fn)


def _is_strategy(val: Any) -> bool:
    """Checks whether a value is a Hypothesis SearchStrategy."""
    try:
        from hypothesis.strategies import SearchStrategy
        if isinstance(val, SearchStrategy):
            return True
    except ImportError:
        pass
    return (
        hasattr(val, "example")
        and hasattr(val, "filter")
        and hasattr(val, "map")
        and callable(getattr(val, "example", None))
    )


def _resolve_argument_value(val: Any, draw_fn: Optional[Callable[..., Any]]) -> Any:
    """Resolves an argument value, drawing from SearchStrategy if active or falling back to example."""
    if _is_strategy(val):
        if draw_fn is not None:
            return draw_fn(val)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return val.example()
    return val



class PretenseSpecificationError(PretenseError):
    """Raised when a state machine contract, transition invariant, or antecedent predicate is violated."""


@dataclass(frozen=True)
class TraceStep:
    """Records an executed state transition step within a run trace."""
    transition_name: str
    target_name: Optional[str] = None
    is_seeding: bool = False
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    outcome: Optional[Any] = None


@dataclass
class PretenseRunnerConfig:
    """Configuration governing test discovery, fuzzing, coverage, and watchdogs."""
    target_paths: List[str]
    fuzz: bool = True
    cov: bool = False
    cov_threshold: float = 100.0
    timeout: float = 45.0
    synthesize: bool = False


@dataclass
class PretenseRunResult:
    """Summary metrics of test execution."""
    passed: int = 0
    failed: int = 0
    coverage_pct: float = 0.0
    counterexamples: List[List[TraceStep]] = field(default_factory=list)
    is_passing: bool = True


def _safe_instantiate_exception(exc_cls: Type[Exception], match: str = "") -> Exception:
    """Safely instantiates an exception for fake adapter dispatch, handling multi-argument exceptions."""
    msg = match or "Contract violation"
    try:
        return exc_cls(msg)
    except TypeError:
        pass
    import inspect
    try:
        sig = inspect.signature(exc_cls)
        args: list[Any] = []
        kwargs: dict[str, Any] = {}
        for i, (name, param) in enumerate(sig.parameters.items()):
            if param.default is not inspect.Parameter.empty:
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            if param.annotation is int:
                args.append(0)
            elif param.annotation is float:
                args.append(0.0)
            elif param.annotation is bool:
                args.append(False)
            elif param.annotation is list or param.annotation is Sequence:
                args.append([])
            elif param.annotation is tuple:
                args.append(())
            elif param.annotation is dict:
                args.append({})
            elif i == 0 or "message" in name.lower() or "msg" in name.lower():
                args.append(msg)
            else:
                args.append(f"<mock_{name}>")
        return exc_cls(*args, **kwargs)
    except Exception:
        pass
    try:
        obj = object.__new__(exc_cls)
        Exception.__init__(obj, msg)
        return obj
    except Exception:
        return exc_cls()


class RequiresCheck:
    """Precondition check helper that records failure flags and reasons without exception overhead."""

    def __init__(self) -> None:
        self.ok: bool = True
        self.reasons: List[str] = []

    def __call__(self, condition: bool, reason: str = "") -> bool:
        if not condition:
            self.ok = False
            if reason:
                self.reasons.append(reason)
            return False
        return True


class EnsuresCheck:
    """Postcondition check helper providing assertion checks, equality diffs, and singleton lookup."""

    def __init__(self, singletons: Optional[Dict[Type[Any], Any]] = None) -> None:
        self.singletons: Dict[Type[Any], Any] = dict(singletons or {})

    def __call__(self, condition: bool, msg: str = "") -> None:
        if not condition:
            raise AssertionError(msg or "Postcondition check failed")

    def equal(self, actual: Any, expected: Any, msg: str = "") -> None:
        if actual != expected:
            prefix = f"{msg}: " if msg else ""
            raise AssertionError(f"{prefix}Expected {expected!r}, but got {actual!r}")

    def get(self, singleton_type: Type[T]) -> T:
        if singleton_type in self.singletons:
            return self.singletons[singleton_type]
        for s_type, s_inst in self.singletons.items():
            if isinstance(s_type, type) and (issubclass(s_type, singleton_type) or getattr(s_type, "__name__", "") == getattr(singleton_type, "__name__", "")):
                return s_inst
            if isinstance(s_inst, singleton_type):
                return s_inst
        raise KeyError(f"No singleton registered for type '{singleton_type.__name__}'")


def require(
    condition: bool,
    reason_or_exc: Union[str, Type[PretenseSpecificationError]] = "",
    exc_class: Optional[Type[PretenseSpecificationError]] = None,
) -> None:
    """Precondition requirement assertion enforcing state machine antecedents."""
    if not condition:
        target_exc_cls = exc_class
        reason = ""
        if isinstance(reason_or_exc, type) and issubclass(reason_or_exc, BaseException):
            target_exc_cls = reason_or_exc
        elif isinstance(reason_or_exc, str):
            reason = reason_or_exc

        if target_exc_cls is not None:
            try:
                raise target_exc_cls()
            except TypeError:
                msg = f"Requirement failed: {reason}" if reason else "Requirement failed"
                raise target_exc_cls(msg)
        msg = f"Requirement failed: {reason}" if reason else "Requirement failed"
        raise PretenseSpecificationError(msg)


requires = require


@overload
def require_arg(
    val: Sequence[E],
    domain: Union[Domain[Sequence[E]], Domain[List[E]], Domain[Tuple[E, ...]]],
    preferred: Optional[Sequence[Sequence[E]]] = None,
) -> None: ...
@overload
def require_arg(
    val: Optional[Sequence[E]],
    domain: Union[Domain[Optional[Sequence[E]]], Domain[Optional[List[E]]], Domain[Optional[Tuple[E, ...]]]],
    preferred: Optional[Sequence[Optional[Sequence[E]]]] = None,
) -> None: ...
@overload
def require_arg(
    val: T,
    domain: Domain[T],
    preferred: Optional[Sequence[T]] = None,
) -> None: ...
def require_arg(
    val: Any,
    domain: Any,
    preferred: Optional[Sequence[Any]] = None,
) -> None:
    """Argument domain validation and preferred candidate binding."""
    dom: Domain[Any] = domain if isinstance(domain, Domain) else Domain.of(domain)
    if not dom.validate(val):
        raise PretenseSpecificationError(
            f"Argument value {val!r} failed domain validation for {domain}. "
            "If this argument is valid per the specification contract (e.g. testing error paths or edge cases), "
            "the domain passed to require_arg may be too restrictive. Consider using Domain.type(...) or open domains, "
            "and pass preferred=[...] for fuzz generation sizing."
        )


def ensure(condition: bool, reason: str = "") -> None:
    """Postcondition assertion verifying invariants over model state and test singletons."""
    if not condition:
        msg = f"Postcondition failed: {reason}" if reason else "Postcondition failed"
        raise AssertionError(msg)


def ensure_ret(
    call_expr: T,
    domain: Optional[Domain[T]] = None,
    preferred: Optional[Sequence[T]] = None,
) -> T:
    """Wrapped execution verifying return value against an expected domain or value."""
    _last_ensured_ret.set(call_expr)
    if domain is not None:
        dom: Domain[T] = domain if isinstance(domain, Domain) else Domain.of(domain)
        if not dom.validate(call_expr):
            raise AssertionError(
                f"Return value {call_expr!r} does not belong to expected domain {domain}"
            )
    return call_expr


class ensure_raises:
    """Wrapped execution verifying that an operation under test raises a contracted exception."""

    def __init__(
        self,
        call_expr: Any = None,
        exc_type: Optional[Type[BaseException]] = None,
        match: str = "",
    ) -> None:
        self.exc_type = exc_type
        self.match = match
        self.raised = False
        if exc_type is not None:
            raise AssertionError(
                f"Expected exception {exc_type.__name__} was not raised"
            )

    def __enter__(self) -> ensure_raises:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> bool:
        if exc_type is None:
            expected = self.exc_type.__name__ if self.exc_type else "exception"
            raise AssertionError(f"Expected exception {expected} was not raised")
        if self.exc_type and issubclass(exc_type, self.exc_type):
            if self.match and self.match not in str(exc_val):
                raise AssertionError(
                    f"Exception message '{exc_val}' does not match pattern '{self.match}'"
                )
            self.raised = True
            return True
        return False


def _draw_from_domain(concrete_domain: Domain[Any], draw: Optional[Callable[..., Any]]) -> Any:
    """Draws a value from a Domain using the active draw function or fallback example."""
    strat = concrete_domain.to_strategy()
    if callable(strat) and not _is_strategy(strat):
        import inspect
        try:
            sig = inspect.signature(strat)
            params = list(sig.parameters.values())
            takes_draw = len(params) >= 1 and params[0].kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        except (ValueError, TypeError):
            takes_draw = False

        if takes_draw:
            effective_draw = draw if draw is not None else (lambda s: _resolve_argument_value(s, None))
            val = strat(effective_draw)
        else:
            val = strat()
        return _resolve_argument_value(val, draw)
    return _resolve_argument_value(strat, draw)


class Domain(Generic[T]):
    """Specification of an argument domain uniting generative sampling and analytical validation."""

    def __init__(
        self,
        strategy: Union[Callable[..., T], Any],
        validator: Optional[Callable[[T], bool]] = None,
        default: Any = NotBound,
    ) -> None:
        self.strategy = strategy
        self.validator = validator
        self.default = default

    def to_strategy(self) -> Any:
        strat = self.strategy
        if callable(strat) and not _is_strategy(strat):
            return strat
        return strat

    def validate(self, val: Any) -> bool:
        if self.validator is not None:
            return bool(self.validator(val))
        return True

    @classmethod
    def set(cls, items: Collection[T]) -> Domain[T]:
        if isinstance(items, Expr):
            from hypothesis import strategies as st

            def _dyn_set_strat(draw: Any) -> Any:
                seq_dyn = tuple(items.value())
                return draw(st.sampled_from(seq_dyn) if seq_dyn else st.nothing())

            return Domain[T](
                strategy=_dyn_set_strat,
                validator=lambda val: val in tuple(items.value()),
            )
        seq = tuple(items)
        from hypothesis import strategies as st
        return Domain[T](
            strategy=st.sampled_from(seq) if seq else st.nothing(),
            validator=lambda val: val in seq,
        )

    @classmethod
    def in_set(cls, items: Collection[T]) -> Domain[T]:
        return cls.set(items)

    @classmethod
    def sampled_from(cls, items: Collection[T]) -> Domain[T]:
        return cls.set(items)

    @classmethod
    def not_in(
        cls,
        items: Collection[T],
        base: Optional[Any] = None,
        base_type: Optional[Type[T]] = None,
        prefix: str = "item_",
    ) -> Domain[T]:
        from hypothesis import strategies as st
        forbidden = set(items)
        if base is not None:
            base_dom = cls.of(base)
            b_strat = base_dom.to_strategy()
            if _is_strategy(b_strat):
                strat: Any = b_strat.filter(lambda x: x not in forbidden)
            else:
                @st.composite
                def _not_in_base_strat(draw_fn: Any) -> Any:
                    for _ in range(50):
                        cand = _draw_from_domain(base_dom, draw_fn)
                        if cand not in forbidden:
                            return cand
                    raise PretenseSpecificationError(f"Failed to sample value not in {forbidden!r}")

                strat = _not_in_base_strat()

            return Domain[T](
                strategy=strat,
                validator=lambda val: base_dom.validate(val) and val not in forbidden,
            )

        if base_type is str or (base_type is None and not (forbidden and all(isinstance(x, int) and not isinstance(x, bool) for x in forbidden))):
            strat: Any = st.integers(min_value=0, max_value=10000).map(lambda i: f"{prefix}{i}").filter(lambda s: s not in forbidden)
            return Domain[T](
                strategy=strat,
                validator=lambda val: isinstance(val, str) and val not in forbidden,
            )
        elif base_type is int or (forbidden and all(isinstance(x, int) and not isinstance(x, bool) for x in forbidden)):
            strat = st.integers(min_value=0, max_value=10000).filter(lambda x: x not in forbidden)
            return Domain[T](
                strategy=strat,
                validator=lambda val: isinstance(val, int) and not isinstance(val, bool) and val not in forbidden,
            )
        else:
            strat = st.integers(min_value=0, max_value=10000).map(lambda i: f"{prefix}{i}").filter(lambda s: s not in forbidden)
            return Domain[T](
                strategy=strat,
                validator=lambda val: val not in forbidden,
            )

    @classmethod
    def any(cls) -> Domain[Any]:
        from hypothesis import strategies as st
        return Domain[Any](
            strategy=st.one_of(
                st.integers(min_value=-1000, max_value=1000),
                st.text(min_size=0, max_size=50),
                st.booleans(),
                st.none(),
            ),
            validator=lambda val: True,
        )

    @classmethod
    def subset_of(cls, items: Collection[T]) -> Domain[Set[T]]:
        from hypothesis import strategies as st
        seq = tuple(items)
        allowed = set(seq)
        strat = st.sets(st.sampled_from(seq)) if seq else st.builds(set)
        return Domain[Set[T]](
            strategy=strat,
            validator=lambda val: (
                isinstance(val, Collection)
                and not isinstance(val, (str, bytes, dict))
                and set(val).issubset(allowed)
            ),
        )

    @classmethod
    def just(cls, val: Union[T, Expr[T]]) -> Domain[T]:
        if isinstance(val, Expr):
            return Domain[T](
                strategy=lambda: val.value(),
                validator=lambda v: v == val.value(),
            )
        from hypothesis import strategies as st
        return Domain[T](
            strategy=st.just(val),
            validator=lambda v: v == val,
        )

    @classmethod
    def range(cls, start: Any, stop: Any, step: int = 1) -> Domain[int]:
        from hypothesis import strategies as st
        if isinstance(start, Expr) or isinstance(stop, Expr):
            def _dyn_range_strat(draw: Any) -> int:
                s = int(start.value()) if isinstance(start, Expr) else int(start)
                e = int(stop.value()) if isinstance(stop, Expr) else int(stop)
                return int(draw(st.integers(min_value=s, max_value=e - 1) if s < e else st.nothing()))

            def _dyn_range_val(val: Any) -> bool:
                s = int(start.value()) if isinstance(start, Expr) else int(start)
                e = int(stop.value()) if isinstance(stop, Expr) else int(stop)
                return isinstance(val, int) and not isinstance(val, bool) and val in range(s, e, step)

            return Domain[int](
                strategy=_dyn_range_strat,
                validator=_dyn_range_val,
            )
        r = range(start, stop, step)
        return Domain[int](
            strategy=st.integers(min_value=start, max_value=stop - 1) if start < stop else st.nothing(),
            validator=lambda val: isinstance(val, int) and not isinstance(val, bool) and val in r,
        )

    @classmethod
    def integers(
        cls,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
    ) -> Domain[int]:
        from hypothesis import strategies as st
        strat = st.integers(min_value=min_value, max_value=max_value)

        def _int_val(val: Any) -> bool:
            if not isinstance(val, int) or isinstance(val, bool):
                return False
            if min_value is not None and val < min_value:
                return False
            if max_value is not None and val > max_value:
                return False
            return True

        return Domain[int](strategy=strat, validator=_int_val)

    @classmethod
    def regex(cls, pattern: Union[str, Any]) -> Domain[str]:
        from hypothesis import strategies as st
        import re
        pat = re.compile(pattern) if isinstance(pattern, str) else pattern
        return Domain[str](
            strategy=st.from_regex(pat, fullmatch=True),
            validator=lambda val: isinstance(val, str) and bool(pat.fullmatch(val)),
        )

    @overload
    @classmethod
    def type(
        cls,
        target_cls: Type[T],
        validator: Optional[Callable[[Any], bool]] = None,
        **kwargs: Any,
    ) -> Domain[T]: ...
    @overload
    @classmethod
    def type(
        cls,
        target_cls: Any,
        validator: Optional[Callable[[Any], bool]] = None,
        **kwargs: Any,
    ) -> Domain[Any]: ...
    @classmethod
    def type(
        cls,
        target_cls: Any,
        validator: Optional[Callable[[Any], bool]] = None,
        **kwargs: Any,
    ) -> Domain[Any]:
        from hypothesis import strategies as st
        import typing

        if target_cls is typing.Any:
            return cls.any()
        origin = typing.get_origin(target_cls)
        if origin is typing.Union:
            u_args = typing.get_args(target_cls)
            if typing.Any in u_args:
                return cls.any()
            has_none = type(None) in u_args
            non_none = [a for a in u_args if a is not type(None)]
            if len(non_none) == 1 and has_none:
                return cls.optional(cls.of(non_none[0]))
            sub_doms = [cls.of(a) for a in non_none]
            sub_strats = [d.to_strategy() for d in sub_doms]
            comb_strat = st.one_of(*sub_strats)
            if has_none:
                comb_strat = st.one_of(st.none(), comb_strat)
            return Domain[Any](
                strategy=comb_strat,
                validator=lambda val: (val is None if has_none else False) or any(d.validate(val) for d in sub_doms),
            )

        if target_cls is None or target_cls is type(None):
            return Domain[Any](
                strategy=st.none(),
                validator=lambda val: val is None,
            )

        actual_cls: Any = target_cls
        origin = typing.get_origin(target_cls)
        check_cls = origin if (origin is not None and origin is not typing.Union) else actual_cls
        while hasattr(check_cls, "__supertype__"):
            check_cls = getattr(check_cls, "__supertype__")
        while hasattr(actual_cls, "__supertype__"):
            actual_cls = getattr(actual_cls, "__supertype__")
        strat: Any
        if actual_cls is bool:
            strat = st.booleans()
        elif actual_cls is int:
            strat = st.integers()
        elif actual_cls is float:
            strat = st.floats(allow_nan=False, allow_infinity=False)
        elif actual_cls is str:
            strat = st.text(**kwargs)
        else:
            try:
                strat = st.builds(actual_cls)
            except Exception:
                try:
                    strat = st.from_type(actual_cls)
                except Exception:
                    strat = st.from_type(check_cls)
        if validator is not None:
            if _is_strategy(strat):
                strat = strat.filter(validator)

            def _type_and_pred_val(val: Any) -> bool:
                if check_cls is int and isinstance(val, bool):
                    return False
                return isinstance(val, check_cls) and bool(validator(val))

            return Domain[Any](strategy=strat, validator=_type_and_pred_val)
        return Domain[Any](
            strategy=strat,
            validator=lambda val: (not isinstance(val, bool) if check_cls is int else True) and isinstance(val, check_cls),
        )

    @classmethod
    def tuple_of(cls, *elem_domains: Any) -> Domain[Tuple[Any, ...]]:
        from hypothesis import strategies as st
        strats = [d.to_strategy() if isinstance(d, Domain) else d for d in elem_domains]
        tuple_strat = st.tuples(*strats)

        def _tuple_val(val: Any) -> bool:
            if not isinstance(val, tuple) or len(val) != len(elem_domains):
                return False
            for elem, d in zip(val, elem_domains):
                if isinstance(d, Domain) and not d.validate(elem):
                    return False
            return True

        return Domain[Tuple[Any, ...]](strategy=tuple_strat, validator=_tuple_val)

    @classmethod
    def object(cls, target_cls: Type[T], **field_domains: Any) -> Domain[T]:
        from hypothesis import strategies as st

        def _obj_strat(draw: Any) -> T:
            if not field_domains:
                return draw(st.builds(target_cls))
            kwargs: dict[str, Any] = {}
            for k, spec in field_domains.items():
                dom = cls.of(spec)
                kwargs[k] = _draw_from_domain(dom, draw)
            return target_cls(**kwargs)

        def _obj_val(val: Any) -> bool:
            if not isinstance(val, target_cls):
                return False
            for k, spec in field_domains.items():
                if not hasattr(val, k):
                    return False
                dom = cls.of(spec)
                if not dom.validate(getattr(val, k)):
                    return False
            return True

        return Domain[T](strategy=_obj_strat, validator=_obj_val)

    @classmethod
    def newtype(cls, newtype_cls: Any, inner_domain: Any) -> Domain[Any]:
        inner = cls.of(inner_domain)
        return Domain[Any](
            strategy=lambda draw: newtype_cls(_draw_from_domain(inner, draw)),
            validator=lambda val: inner.validate(val),
        )

    @classmethod
    def list_of(cls, elem_domain: Union[Domain[E], Type[E]], min_size: int = 0, max_size: int = 5, unique: bool = False) -> Domain[List[E]]:
        from hypothesis import strategies as st
        elem = cls.of(elem_domain)
        elem_strat = elem.to_strategy()
        if _is_strategy(elem_strat):
            if getattr(elem_strat, "is_empty", False):
                if min_size == 0:
                    strat: Any = st.just([])
                else:
                    strat = st.nothing()
            else:
                strat = st.lists(elem_strat, min_size=min_size, max_size=max_size, unique=unique)
        else:
            def _list_strat(draw: Any) -> List[Any]:
                sz = draw(st.integers(min_value=min_size, max_value=max_size))
                res: list[Any] = []
                attempts = 0
                while len(res) < sz and attempts < sz * 10 + 10:
                    attempts += 1
                    item = _draw_from_domain(elem, draw)
                    if unique and item in res:
                        continue
                    res.append(item)
                return res

            strat = _list_strat

        def _list_val(val: Any) -> bool:
            if not isinstance(val, list):
                return False
            if len(val) < min_size or len(val) > max_size:
                return False
            if unique and len(set(val)) != len(val):
                return False
            return all(elem.validate(x) for x in val)

        return Domain[List[E]](strategy=strat, validator=_list_val)

    @classmethod
    def set_of(cls, elem_domain: Union[Domain[E], Type[E]], min_size: int = 0, max_size: int = 5) -> Domain[Set[E]]:
        from hypothesis import strategies as st
        elem = cls.of(elem_domain)
        elem_strat = elem.to_strategy()
        if _is_strategy(elem_strat):
            if getattr(elem_strat, "is_empty", False):
                if min_size == 0:
                    strat: Any = st.just(set())
                else:
                    strat = st.nothing()
            else:
                strat = st.sets(elem_strat, min_size=min_size, max_size=max_size)
        else:
            def _set_strat(draw: Any) -> Set[Any]:
                sz = draw(st.integers(min_value=min_size, max_value=max_size))
                res: set[Any] = set()
                attempts = 0
                while len(res) < sz and attempts < sz * 10 + 10:
                    attempts += 1
                    res.add(_draw_from_domain(elem, draw))
                return res

            strat = _set_strat

        def _set_val(val: Any) -> bool:
            if not isinstance(val, (set, frozenset)):
                return False
            if len(val) < min_size or len(val) > max_size:
                return False
            return all(elem.validate(x) for x in val)

        return Domain[Set[E]](strategy=strat, validator=_set_val)

    @classmethod
    def mapping_of(cls, key_domain: Union[Domain[K], Type[K]], val_domain: Union[Domain[V], Type[V]], min_size: int = 0, max_size: int = 5) -> Domain[Dict[K, V]]:
        from hypothesis import strategies as st
        k_dom = cls.of(key_domain)
        v_dom = cls.of(val_domain)
        k_strat = k_dom.to_strategy()
        v_strat = v_dom.to_strategy()
        if _is_strategy(k_strat) and _is_strategy(v_strat):
            if getattr(k_strat, "is_empty", False) or getattr(v_strat, "is_empty", False):
                if min_size == 0:
                    strat: Any = st.just({})
                else:
                    strat = st.nothing()
            else:
                strat = st.dictionaries(k_strat, v_strat, min_size=min_size, max_size=max_size)
        else:
            def _map_strat(draw: Any) -> Dict[Any, Any]:
                sz = draw(st.integers(min_value=min_size, max_value=max_size))
                res: dict[Any, Any] = {}
                attempts = 0
                while len(res) < sz and attempts < sz * 10 + 10:
                    attempts += 1
                    k = _draw_from_domain(k_dom, draw)
                    v = _draw_from_domain(v_dom, draw)
                    res[k] = v
                return res

            strat = _map_strat

        def _map_val(val: Any) -> bool:
            if not isinstance(val, dict):
                return False
            if len(val) < min_size or len(val) > max_size:
                return False
            return all(k_dom.validate(k) and v_dom.validate(v) for k, v in val.items())

        return Domain[Dict[K, V]](strategy=strat, validator=_map_val)

    @classmethod
    def optional(cls, inner_domain: Union[Domain[E], Type[E]]) -> Domain[Optional[E]]:
        from hypothesis import strategies as st
        inner = cls.of(inner_domain)
        inner_strat = inner.to_strategy()
        if _is_strategy(inner_strat):
            if getattr(inner_strat, "is_empty", False):
                strat: Any = st.none()
            else:
                strat = st.one_of(st.none(), inner_strat)
        else:
            strat = lambda draw: None if draw(st.booleans()) else _draw_from_domain(inner, draw)
        return Domain[Optional[E]](
            strategy=strat,
            validator=lambda val: val is None or inner.validate(val),
        )

    @classmethod
    def none(cls) -> Domain[None]:
        from hypothesis import strategies as st
        return Domain[None](
            strategy=st.none(),
            validator=lambda val: val is None,
        )

    @classmethod
    def boolean(cls) -> Domain[bool]:
        from hypothesis import strategies as st
        return Domain[bool](
            strategy=st.booleans(),
            validator=lambda val: isinstance(val, bool),
        )

    @classmethod
    def text(cls, min_size: int = 0, max_size: Optional[int] = None, alphabet: Any = None) -> Domain[str]:
        from hypothesis import strategies as st
        kwargs: dict[str, Any] = {"min_size": min_size}
        if max_size is not None:
            kwargs["max_size"] = max_size
        if alphabet is not None:
            kwargs["alphabet"] = alphabet
        return Domain[str](
            strategy=st.text(**kwargs),
            validator=lambda val: isinstance(val, str) and len(val) >= min_size and (max_size is None or len(val) <= max_size),
        )

    @classmethod
    def perturb(
        cls,
        anchor: Any,
        mutations: Sequence[Any],
        validator: Callable[[Any], bool],
    ) -> Domain[T]:
        """Relational domain derived constructively from an anchor via targeted mutations."""
        from hypothesis import strategies as st

        def _perturb_strat(draw_fn: Any) -> Any:
            if not mutations:
                return anchor
            mut_fn = draw_fn(st.sampled_from(tuple(mutations)))
            if callable(mut_fn) and not _is_strategy(mut_fn):
                import inspect
                try:
                    sig = inspect.signature(mut_fn)
                    takes_draw = len(sig.parameters) >= 2
                except (ValueError, TypeError):
                    takes_draw = False
                if takes_draw:
                    return mut_fn(anchor, draw_fn)
                return mut_fn(anchor)
            elif _is_strategy(mut_fn):
                return draw_fn(mut_fn)
            return mut_fn

        return Domain[T](
            strategy=_perturb_strat,
            validator=validator,
        )

    @classmethod
    def required(cls, name: str = "") -> Domain[Any]:
        """Unresolved domain placeholder that fails at runtime if left unspecialized."""
        msg = (
            f"Pretense transition parameter '{name}' requires an explicit Domain specification."
            if name
            else "Pretense transition parameter requires an explicit Domain specification."
        )

        def _fail_strat(*_args: Any, **_kwargs: Any) -> Any:
            raise NotImplementedError(msg)

        def _fail_val(*_args: Any, **_kwargs: Any) -> bool:
            raise NotImplementedError(msg)

        return Domain[Any](strategy=_fail_strat, validator=_fail_val)

    @classmethod
    def of(cls, val: Any) -> Domain[Any]:
        """Promotes native Python objects, strategies, or callables to a Domain."""
        import typing
        if val is typing.Any:
            return cls.any()
        if isinstance(val, Domain):
            return val
        if isinstance(val, Expr):
            return cls.just(val)
        if isinstance(val, set):
            return cls.set(val)
        if isinstance(val, range):
            return cls.range(val.start, val.stop, val.step)
        import re
        if isinstance(val, re.Pattern):
            return cls.regex(val)
        if typing.get_origin(val) is not None:
            return cls.type(val)
        if isinstance(val, type):
            return cls.type(val)
        if _is_strategy(val):
            return cls(strategy=val, validator=None)
        if isinstance(val, (list, tuple)) and not callable(val):
            return cls.set(val)
        if callable(val):
            return cls(strategy=val, validator=None)
        return cls.just(val)


def _derive_expr(name: str, deps: Sequence[Any], eval_fn: Callable[[], Any]) -> Expr[Any]:
    expr: Expr[Any] = Expr(name=name, is_return=False)
    expr._eval_fn = eval_fn
    expr._deps = tuple(d for d in deps if isinstance(d, Expr))
    return expr


class Expr(Generic[T]):
    """Lifted symbolic parameter or return outcome expression for a state transition."""

    def __init__(self, name: str = "", is_return: bool = False) -> None:
        self.name: str = name
        self.is_return: bool = is_return
        self._constraint: Any = NotBound
        self._raised: Optional[Tuple[Type[BaseException], Any]] = None
        self._val: Any = NotBound
        self._eval_fn: Optional[Callable[[], Any]] = None
        self._deps: Tuple[Expr[Any], ...] = ()

    def constrain(self, domain_or_val: Any) -> None:
        if self._raised is not None:
            raise ValueError(
                f"Expr '{self.name}' cannot declare both constrain(...) and raises(...)."
            )
        self._constraint = domain_or_val

    def raises(self, exc_type: Type[BaseException], match: Any = "") -> None:
        if self._constraint is not NotBound:
            raise ValueError(
                f"Expr '{self.name}' cannot declare both constrain(...) and raises(...)."
            )
        self._raised = (exc_type, match)

    def is_bound(self) -> bool:
        if self._eval_fn is not None:
            return all(d.is_bound() for d in self._deps)
        return not isinstance(self._val, NotBoundType)

    def value(self) -> T:
        if self._eval_fn is not None:
            if not self.is_bound():
                raise PretenseSpecificationError(
                    f"Cannot call .value() on unbound derived Expr '{self.name}' during antecedent/constraint evaluation; "
                    f"access .value() only inside `if ctx.updates:`, `if ctx.target:`, or a deferred lambda."
                )
            return cast(T, self._eval_fn())
        if isinstance(self._val, NotBoundType):
            raise PretenseSpecificationError(
                f"Cannot call .value() on unbound Expr '{self.name}' during antecedent/constraint evaluation; "
                f"access .value() only inside `if ctx.updates:`, `if ctx.target:`, or a deferred lambda."
            )
        return cast(T, self._val)

    def __add__(self, other: Any) -> Expr[Any]:
        return _derive_expr(
            f"({self.name} + {other!r})",
            (self, other),
            lambda: self.value() + (other.value() if isinstance(other, Expr) else other),
        )

    def __radd__(self, other: Any) -> Expr[Any]:
        return _derive_expr(
            f"({other!r} + {self.name})",
            (other, self),
            lambda: (other.value() if isinstance(other, Expr) else other) + self.value(),
        )

    def __sub__(self, other: Any) -> Expr[Any]:
        return _derive_expr(
            f"({self.name} - {other!r})",
            (self, other),
            lambda: self.value() - (other.value() if isinstance(other, Expr) else other),
        )

    def __rsub__(self, other: Any) -> Expr[Any]:
        return _derive_expr(
            f"({other!r} - {self.name})",
            (other, self),
            lambda: (other.value() if isinstance(other, Expr) else other) - self.value(),
        )

    def __mul__(self, other: Any) -> Expr[Any]:
        return _derive_expr(
            f"({self.name} * {other!r})",
            (self, other),
            lambda: self.value() * (other.value() if isinstance(other, Expr) else other),
        )

    def __rmul__(self, other: Any) -> Expr[Any]:
        return _derive_expr(
            f"({other!r} * {self.name})",
            (other, self),
            lambda: (other.value() if isinstance(other, Expr) else other) * self.value(),
        )

    def __getattr__(self, attr: str) -> Expr[Any]:
        if attr.startswith("_"):
            raise AttributeError(attr)
        return _derive_expr(
            f"{self.name}.{attr}",
            (self,),
            lambda: getattr(self.value(), attr),
        )

    def __getitem__(self, key: Any) -> Expr[Any]:
        return _derive_expr(
            f"{self.name}[{key!r}]",
            (self, key),
            lambda: cast(Any, self.value())[key.value() if isinstance(key, Expr) else key],
        )


class _RequirementFailed(Exception):
    """Internal control-flow signal short-circuiting Pass 1 when a requirement fails."""


class TransitionContext(Generic[Target, P, R]):
    """Context for specifying requires, argument, return, ensures, and update handlers for a transition."""

    def __init__(self, target: Any = None, name: Optional[str] = None, is_seeding: bool = False) -> None:
        self.updates: bool = False
        self.target: Optional[Target] = target
        self.check: EnsuresCheck = EnsuresCheck()
        self.name: Optional[str] = name
        self.is_seeding: bool = is_seeding
        self.predicate: Optional[Callable[..., Any]] = None
        self.domains: list[tuple[str, Any]] = []
        self.returns_fn: Optional[Any] = None
        self.ensures_fn: Optional[Callable[..., Any]] = None
        self.consequent_fn: Optional[Callable[..., Any]] = None
        self.expected_exception: Optional[Tuple[Type[Exception], str]] = None
        self._req_check: RequiresCheck = RequiresCheck()
        self._in_pass1: bool = False

    def requires(self, fn: Union[bool, Callable[[RequiresCheck], Any], Callable[[], bool]], reason: str = "") -> None:
        if callable(fn):
            self.predicate = fn
            if self._in_pass1:
                import inspect
                try:
                    sig = inspect.signature(fn)
                    param_count = len(sig.parameters)
                except (ValueError, TypeError):
                    param_count = 0
                if param_count >= 1:
                    res = cast(Any, fn)(self._req_check)
                    if res is False:
                        self._req_check(False, reason or "Precondition returned False")
                else:
                    ok = bool(cast(Any, fn)())
                    if not ok:
                        self._req_check(False, reason or "Precondition returned False")
                if not self._req_check.ok:
                    raise _RequirementFailed()
        else:
            if self._in_pass1:
                if not bool(fn):
                    self._req_check(False, reason or "Precondition returned False")
                    raise _RequirementFailed()
            else:
                val = bool(fn)
                self.predicate = lambda: val

    def antecedent(self, predicate: Union[bool, Callable[[], bool]], reason: str = "") -> None:
        self.requires(predicate, reason=reason)

    def check_equal(self, actual: Any, expected: Any, msg: str = "") -> None:
        self.check.equal(actual, expected, msg=msg)

    def get(self, singleton_type: Type[T]) -> T:
        return self.check.get(singleton_type)

    def arguments(self, *domains: Any, **kw_domains: Any) -> None:
        dom_list: list[tuple[str, Any]] = []
        for i, d in enumerate(domains):
            dom_list.append((f"arg_{i}", d))
        for k, v in kw_domains.items():
            dom_list.append((k, v))
        self.domains = dom_list

    @overload
    def returns(self, fn: Callable[P, Union[R, Outcome[R], Outcome[Any], None]]) -> None: ...

    @overload
    def returns(self, fn: Callable[[], Union[R, Outcome[R], Outcome[Any], None]]) -> None: ...

    @overload
    def returns(self, fn: Callable[..., Union[R, Outcome[R], Outcome[Any], None]]) -> None: ...

    @overload
    def returns(self, fn: Union[R, Outcome[R], Outcome[Any]]) -> None: ...

    def returns(self, fn: Any) -> None:
        if self.expected_exception is not None:
            t_name = f" '{self.name}'" if self.name else ""
            raise ValueError(
                f"Transition{t_name} cannot declare both ctx.raises(...) and ctx.returns(...). "
                f"Use ctx.raises(...) for transitions that unconditionally raise an exception, "
                f"or return Raised(...) dynamically from ctx.returns(...)."
            )
        self.returns_fn = fn

    def ensures(self, fn: Callable[..., Any]) -> None:
        self.ensures_fn = fn

    @overload
    def update(self, fn: Callable[Concatenate[Any, P], Any]) -> None: ...

    @overload
    def update(self, fn: Callable[[Any], Any]) -> None: ...

    @overload
    def update(self, fn: Callable[[], Any]) -> None: ...

    @overload
    def update(self, fn: Callable[..., Any]) -> None: ...

    def update(self, fn: Callable[..., Any]) -> None:
        self.consequent_fn = fn

    @overload
    def consequent(self, fn: Callable[Concatenate[Any, P], Any]) -> None: ...

    @overload
    def consequent(self, fn: Callable[[Any], Any]) -> None: ...

    @overload
    def consequent(self, fn: Callable[[], Any]) -> None: ...

    @overload
    def consequent(self, fn: Callable[..., Any]) -> None: ...

    def consequent(self, fn: Callable[..., Any]) -> None:
        self.update(fn)

    def raises(self, exc_type: Type[Exception], match: str = "") -> None:
        if self.returns_fn is not None:
            t_name = f" '{self.name}'" if self.name else ""
            raise ValueError(
                f"Transition{t_name} cannot declare both ctx.raises(...) and ctx.returns(...). "
                f"Use ctx.raises(...) for transitions that unconditionally raise an exception, "
                f"or return Raised(...) dynamically from ctx.returns(...)."
            )
        self.expected_exception = (exc_type, match)


class transition:
    """Decorator registering a transition method against a target singleton operation."""

    def __init__(
        self,
        target: Optional[Any] = None,
        *,
        name: Optional[str] = None,
        is_seeding: bool = False,
        seeding: bool = False,
    ) -> None:
        self.target: Optional[Any] = target
        self.name: Optional[str] = name
        self.is_seeding: bool = is_seeding or seeding
        self.fn: Optional[Callable[..., Any]] = None

    @classmethod
    def seeding(cls, fn: Optional[Callable[..., Any]] = None, *, name: Optional[str] = None) -> Any:
        inst = cls(name=name, is_seeding=True)
        if fn is not None and callable(fn):
            return inst(fn)
        return inst

    def __call__(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        self.fn = fn
        tr_self = self
        target_fn = fn

        try:
            src = inspect.getsource(fn)
            if "ensure_raises" in src:
                import ast
                import textwrap

                class _EnsureRaisesTransformer(ast.NodeTransformer):
                    def visit_Expr(self, node: ast.Expr) -> ast.AST:
                        if isinstance(node.value, ast.Call):
                            call = node.value
                            func = call.func
                            if (isinstance(func, ast.Name) and func.id == "ensure_raises") or (
                                isinstance(func, ast.Attribute) and func.attr == "ensure_raises"
                            ):
                                if len(call.args) >= 2:
                                    call_expr = call.args[0]
                                    exc_type = call.args[1]
                                    try_stmt = ast.Try(
                                        body=[ast.Expr(value=call_expr)],
                                        handlers=[
                                            ast.ExceptHandler(
                                                type=exc_type,
                                                name="_exc",
                                                body=[
                                                    ast.Expr(
                                                        value=ast.Call(
                                                            func=ast.Attribute(
                                                                value=ast.Name(id="_last_raised_exc", ctx=ast.Load()),
                                                                attr="set",
                                                                ctx=ast.Load(),
                                                            ),
                                                            args=[ast.Name(id="_exc", ctx=ast.Load())],
                                                            keywords=[],
                                                        )
                                                    ),
                                                    ast.Pass(),
                                                ],
                                            )
                                        ],
                                        orelse=[
                                            ast.Raise(
                                                exc=ast.Call(
                                                    func=ast.Name(id="AssertionError", ctx=ast.Load()),
                                                    args=[ast.Constant(value="Expected exception was not raised")],
                                                    keywords=[],
                                                )
                                            )
                                        ],
                                        finalbody=[],
                                    )
                                    return ast.copy_location(try_stmt, node)
                        return node

                dedented = textwrap.dedent(src)
                tree = ast.parse(dedented)
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        node.decorator_list = []
                new_tree = _EnsureRaisesTransformer().visit(tree)
                ast.fix_missing_locations(new_tree)
                code_obj = compile(new_tree, inspect.getfile(fn), "exec")
                caller_frame = inspect.currentframe()
                caller_locals = caller_frame.f_back.f_locals if caller_frame and caller_frame.f_back else {}
                temp_ns = dict(fn.__globals__)
                temp_ns.setdefault("require", require)
                temp_ns.setdefault("require_arg", require_arg)
                temp_ns.setdefault("ensure", ensure)
                temp_ns.setdefault("ensure_ret", ensure_ret)
                temp_ns.setdefault("ensure_raises", ensure_raises)
                temp_ns.setdefault("_last_raised_exc", _last_raised_exc)
                temp_ns.setdefault("Domain", Domain)
                temp_ns.setdefault("PretenseSpecificationError", PretenseSpecificationError)
                temp_ns.update(caller_locals)
                exec(code_obj, temp_ns)
                target_fn = temp_ns.get(fn.__name__, fn)


        except Exception:
            target_fn = fn



        try:
            sig = inspect.signature(fn)
            params = list(sig.parameters.values())
            is_linear = bool(not params or params[-1].name != "ctx")
        except Exception:
            is_linear = False

        def method_proxy(instance: Any, *args: Any, **kwargs: Any) -> Any:
            if args and not kwargs and isinstance(args[-1], TransitionContext):
                return fn(instance, *args)
            if is_linear and tr_self.is_seeding:
                return target_fn(instance, *args, **kwargs)
            tr_name = tr_self.name or fn.__name__
            return instance.dispatch_transition(tr_name, *args, **kwargs)

        setattr(method_proxy, "__transition_spec__", self)
        setattr(method_proxy, "__is_linear__", is_linear)
        setattr(method_proxy, "__target_fn__", target_fn)
        method_proxy.__name__ = fn.__name__
        method_proxy.__doc__ = fn.__doc__
        return method_proxy


def _build_transition_from_context(ctx: TransitionContext[Any, Any, Any]) -> Transition:
    tr_name = ctx.name or getattr(ctx.target, "__name__", None) or getattr(getattr(ctx.target, "fget", None), "__name__", "transition")
    t = Transition(
        name=tr_name,
        target=ctx.target,
        is_seeding=ctx.is_seeding,
    )
    if ctx.predicate is not None:
        pred = ctx.predicate
        import inspect
        try:
            sig = inspect.signature(pred)
            param_count = len(sig.parameters)
        except (ValueError, TypeError):
            param_count = 0

        if param_count >= 1:
            def req_wrapper(state: Any, this: Any) -> bool:
                chk = RequiresCheck()
                setattr(req_wrapper, "last_check", chk)
                res = pred(chk)
                if res is False:
                    chk.ok = False
                return chk.ok
            setattr(req_wrapper, "last_check", None)
            t.requirements.append(req_wrapper)
        else:
            def req_wrapper_noarg(state: Any, this: Any) -> bool:
                chk = RequiresCheck()
                setattr(req_wrapper_noarg, "last_check", chk)
                ok = bool(pred())
                if not ok:
                    chk(False, "Precondition returned False")
                return ok
            setattr(req_wrapper_noarg, "last_check", None)
            t.requirements.append(req_wrapper_noarg)

    domains = ctx.domains

    def args_fn(state: Any, this: Any, *args: Any, **kwargs: Any) -> Any:
        is_generation = (not args and not kwargs) or (args and all(isinstance(a, NotBoundType) for a in args))

        if domains is None or len(domains) == 0:
            if is_generation:
                return ()
            if not args and not kwargs:
                return ()
            return None

        if is_generation:
            draw = get_current_draw()
            resolved_args: list[Any] = []
            for name, item in domains:
                if callable(item) and not isinstance(item, Domain) and not _is_strategy(item):
                    concrete_domain = Domain.of(item(*resolved_args))
                else:
                    concrete_domain = Domain.of(item)
                strat = concrete_domain.to_strategy()
                if callable(strat) and not _is_strategy(strat):
                    import inspect
                    try:
                        sig = inspect.signature(strat)
                        params = list(sig.parameters.values())
                        takes_draw = len(params) >= 1 and params[0].kind in (
                            inspect.Parameter.POSITIONAL_ONLY,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        )
                    except (ValueError, TypeError):
                        takes_draw = False

                    if takes_draw:
                        effective_draw = draw if draw is not None else (lambda s: _resolve_argument_value(s, None))
                        val = strat(effective_draw)
                    else:
                        val = strat()
                    val = _resolve_argument_value(val, draw)
                else:
                    val = _resolve_argument_value(strat, draw)
                resolved_args.append(val)
            return tuple(resolved_args)
        else:
            bound_vals: list[Any] = []
            target = ctx.target
            target_callable = target if (target is not None and callable(target)) else (
                ctx.returns_fn if (ctx.returns_fn is not None and callable(ctx.returns_fn)) else None
            )
            has_leading_res = False
            if target_callable is None and ctx.consequent_fn is not None and callable(ctx.consequent_fn):
                target_callable = ctx.consequent_fn
                has_leading_res = True

            if target_callable is not None:
                import inspect
                try:
                    sig = inspect.signature(target_callable)
                    params = list(sig.parameters.values())
                    if has_leading_res:
                        try:
                            bound = sig.bind_partial(None, *args, **kwargs)
                        except TypeError:
                            bound = sig.bind_partial(*args, **kwargs)
                    elif params and params[0].name in ("self", "cls"):
                        try:
                            bound = sig.bind_partial(None, *args, **kwargs)
                        except TypeError:
                            bound = sig.bind_partial(*args, **kwargs)
                    else:
                        bound = sig.bind_partial(*args, **kwargs)
                    bound.apply_defaults()
                    param_names = [p.name for p in params if p.name not in ("self", "cls", "res")]
                    for i, (name, _) in enumerate(domains):
                        if name in bound.arguments:
                            bound_vals.append(bound.arguments[name])
                        elif i < len(param_names) and param_names[i] in bound.arguments:
                            bound_vals.append(bound.arguments[param_names[i]])
                        elif i < len(args):
                            bound_vals.append(args[i])
                        elif name in kwargs:
                            bound_vals.append(kwargs[name])
                except (TypeError, ValueError):
                    bound_vals = []
            if not bound_vals:
                for i, (name, _) in enumerate(domains):
                    if i < len(args):
                        bound_vals.append(args[i])
                    elif name in kwargs:
                        bound_vals.append(kwargs[name])

            if len(bound_vals) < len(domains):
                for i in range(len(bound_vals), len(domains)):
                    d_name, d_item = domains[i]
                    if d_name in kwargs:
                        bound_vals.append(kwargs[d_name])
                    elif isinstance(d_item, Domain) and d_item.default is not NotBound:
                        bound_vals.append(d_item.default)
                    else:
                        return None

            if len(bound_vals) != len(domains):
                return None
            collected_domain_vals = list(bound_vals)
            for i, (name, item) in enumerate(domains):
                val = bound_vals[i]
                if callable(item) and not isinstance(item, Domain) and not _is_strategy(item):
                    concrete_domain = Domain.of(item(*collected_domain_vals[:i]))
                else:
                    concrete_domain = Domain.of(item)
                if not concrete_domain.validate(val):
                    return None
            return tuple(bound_vals)

    t.args_fn = args_fn

    exp_exc = ctx.expected_exception
    ret_fn = ctx.returns_fn

    def return_fn(state: Any, this: Any, *args: Any, outcome: Any = NotBound) -> Any:
        if exp_exc is not None:
            exc_cls, match = exp_exc
            if outcome is not NotBound:
                if isinstance(outcome, Raised) and isinstance(outcome.exc, exc_cls):
                    if match and match not in str(outcome.exc):
                        return None
                    return outcome
                return None
            return Raised(_safe_instantiate_exception(exc_cls, match))

        if ret_fn is not None:
            import inspect
            try:
                sig = inspect.signature(ret_fn)
                params = list(sig.parameters.values())
                takes_state_this = len(params) >= 2 and params[0].name in ("state", "st") and params[1].name in ("this", "sm", "self")
                has_outcome_param = "outcome" in sig.parameters
            except (ValueError, TypeError):
                takes_state_this = False
                has_outcome_param = False

            if takes_state_this:
                kw = {"outcome": outcome} if has_outcome_param and outcome is not NotBound else {}
                raw_val = ret_fn(state, this, *args, **kw)
            else:
                raw_val = ret_fn(*args) if callable(ret_fn) else ret_fn

            if isinstance(raw_val, Raised):
                if outcome is not NotBound:
                    if isinstance(outcome, Raised) and type(outcome.exc) is type(raw_val.exc):
                        return outcome
                    return None
                return raw_val

            expected_val = raw_val.val if isinstance(raw_val, Value) else raw_val
            if outcome is not NotBound:
                if isinstance(outcome, Value) and outcome.val == expected_val:
                    return outcome
                elif outcome == expected_val or outcome == raw_val:
                    return Value(expected_val)
                return outcome if isinstance(outcome, Outcome) else Value(outcome)
            return raw_val if isinstance(raw_val, Outcome) else Value(raw_val)
        else:
            if outcome is not NotBound:
                return outcome if isinstance(outcome, Outcome) else Value(outcome)
            return Value(None)

    t.return_fn = return_fn

    cons = ctx.consequent_fn

    def provider(state: Any, this: Any, *args: Any, result: Any = None) -> None:
        if cons is not None:
            import inspect
            params: list[Any] = []
            takes_state_this = False
            try:
                sig = inspect.signature(cons)
                params = list(sig.parameters.values())
                takes_state_this = len(params) >= 2 and params[0].name in ("state", "st") and params[1].name in ("this", "sm", "self")
            except (ValueError, TypeError):
                takes_state_this = False

            if takes_state_this:
                cons(state, this, *args, result=result)
            else:
                param_count = len(params)
                if param_count == 0:
                    cons()
                elif param_count == 1:
                    cons(result)
                else:
                    cons(result, *args)

    t.provider = provider

    raw_ensure = ctx.ensures_fn
    if raw_ensure is not None:
        def ensure_wrapper(res: Any, target: Any, check: EnsuresCheck, *args: Any, **kwargs: Any) -> None:
            import inspect
            try:
                sig = inspect.signature(raw_ensure)
                params = list(sig.parameters.values())
            except (ValueError, TypeError):
                params = []

            param_count = len(params)
            has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)

            if param_count == 0:
                raw_ensure()
            elif param_count == 1:
                if params[0].name == "check":
                    raw_ensure(check)
                else:
                    raw_ensure(res)
            elif param_count == 2:
                if params[1].name == "check":
                    raw_ensure(res, check)
                elif params[0].name == "check":
                    raw_ensure(check, res)
                else:
                    raw_ensure(res, target)
            elif param_count == 3 and not has_varargs:
                raw_ensure(res, target, check)
            else:
                call_args = [res, target, check] + list(args)
                if not has_varargs:
                    raw_ensure(*call_args[:param_count])
                else:
                    raw_ensure(res, target, check, *args, **kwargs)

        t.ensure_fn = ensure_wrapper

    t.ctx = ctx
    t._is_lifted = False
    return t


def _is_lifted_transition_fn(raw_fn: Callable[..., Any]) -> bool:
    import inspect
    try:
        sig = inspect.signature(raw_fn)
        params = [p for p in sig.parameters.values() if p.name != "self"]
    except (ValueError, TypeError):
        return False
    if len(params) >= 2:
        return True
    code_obj = getattr(raw_fn, "__code__", None)
    co_names = getattr(code_obj, "co_names", ()) if code_obj is not None else ()
    if "updates" in co_names or "check_equal" in co_names:
        return True
    legacy_calls = {"arguments", "returns", "consequent", "update", "ensures", "raises"}
    if not any(c in co_names for c in legacy_calls):
        return True
    return False


def _constraint_to_domain(constraint: Any) -> Domain[Any]:
    if isinstance(constraint, Domain):
        return constraint
    if isinstance(constraint, Expr):
        return Domain.just(constraint)
    if isinstance(constraint, type):
        return Domain.type(constraint)
    if _is_strategy(constraint):
        return Domain(strategy=constraint, validator=None)
    if callable(constraint):
        return Domain(strategy=constraint, validator=None)
    return Domain.just(constraint)


def _build_lifted_transition(
    sm_instance: Any,
    raw_fn: Callable[..., Any],
    spec: transition,
    tr_name: str,
) -> Transition:
    import inspect
    sig = inspect.signature(raw_fn)
    params = [p for p in sig.parameters.values() if p.name != "self"]
    expr_params = params[:-1] if params else []

    if not expr_params:
        arg_params: list[inspect.Parameter] = []
        has_explicit_ret = False
    elif expr_params[-1].name in ("ret", "result", "outcome", "return_val"):
        arg_params = list(expr_params[:-1])
        has_explicit_ret = True
    elif spec.is_seeding:
        arg_params = list(expr_params)
        has_explicit_ret = False
    elif spec.target is not None:
        if isinstance(spec.target, property):
            target_arity = 0
        elif callable(spec.target):
            try:
                t_sig = inspect.signature(spec.target)
                t_params = [p for p in t_sig.parameters.values() if p.name not in ("self", "cls")]
                target_arity = len(t_params)
            except (ValueError, TypeError):
                target_arity = len(expr_params) - 1
        else:
            target_arity = len(expr_params) - 1
        if len(expr_params) == target_arity + 1:
            arg_params = list(expr_params[:-1])
            has_explicit_ret = True
        else:
            arg_params = list(expr_params)
            has_explicit_ret = False
    else:
        arg_params = list(expr_params)
        has_explicit_ret = False

    ret_param_name = expr_params[-1].name if has_explicit_ret else "ret"

    t = Transition(
        name=tr_name,
        target=spec.target,
        is_seeding=spec.is_seeding,
    )
    t._is_lifted = True
    last_ctx = TransitionContext(target=spec.target, name=tr_name, is_seeding=spec.is_seeding)
    t.ctx = last_ctx

    def _resolve_active_sm(state: Any, this: Any) -> Any:
        active = this if isinstance(this, StateMachine) else sm_instance
        if state is not None and hasattr(active, "state"):
            active.state = state
        return active

    def _run_pass1(state: Any, this: Any) -> Tuple[TransitionContext[Any, Any, Any], List[Expr[Any]], Expr[Any]]:
        active_sm = _resolve_active_sm(state, this)
        arg_exprs: List[Expr[Any]] = [Expr(name=p.name, is_return=False) for p in arg_params]
        ret_expr: Expr[Any] = Expr(name=ret_param_name, is_return=True)
        ctx = TransitionContext(target=None, name=tr_name, is_seeding=spec.is_seeding)
        ctx.updates = False
        ctx.target = None
        ctx._in_pass1 = True

        if not params:
            call_args: list[Any] = []
        elif has_explicit_ret:
            call_args = [*arg_exprs, ret_expr, ctx]
        else:
            call_args = [*arg_exprs, ctx]

        try:
            raw_fn(active_sm, *call_args)
        except _RequirementFailed:
            pass
        finally:
            ctx._in_pass1 = False

        if ret_expr._raised is not None:
            exc_t, exc_m = ret_expr._raised
            m_str = exc_m.pattern if hasattr(exc_m, "pattern") else str(exc_m or "")
            if isinstance(exc_t, type) and issubclass(exc_t, Exception):
                ctx.expected_exception = (exc_t, m_str)
        t.ctx = ctx
        return ctx, arg_exprs, ret_expr

    def req_wrapper(state: Any, this: Any) -> bool:
        ctx, _, _ = _run_pass1(state, this)
        setattr(req_wrapper, "last_check", ctx._req_check)
        return ctx._req_check.ok

    setattr(req_wrapper, "last_check", None)
    t.requirements.append(req_wrapper)

    def args_fn(state: Any, this: Any, *args: Any, **kwargs: Any) -> Any:
        is_generation = (not args and not kwargs) or (args and all(isinstance(a, NotBoundType) for a in args))
        ctx, arg_exprs, _ = _run_pass1(state, this)
        if not ctx._req_check.ok:
            return None

        if len(arg_exprs) == 0:
            if is_generation or (not args and not kwargs):
                return ()
            return None

        if is_generation:
            draw = get_current_draw()
            resolved_args: list[Any] = []
            for i, expr in enumerate(arg_exprs):
                if isinstance(expr._constraint, NotBoundType):
                    raise PretenseSpecificationError(
                        f"Transition '{tr_name}' parameter '{expr.name}' has no Domain constraint; "
                        f"call {expr.name}.constrain(...) to specify its domain."
                    )
                dom = _constraint_to_domain(expr._constraint)
                val = _draw_from_domain(dom, draw)
                expr._val = val
                resolved_args.append(val)
            return tuple(resolved_args)
        else:
            bound_vals: list[Any] = []
            if spec.target is not None and callable(spec.target):
                try:
                    t_sig = inspect.signature(spec.target)
                    t_params = list(t_sig.parameters.values())
                    if t_params and t_params[0].name in ("self", "cls"):
                        try:
                            bound = t_sig.bind_partial(None, *args, **kwargs)
                        except TypeError:
                            bound = t_sig.bind_partial(*args, **kwargs)
                    else:
                        bound = t_sig.bind_partial(*args, **kwargs)
                    bound.apply_defaults()
                    t_param_names = [p.name for p in t_params if p.name not in ("self", "cls")]
                    for i, p in enumerate(arg_params):
                        if p.name in bound.arguments:
                            bound_vals.append(bound.arguments[p.name])
                        elif i < len(t_param_names) and t_param_names[i] in bound.arguments:
                            bound_vals.append(bound.arguments[t_param_names[i]])
                        elif i < len(args):
                            bound_vals.append(args[i])
                        elif p.name in kwargs:
                            bound_vals.append(kwargs[p.name])
                        elif not isinstance(arg_exprs[i]._constraint, NotBoundType):
                            dom = _constraint_to_domain(arg_exprs[i]._constraint)
                            bound_vals.append(_draw_from_domain(dom, None))
                except (TypeError, ValueError):
                    bound_vals = []

            if not bound_vals:
                for i, p in enumerate(arg_params):
                    if i < len(args):
                        bound_vals.append(args[i])
                    elif p.name in kwargs:
                        bound_vals.append(kwargs[p.name])
                    elif p.default is not inspect.Parameter.empty:
                        bound_vals.append(p.default)
                    elif not isinstance(arg_exprs[i]._constraint, NotBoundType):
                        dom = _constraint_to_domain(arg_exprs[i]._constraint)
                        bound_vals.append(_draw_from_domain(dom, None))

            if len(bound_vals) != len(arg_exprs):
                return None

            for i, expr in enumerate(arg_exprs):
                val = bound_vals[i]
                expr._val = val
                if not isinstance(expr._constraint, NotBoundType):
                    dom = _constraint_to_domain(expr._constraint)
                    if not dom.validate(val):
                        return None
            return tuple(bound_vals)

    t.args_fn = args_fn

    def return_fn(state: Any, this: Any, *args: Any, outcome: Any = NotBound) -> Any:
        ctx, arg_exprs, ret_expr = _run_pass1(state, this)
        for i, val in enumerate(args):
            if i < len(arg_exprs):
                arg_exprs[i]._val = val

        raised_spec = ret_expr._raised if ret_expr._raised is not None else ctx.expected_exception
        if raised_spec is not None:
            exc_cls, match = raised_spec
            m_val: Any = match.value() if isinstance(match, Expr) else match
            if outcome is not NotBound:
                if isinstance(outcome, Raised) and isinstance(outcome.exc, exc_cls):
                    if m_val:
                        search_fn = getattr(m_val, "search", None)
                        if callable(search_fn):
                            if not search_fn(str(outcome.exc)):
                                return None
                        else:
                            import re
                            m_str = str(m_val)
                            if m_str not in str(outcome.exc) and not re.search(m_str, str(outcome.exc)):
                                return None
                    return outcome
                return None
            pat_attr = getattr(m_val, "pattern", None)
            m_str = str(pat_attr) if pat_attr is not None else str(m_val or "")
            return Raised(_safe_instantiate_exception(cast(Type[Exception], exc_cls), m_str))

        if not isinstance(ret_expr._constraint, NotBoundType):
            c = ret_expr._constraint
            if outcome is not NotBound:
                if callable(c) and not isinstance(c, type):
                    try:
                        c_sig = inspect.signature(c)
                        c_arity = len(c_sig.parameters)
                    except (ValueError, TypeError):
                        c_arity = 0
                    if c_arity == 0:
                        expected_c = c()
                        if isinstance(expected_c, Raised):
                            if isinstance(outcome, Raised) and isinstance(outcome.exc, type(expected_c.exc)):
                                return outcome
                            return None
                        if isinstance(outcome, Raised):
                            return None
                        actual_val = outcome.val if isinstance(outcome, Value) else outcome
                        expected_val = expected_c.val if isinstance(expected_c, Value) else expected_c
                        return (outcome if isinstance(outcome, Outcome) else Value(outcome)) if actual_val == expected_val else None
                if isinstance(outcome, Raised):
                    return None
                actual_val = outcome.val if isinstance(outcome, Value) else outcome
                if isinstance(c, Domain):
                    is_valid = c.validate(actual_val)
                elif _is_strategy(c):
                    is_valid = True
                elif isinstance(c, Expr):
                    is_valid = bool(actual_val == c.value())
                elif callable(c) and not isinstance(c, type):
                    is_valid = bool(c(actual_val))
                else:
                    is_valid = bool(actual_val == c)
                return (outcome if isinstance(outcome, Outcome) else Value(outcome)) if is_valid else None
            else:
                if isinstance(c, Domain):
                    synth_val = _draw_from_domain(c, get_current_draw())
                elif _is_strategy(c):
                    synth_val = _resolve_argument_value(c, get_current_draw())
                elif isinstance(c, Expr):
                    synth_val = c.value()
                elif callable(c) and not isinstance(c, type):
                    synth_val = c()
                else:
                    synth_val = c
                return synth_val if isinstance(synth_val, Outcome) else Value(synth_val)

        if outcome is not NotBound:
            if isinstance(outcome, Raised):
                return None
            return outcome if isinstance(outcome, Outcome) else Value(outcome)
        return Value(None)

    t.return_fn = return_fn

    def _exec_pass2(
        state: Any,
        this: Any,
        resolved_args: Sequence[Any],
        result_val: Any,
        do_updates: bool,
        target_obj: Any,
        check_obj: Optional[EnsuresCheck],
    ) -> None:
        active_sm = _resolve_active_sm(state, this)
        arg_exprs: List[Expr[Any]] = [Expr(name=p.name, is_return=False) for p in arg_params]
        for i, expr in enumerate(arg_exprs):
            if i < len(resolved_args):
                expr._val = resolved_args[i]
        ret_expr: Expr[Any] = Expr(name=ret_param_name, is_return=True)
        if isinstance(result_val, Raised):
            ret_expr._val = result_val.exc
        elif isinstance(result_val, Value):
            ret_expr._val = result_val.val
        else:
            ret_expr._val = result_val

        ctx = TransitionContext(target=target_obj, name=tr_name, is_seeding=spec.is_seeding)
        ctx.updates = do_updates
        ctx.target = target_obj
        ctx.check = check_obj if check_obj is not None else EnsuresCheck(getattr(active_sm, "singletons", None))
        ctx._in_pass1 = False

        if not params:
            call_args: list[Any] = []
        elif has_explicit_ret:
            call_args = [*arg_exprs, ret_expr, ctx]
        else:
            call_args = [*arg_exprs, ctx]

        raw_fn(active_sm, *call_args)

        if do_updates and ctx.consequent_fn is not None:
            cons = ctx.consequent_fn
            try:
                c_sig = inspect.signature(cons)
                c_arity = len(c_sig.parameters)
            except (ValueError, TypeError):
                c_arity = 0
            if c_arity == 0:
                cons()
            elif c_arity == 1:
                cons(ret_expr._val)
            else:
                cons(ret_expr._val, *resolved_args)

        if target_obj is not None and ctx.ensures_fn is not None:
            ens = ctx.ensures_fn
            try:
                e_sig = inspect.signature(ens)
                e_params = list(e_sig.parameters.values())
                e_arity = len(e_params)
            except (ValueError, TypeError):
                e_params = []
                e_arity = 0
            if e_arity == 0:
                ens()
            elif e_arity == 1:
                if e_params[0].name == "check":
                    ens(ctx.check)
                else:
                    ens(target_obj)
            elif e_arity == 2:
                ens(target_obj, ctx.check)
            else:
                ens(ret_expr._val, target_obj, ctx.check, *resolved_args[: max(0, e_arity - 3)])

    def provider(state: Any, this: Any, *args: Any, result: Any = None) -> None:
        _exec_pass2(state, this, args, result, do_updates=True, target_obj=None, check_obj=None)

    def ensure_wrapper(res: Any, target: Any, check: EnsuresCheck, *args: Any, **_kwargs: Any) -> None:
        _exec_pass2(sm_instance.state, sm_instance, args, res, do_updates=False, target_obj=target, check_obj=check)

    def _run_consequent(
        state: Any,
        this: Any,
        res: Any,
        target: Any,
        check: Optional[EnsuresCheck],
        *args: Any,
    ) -> None:
        _exec_pass2(state, this, args, res, do_updates=True, target_obj=target, check_obj=check)

    t.provider = provider
    t.ensure_fn = ensure_wrapper
    t._run_consequent = _run_consequent
    return t


def _resolve_suts_and_target(
    sut_fixture: Any,
    target_spec: Any,
    target_type: Optional[Any],
    suts_type: Optional[Any],
    fn_globals: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, Any]:
    globs = fn_globals or {}
    actual_t_type = globs.get(target_type) if isinstance(target_type, str) else target_type
    actual_s_type = globs.get(suts_type) if isinstance(suts_type, str) else suts_type

    target_obj: Any = None
    if isinstance(sut_fixture, dict):
        if actual_t_type is not None:
            target_obj = sut_fixture.get(actual_t_type)
        if target_obj is None and target_spec is not None:
            target_obj = _resolve_target_singleton(sut_fixture, target_spec)
        if target_obj is None and sut_fixture:
            target_obj = next(iter(sut_fixture.values()))
    else:
        target_obj = sut_fixture

    suts_obj: Any = None
    if actual_s_type not in (None, Any, object) and isinstance(actual_s_type, type):
        if isinstance(sut_fixture, actual_s_type):
            suts_obj = sut_fixture
        else:
            try:
                suts_obj = actual_s_type(target_obj)
            except Exception:
                try:
                    suts_obj = actual_s_type(target=target_obj)
                except Exception:
                    suts_obj = sut_fixture
    else:
        suts_obj = sut_fixture

    return target_obj, suts_obj


_LINEAR_PARSE_CACHE: Dict[Tuple[Callable[..., Any], str], Dict[str, Any]] = {}


def _parse_linear_transition(orig_fn: Callable[..., Any], spec: transition, attr_name: str) -> Dict[str, Any]:
    cache_key = (orig_fn, attr_name)
    cached = _LINEAR_PARSE_CACHE.get(cache_key)
    if cached is not None:
        res = dict(cached)
        res["target"] = spec.target
        return res

    sig = inspect.signature(orig_fn)
    params = list(sig.parameters.values())
    param_names = [p.name for p in params[1:]]
    target_type = None
    suts_type = None
    has_suts_param = False

    req_codes: List[Any] = []
    param_domains: Dict[str, Tuple[Any, Optional[Any]]] = {}

    try:
        src = textwrap.dedent(inspect.getsource(orig_fn))
        tree = ast.parse(src)
        fn_node = tree.body[0]
        if isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in fn_node.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call = stmt.value
                    func_name = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")
                    if func_name in ("require", "requires") and call.args:
                        cond_expr = ast.Expression(body=call.args[0])
                        code = compile(cond_expr, f"<{attr_name}_require_{len(req_codes)}>", "eval")
                        req_codes.append(code)
                    elif func_name == "require_arg" and len(call.args) >= 2:
                        arg_name_node = call.args[0]
                        arg_name = arg_name_node.id if isinstance(arg_name_node, ast.Name) else ""
                        domain_code = compile(ast.Expression(body=call.args[1]), f"<{attr_name}_dom_{arg_name}>", "eval")
                        pref_code = None
                        if len(call.args) >= 3:
                            pref_code = compile(ast.Expression(body=call.args[2]), f"<{attr_name}_pref_{arg_name}>", "eval")
                        else:
                            for kw in call.keywords:
                                if kw.arg == "preferred":
                                    pref_code = compile(ast.Expression(body=kw.value), f"<{attr_name}_pref_{arg_name}>", "eval")
                                    break
                        if arg_name:
                            param_domains[arg_name] = (domain_code, pref_code)
    except Exception:
        pass

    res = {
        "name": attr_name,
        "target": spec.target,
        "orig_fn": orig_fn,
        "target_type": target_type,
        "suts_type": suts_type,
        "has_suts_param": has_suts_param,
        "param_names": param_names,
        "req_codes": req_codes,
        "param_domains": param_domains,
        "globals": orig_fn.__globals__,
    }
    _LINEAR_PARSE_CACHE[cache_key] = res
    return dict(res)


def _build_linear_transition(
    sm_instance: Any,
    raw_fn: Callable[..., Any],
    spec: transition,
    attr_name: str,
    target_fn: Callable[..., Any],
) -> Transition:
    from hypothesis import strategies as st

    desc = _parse_linear_transition(raw_fn, spec, attr_name)
    desc["target_fn"] = target_fn
    t = Transition(name=attr_name, target=spec.target, is_seeding=getattr(spec, "is_seeding", False))
    t._is_linear = True
    t._linear_desc = desc
    t._target_fn = target_fn

    req_codes = list(desc["req_codes"])
    param_names = desc["param_names"]
    param_domains = dict(desc["param_domains"])
    fn_globals = desc["globals"]
    eval_globs = dict(fn_globals)
    eval_globs.setdefault("Domain", Domain)
    eval_globs.setdefault("PretenseSpecificationError", PretenseSpecificationError)

    # Inherit parameter domains and requirement codes from base state machine if missing
    if sm_instance is not None and hasattr(sm_instance, "__class__"):
        for base_cls in sm_instance.__class__.__mro__[1:]:
            if not issubclass(base_cls, StateMachine):
                continue
            base_attr = getattr(base_cls, attr_name, None)
            if base_attr is not None:
                base_spec = getattr(base_attr, "__transition_spec__", None)
                if base_spec is not None:
                    base_raw_fn = getattr(base_spec, "fn", None) or base_attr
                    base_desc = _parse_linear_transition(base_raw_fn, base_spec, attr_name)
                    for p_name, (d_code, pr_code) in base_desc.get("param_domains", {}).items():
                        if p_name not in param_domains:
                            param_domains[p_name] = (d_code, pr_code)
                            for k, v in base_desc.get("globals", {}).items():
                                eval_globs.setdefault(k, v)
                    if not req_codes and base_desc.get("req_codes"):
                        req_codes = list(base_desc["req_codes"])
                    break

    target_defaults: Dict[str, Any] = {}
    if spec.target is not None:
        try:
            t_sig = inspect.signature(spec.target)
            for p in t_sig.parameters.values():
                if p.default is not inspect.Parameter.empty:
                    target_defaults[p.name] = p.default
        except (ValueError, TypeError):
            pass

    fn_defaults: Dict[str, Any] = {}
    try:
        f_sig = inspect.signature(raw_fn)
        for p in f_sig.parameters.values():
            if p.default is not inspect.Parameter.empty:
                fn_defaults[p.name] = p.default
    except (ValueError, TypeError):
        pass

    def linear_req(state: Any, this: Any) -> bool:
        eval_ns = {"self": this, "state": state}
        for code in req_codes:
            try:
                if not eval(code, eval_globs, eval_ns):
                    return False
            except Exception:
                return False
        return True

    t.requirements.append(linear_req)

    def linear_args(state: Any, this: Any, *args: Any, **kwargs: Any) -> Any:
        is_generation = (not args and not kwargs) or (args and all(isinstance(a, NotBoundType) for a in args))
        eval_ns = {"self": this, "state": state}
        drawn: Dict[str, Any] = {}

        if is_generation:
            draw = get_current_draw()
            for p_name in param_names:
                eval_ns.update(drawn)
                if p_name not in param_domains:
                    raise PretenseSpecificationError(f"Parameter '{p_name}' has no require_arg declaration in '{attr_name}'")
                d_code, pr_code = param_domains[p_name]
                dom = eval(d_code, eval_globs, eval_ns)
                if not isinstance(dom, Domain):
                    dom = Domain.of(dom)

                valid_pref: List[Any] = []
                if pr_code is not None:
                    try:
                        pr_vals = eval(pr_code, eval_globs, eval_ns)
                        if pr_vals:
                            valid_pref = [v for v in pr_vals if dom.validate(v)]
                    except Exception:
                        valid_pref = []

                strat = dom.to_strategy()
                if getattr(strat, "is_empty", False) and not valid_pref:
                    raise UnsatisfiedAntecedentError(
                        f"Domain for parameter '{p_name}' cannot generate valid arguments in state: {state}"
                    )

                chosen_val = NotBound
                if valid_pref and draw is not None and draw(st.booleans()):
                    chosen_val = draw(st.sampled_from(valid_pref))
                elif draw is not None:
                    try:
                        chosen_val = _draw_from_domain(dom, draw)
                    except Exception as e:
                        if valid_pref:
                            chosen_val = draw(st.sampled_from(valid_pref))
                        else:
                            raise UnsatisfiedAntecedentError(
                                f"Domain for parameter '{p_name}' failed to generate valid argument in state: {state}"
                            ) from e
                else:
                    chosen_val = _resolve_argument_value(strat, None)

                if chosen_val is NotBound or not dom.validate(chosen_val):
                    if valid_pref:
                        chosen_val = valid_pref[0]
                    else:
                        raise UnsatisfiedAntecedentError(
                            f"Domain for parameter '{p_name}' failed to generate valid argument in state: {state}"
                        )
                drawn[p_name] = chosen_val
            return tuple(drawn[p] for p in param_names)
        else:
            actual_args = args
            for i, p_name in enumerate(param_names):
                if i < len(actual_args):
                    val = actual_args[i]
                elif p_name in kwargs:
                    val = kwargs[p_name]
                elif p_name in target_defaults:
                    val = target_defaults[p_name]
                elif p_name in fn_defaults:
                    val = fn_defaults[p_name]
                else:
                    t._last_reject_reason = f"missing required argument '{p_name}'"
                    return None
                eval_ns.update(drawn)
                if p_name in param_domains:
                    d_code, _ = param_domains[p_name]
                    dom = eval(d_code, eval_globs, eval_ns)
                    if not isinstance(dom, Domain):
                        dom = Domain.of(dom)
                    if not dom.validate(val):
                        t._last_reject_reason = f"parameter '{p_name}' failed domain validation (expected {dom}, got {val!r})"
                        return None
                drawn[p_name] = val
            return tuple(drawn[p] for p in param_names)


    t.args_fn = linear_args
    return t


class Transition:
    """Declarative state transition model."""

    def __init__(
        self,
        name: str,
        target: Optional[Any] = None,
        is_seeding: bool = False,
    ) -> None:
        self.name: str = name
        self.target: Optional[Any] = target
        self.is_seeding: bool = is_seeding
        self.requirements: List[Callable[..., bool]] = []
        self.args_fn: Optional[Callable[..., Any]] = None
        self.return_fn: Optional[Callable[..., Any]] = None
        self.ensure_fn: Optional[Callable[..., Any]] = None
        self.provider: Optional[Callable[..., Any]] = None
        self.ctx: Optional[TransitionContext[Any, Any, Any]] = None
        self._is_lifted: bool = False
        self._is_linear: bool = False
        self._linear_desc: Dict[str, Any] = {}
        self._target_fn: Optional[Callable[..., Any]] = None
        self._run_consequent: Optional[Callable[..., None]] = None
        self._last_reject_reason: Optional[str] = None


    def require(self, fn: Callable[..., bool]) -> Callable[..., bool]:
        self.requirements.append(fn)
        return fn

    def requires(self, fn: Callable[..., bool]) -> Callable[..., bool]:
        return self.require(fn)

    def arguments(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        self.args_fn = fn
        return fn

    def returns(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        self.return_fn = fn
        return fn

    def ensures(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        self.ensure_fn = fn
        return fn

    def provide(self, fn: Callable[..., None]) -> Callable[..., None]:
        self.provider = fn
        return fn

    def update(self, fn: Callable[..., None]) -> Callable[..., None]:
        return self.provide(fn)


class StateMachineProto(Generic[StateT]):
    """Structural prototype for Pretense state machine definitions."""

    transitions: List[Transition]
    invariants: List[Callable[..., None]]

    def __init__(self) -> None:
        self.transitions = []
        self.invariants = []

    def transition(
        self,
        method: Optional[Any] = None,
        *,
        name: Optional[str] = None,
    ) -> Callable[[Callable[..., Any]], Transition]:
        def decorator(marker: Callable[..., Any]) -> Transition:
            tr_name = name or getattr(method, "__name__", marker.__name__)
            t = Transition(
                name=tr_name,
                target=method if callable(method) else None,
                is_seeding=False,
            )
            self.transitions.append(t)
            return t
        return decorator

    def seeding(self) -> Callable[[Callable[..., Any]], Transition]:
        def decorator(marker: Callable[..., Any]) -> Transition:
            t = Transition(
                name=marker.__name__,
                target=None,
                is_seeding=True,
            )
            self.transitions.append(t)
            return t
        return decorator

    def invariant(self, fn: Callable[..., None]) -> Callable[..., None]:
        self.invariants.append(fn)
        return fn

    def as_fake(self) -> Any:
        return self.make_state_machine(None).as_fake()

    def make_state_machine(self, initial_state: Any) -> StateMachine:
        return StateMachine(
            state=initial_state,
            transitions=list(self.transitions),
            invariants=list(self.invariants),
        )

    def make_fake(self, protocol_type: Type[Any], initial_state: Any) -> Any:
        sm = self.make_state_machine(initial_state)
        return sm.as_fake(protocol_type)


def _resolve_target_singleton(singletons: Any, target: Any) -> Any:
    """Resolves the concrete singleton instance under test matching a target function or class."""
    if target is None:
        return None
    target_name = getattr(target, "__name__", "")
    target_qualname = getattr(target, "__qualname__", "")
    class_name = target_qualname.rsplit(".", 1)[0] if "." in target_qualname else ""

    if isinstance(singletons, dict):
        if isinstance(target, type) and target in singletons:
            return singletons[target]

        if class_name:
            for k, v in singletons.items():
                if getattr(k, "__name__", "") == class_name or getattr(k, "__qualname__", "") == class_name:
                    return v

        if target_name:
            for k, v in singletons.items():
                if v is not None and hasattr(v, target_name) and callable(getattr(v, target_name)):
                    return v

        if isinstance(target, type):
            for k, v in singletons.items():
                if isinstance(v, target):
                    return v
        return None

    if singletons is not None:
        if isinstance(target, type) and isinstance(singletons, target):
            return singletons
        if target_name and hasattr(singletons, target_name):
            return singletons
    return None


class StateMachine(Generic[StateT]):
    """Base class for Pretense state machines."""

    _compiler: Optional[Callable[..., Any]] = None

    @classmethod
    def register_compiler(cls, compiler: Callable[..., Any]) -> None:
        cls._compiler = compiler

    @classmethod
    def to_proto(cls, *args: Any, **kwargs: Any) -> Any:
        """Instantiates and returns a prototype state machine instance for test compilation."""
        return cls(*args, **kwargs)

    def __init__(
        self,
        state: Any = None,
        transitions: Optional[List[Transition]] = None,
        invariants: Optional[List[Callable[..., None]]] = None,
        singletons: Optional[Dict[Type[Any], Any]] = None,
    ) -> None:
        self.state: Any = state
        self.transitions: List[Transition] = list(transitions) if transitions is not None else []
        self.invariants: List[Callable[..., None]] = list(invariants) if invariants is not None else []
        self.singletons: Dict[Type[Any], Any] = dict(singletons or {})

        # Auto-discover @transition methods on self in class definition order
        seen_transitions: set[str] = set()
        for cls_in_mro in reversed(self.__class__.__mro__):
            for attr_name, attr in cls_in_mro.__dict__.items():
                if attr_name.startswith("__") or attr_name in seen_transitions:
                    continue
                spec = getattr(attr, "__transition_spec__", None)
                if spec is not None:
                    seen_transitions.add(attr_name)
                    raw_fn = spec.fn or attr
                    try:
                        sig = inspect.signature(raw_fn)
                        params = list(sig.parameters.values())
                        has_ctx = bool(params and params[-1].name == "ctx")
                    except Exception:
                        has_ctx = False
                    if has_ctx:
                        tr_name = spec.name or getattr(spec.target, "__name__", None) or getattr(getattr(spec.target, "fget", None), "__name__", attr_name)
                        ctx = TransitionContext(target=spec.target, name=tr_name, is_seeding=getattr(spec, "is_seeding", False))
                        method = getattr(self, attr_name)
                        method(ctx)
                        t = _build_transition_from_context(ctx)
                    else:
                        target_fn = getattr(attr, "__target_fn__", raw_fn)
                        t = _build_linear_transition(self, raw_fn, spec, attr_name, target_fn)
                    self.transitions.append(t)


        # Auto-discover invariant_* methods on self
        for attr_name in dir(self.__class__):
            if attr_name.startswith("invariant_") and callable(getattr(self, attr_name)):
                inv_method = getattr(self, attr_name)

                def _make_inv_wrapper(m: Callable[..., Any]) -> Callable[..., None]:
                    def inv_wrapper(st: Any, sm: Any) -> None:
                        m()
                    return inv_wrapper

                self.invariants.append(_make_inv_wrapper(inv_method))

    def bind_singleton(self, target_type: Type[Any], instance: Any) -> None:
        self.singletons[target_type] = instance

    def get_singleton(self, target_type: Type[T]) -> T:
        if target_type not in self.singletons:
            raise KeyError(f"No singleton registered for type '{target_type.__name__}'")
        return self.singletons[target_type]

    def sut(self, target_type: Type[T]) -> T:
        """Convenience accessor on the active state machine resolving a registered singleton under test."""
        return self.get_singleton(target_type)

    def as_fake(self, protocol_type: Optional[Type[T]] = None) -> T:
        target = protocol_type if protocol_type is not None else object
        return cast(
            T,
            FakeAdapter(
                target_protocol=target,
                state=self.state,
                transitions=self.transitions,
                state_machine=self,
            ),
        )

    def as_checked(self, protocol_type: Type[T], real_instance: Optional[T] = None) -> T:
        return cast(
            T,
            CheckedAdapter(
                target_protocol=protocol_type,
                state_machine=self,
                real_instance=real_instance,
            ),
        )

    def bind(self, target: Any) -> Any:
        """Binds this state machine to a concrete target instance, returning a verification driver."""
        return CheckedAdapter(type(target), self, target)

    def make_state_machine(self, initial_state: Any) -> StateMachine:
        try:
            return type(self)(state=initial_state, singletons=dict(self.singletons))
        except TypeError:
            try:
                return type(self)(initial_state)
            except TypeError:
                pass
        return StateMachine(
            state=initial_state,
            transitions=list(self.transitions),
            invariants=list(self.invariants),
            singletons=dict(self.singletons),
        )

    def check_invariants(self) -> None:
        for inv in self.invariants:
            inv(self.state, self)

    def dispatch_transition(self, transition_name: Any, *args: Any, **kwargs: Any) -> Any:
        target_or_name = transition_name
        candidate_transitions = [
            t for t in self.transitions
            if t.name == target_or_name
            or t.target == target_or_name
            or getattr(t.target, "__name__", None) == target_or_name
            or getattr(getattr(t.target, "fget", None), "__name__", None) == target_or_name
        ]
        if not candidate_transitions:
            raise KeyError(f"No transition matching '{target_or_name}' in state machine")

        matched: List[Tuple[Transition, Tuple[Any, ...]]] = []
        rejection_reasons = []
        for cand in candidate_transitions:
            failed_reqs = []
            for req in cand.requirements:
                if not req(self.state, self):
                    chk = getattr(req, "last_check", None)
                    reason_msg = ", ".join(chk.reasons) if chk and chk.reasons else getattr(req, "__name__", "precondition unmet")
                    failed_reqs.append(reason_msg)
            if failed_reqs:
                rejection_reasons.append(f"'{cand.name}': {', '.join(failed_reqs)}")
                continue

            if cand.args_fn is not None:
                parsed = cand.args_fn(self.state, self, *args, **kwargs)
                if parsed is None:
                    last_rej = getattr(cand, "_last_reject_reason", None)
                    if last_rej:
                        rejection_reasons.append(f"'{cand.name}': {last_rej}")
                    else:
                        rejection_reasons.append(f"'{cand.name}': argument parsing failed")
                    continue
                matched.append((cand, parsed))
            else:
                matched.append((cand, args))

        if len(matched) == 0:
            detail = f" (rejection reasons: {'; '.join(rejection_reasons)})" if rejection_reasons else ""
            raise NoMatchingTransitionError(
                f"No matching transition for '{target_or_name}' with args={args}, "
                f"kwargs={kwargs} in state: {self.state}{detail}"
            )
        if len(matched) > 1:
            matching_names = [cand.name for cand, _ in matched]
            raise AmbiguousTransitionError(
                f"Ambiguous transitions for '{target_or_name}' ({matching_names}) with "
                f"args={args}, kwargs={kwargs} in state: {self.state}"
            )

        t, resolved_args = matched[0]
        if getattr(t, "_is_linear", False) and t._target_fn is not None:
            token = _last_ensured_ret.set(NotBound)
            token_exc = _last_raised_exc.set(None)
            token_suts = _ACTIVE_SUTS.set(dict(self.singletons))
            token_sm = _current_sm.set(self)
            try:
                res = t._target_fn(self, *resolved_args)
                self.check_invariants()
                last_raised = _last_raised_exc.get()
                if last_raised is not None:
                    raise last_raised
                ensured_val = _last_ensured_ret.get()
                if res is None and ensured_val is not NotBound:
                    return ensured_val
                return res
            finally:
                _current_sm.reset(token_sm)
                _ACTIVE_SUTS.reset(token_suts)
                _last_raised_exc.reset(token_exc)
                _last_ensured_ret.reset(token)

        is_lifted = bool(getattr(t, "_is_lifted", False))

        target_obj = _resolve_target_singleton(self.singletons, t.target)
        res = None
        raised_exc: Optional[Exception] = None

        target_method_name = (
            getattr(t.target, "__name__", None)
            or getattr(getattr(t.target, "fget", None), "__name__", str(t.name))
        )
        target_fn = (
            getattr(target_obj, target_method_name, None)
            if (target_obj is not None and hasattr(target_obj, target_method_name))
            else (t.target if callable(t.target) else None)
        )
        call_kwargs = dict(kwargs)
        if target_fn is not None and call_kwargs:
            try:
                sig = inspect.signature(target_fn)
                for p in sig.parameters.values():
                    if p.name in call_kwargs and p.kind in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    ):
                        del call_kwargs[p.name]
            except (ValueError, TypeError):
                pass

        if target_obj is not None and t.target is not None and not t.is_seeding:
            try:
                if isinstance(t.target, property) or isinstance(getattr(type(target_obj), target_method_name, None), property):
                    res = getattr(target_obj, target_method_name)
                elif hasattr(target_obj, target_method_name):
                    method = getattr(target_obj, target_method_name)
                    res = method(*resolved_args, **call_kwargs)
                elif callable(t.target):
                    res = t.target(target_obj, *resolved_args, **call_kwargs)
            except Exception as e:  # cleanroom: allow-broad-exception
                raised_exc = e

            sut_outcome: Outcome[Any] = Raised(raised_exc) if raised_exc is not None else Value(res)
            if t.return_fn is not None:
                recognized = t.return_fn(self.state, self, *resolved_args, outcome=sut_outcome)
                if recognized is None and sut_outcome == Value(None) and not (getattr(t, "ctx", None) and getattr(t.ctx, "expected_exception", None)):
                    valid_outcome: Outcome[Any] = Value(None)
                elif recognized is not None:
                    valid_outcome = recognized if isinstance(recognized, (Value, Raised)) else Value(recognized)
                else:
                    if raised_exc is not None and not (getattr(t, "ctx", None) and getattr(t.ctx, "expected_exception", None)):
                        raise raised_exc
                    raise AssertionError(
                        f"Return Contract Violation: SUT produced invalid outcome {sut_outcome!r} "
                        f"which was rejected by the returns recognizer for '{t.name}'"
                    )
            else:
                if raised_exc is not None:
                    raise raised_exc
                valid_outcome = Value(res)

            check_obj = EnsuresCheck(self.singletons)
            if isinstance(valid_outcome, Raised):
                if is_lifted and t._run_consequent is not None:
                    t._run_consequent(self.state, self, valid_outcome, target_obj, check_obj, *resolved_args)
                self.check_invariants()
                raise valid_outcome.exc

            actual_res = valid_outcome.val if isinstance(valid_outcome, Value) else valid_outcome
            if is_lifted and t._run_consequent is not None:
                t._run_consequent(self.state, self, actual_res, target_obj, check_obj, *resolved_args)
            else:
                if t.ensure_fn is not None and (target_obj is not None or self.singletons):
                    t.ensure_fn(actual_res, target_obj, check_obj, *resolved_args, **kwargs)
                if t.provider is not None:
                    t.provider(self.state, self, *resolved_args, result=actual_res)

            self.check_invariants()
            return actual_res
        else:
            if t.return_fn is not None:
                try:
                    ret_val = t.return_fn(self.state, self, *resolved_args, outcome=NotBound)
                    if isinstance(ret_val, Raised):
                        if is_lifted and t.provider is not None:
                            t.provider(self.state, self, *resolved_args, result=ret_val)
                        self.check_invariants()
                        raise ret_val.exc
                    res = ret_val.unwrap() if isinstance(ret_val, Value) else ret_val
                except Exception as e:  # cleanroom: allow-broad-exception
                    raised_exc = e
            if raised_exc is not None:
                raise raised_exc

            if is_lifted and t._run_consequent is not None:
                check_obj = EnsuresCheck(self.singletons) if self.singletons else None
                t._run_consequent(self.state, self, res, None, check_obj, *resolved_args)
            else:
                if t.ensure_fn is not None and self.singletons:
                    check_obj = EnsuresCheck(self.singletons)
                    t.ensure_fn(res, None, check_obj, *resolved_args, **kwargs)
                if t.provider is not None:
                    t.provider(self.state, self, *resolved_args, result=res)

            self.check_invariants()
            return res

    def to_hypothesis_test_case(
        self,
        sut_factory: Optional[Callable[[], Any]] = None,
        settings: Optional[Any] = None,
        name: Optional[str] = None,
    ) -> Type[Any]:
        if StateMachine._compiler is None:
            raise RuntimeError(
                "Pretense Hypothesis test case compiler is not registered. "
                "Ensure pretense is imported (e.g. `import pretense`)."
            )
        actual_sut_factory = sut_factory if sut_factory is not None else (lambda: self.singletons)
        import copy
        return StateMachine._compiler(
            proto=self,
            sut_factory=actual_sut_factory,
            initial_state_factory=lambda: copy.deepcopy(self.state),
            settings=settings,
            name=name or f"Test{type(self).__name__}Fuzz",
        )

    def __getattr__(self, name: str) -> Any:
        # Check if attribute corresponds to a seeding transition
        for t in self.transitions:
            if t.is_seeding and t.name == name:
                def invoke_seeding(*args: Any, **kwargs: Any) -> Any:
                    return self.dispatch_transition(name, *args, **kwargs)
                return invoke_seeding
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


class CheckedAdapter:
    """Verification proxy conforming to an interface protocol that dispatches through a state machine and real singleton."""

    def __init__(
        self,
        target_protocol: Type[Any],
        state_machine: Any,
        real_instance: Optional[Any] = None,
    ) -> None:
        self._target_protocol: Type[Any] = target_protocol
        self._state_machine: Any = state_machine
        self._real_instance: Optional[Any] = real_instance
        if real_instance is not None and hasattr(state_machine, "bind_singleton"):
            state_machine.bind_singleton(target_protocol, real_instance)
            if type(real_instance) is not target_protocol:
                state_machine.bind_singleton(type(real_instance), real_instance)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        # 1. Find 1:1 base interface transition method first (outer onion)
        base_method = None
        for c in reversed(type(self._state_machine).__mro__):
            if issubclass(c, StateMachine) and hasattr(c, name):
                m = getattr(c, name)
                if hasattr(m, "__transition_spec__") or hasattr(m, "__pretense_transition__"):
                    base_method = m
                    break
        if base_method is None:
            tr_method = getattr(self._state_machine, name, None)
            if tr_method is not None and (
                hasattr(tr_method, "__transition_spec__")
                or hasattr(tr_method, "__pretense_transition__")
                or any(getattr(t, "name", None) == name for t in getattr(self._state_machine, "transitions", []))
            ):
                base_method = tr_method

        if base_method is not None and callable(base_method):
            is_prop = False
            if self._real_instance is not None and hasattr(self._real_instance, name):
                if not callable(getattr(self._real_instance, name)):
                    is_prop = True
            elif hasattr(self._target_protocol, name):
                is_prop = isinstance(getattr(self._target_protocol, name), property)

            if not is_prop:
                for t in getattr(self._state_machine, "transitions", []):
                    if getattr(t, "name", None) == name:
                        tgt = getattr(t, "target", None)
                        if isinstance(tgt, property) or (tgt is not None and hasattr(tgt, "fget")):
                            is_prop = True
                            break

            def direct_dispatch(*args: Any, **kwargs: Any) -> Any:
                token_sut = _current_sut.set(self._real_instance)
                token_ver = _is_verification.set(True)
                token_tgt = _current_target.set(self._real_instance)
                token_mth = _current_method.set(name)
                token_arg = _current_args.set(args)
                token_kw = _current_kwargs.set(kwargs)
                token_sm = _current_sm.set(self._state_machine)
                tok_ret = _last_ensured_ret.set(NotBound)
                try:
                    target_base = getattr(base_method, "__target_fn__", base_method)
                    res = target_base(self._state_machine, *args, **kwargs)
                    last_ret = _last_ensured_ret.get()
                    if res is None and last_ret is not NotBound:
                        res = last_ret
                    return res
                finally:
                    _last_ensured_ret.reset(tok_ret)
                    _current_sm.reset(token_sm)
                    _current_kwargs.reset(token_kw)
                    _current_args.reset(token_arg)
                    _current_method.reset(token_mth)
                    _current_target.reset(token_tgt)
                    _is_verification.reset(token_ver)
                    _current_sut.reset(token_sut)

            if is_prop:
                return direct_dispatch()
            return direct_dispatch

        # 2. Check for real instance attributes or protocol properties
        if self._real_instance is not None and hasattr(self._real_instance, name):
            return getattr(self._real_instance, name)

        lifecycle_methods = {"initialize", "teardown", "close", "cleanup"}
        if name in lifecycle_methods:
            return lambda *_a, **_kw: None

        raise AttributeError(
            f"'{getattr(self._target_protocol, '__name__', str(self._target_protocol))}' checked adapter has no attribute or transition '{name}'"
        )


class FakeAdapter:
    """Dynamic test double conforming to an interface protocol."""

    def __init__(
        self,
        target_protocol: Type[Any],
        state: Any = None,
        transitions: Optional[List[Transition]] = None,
        state_machine: Any = None,
    ) -> None:
        self._target_protocol: Type[Any] = target_protocol
        self._state: Any = state
        self._transitions: List[Transition] = transitions or []
        self._state_machine: Any = state_machine

    def _dispatch(self, method_name: str, *bound_args: Any, **bound_kwargs: Any) -> Any:
        candidate_transitions = [
            t
            for t in self._transitions
            if not t.is_seeding
            and (
                getattr(t.target, "__name__", None) == method_name
                or getattr(getattr(t.target, "fget", None), "__name__", None) == method_name
                or t.name == method_name
            )
        ]

        if len(candidate_transitions) == 0 and method_name in (
            "initialize",
            "teardown",
            "close",
            "cleanup",
        ):
            return None

        matches: List[Tuple[Transition, Tuple[Any, ...]]] = []
        this = self._state_machine if self._state_machine is not None else self

        for t in candidate_transitions:
            if not all(req(self._state, this) for req in t.requirements):
                continue

            if t.args_fn is not None:
                parsed_args = t.args_fn(self._state, this, *bound_args, **bound_kwargs)
                if parsed_args is None:
                    continue
                matches.append((t, parsed_args))
            else:
                matches.append((t, bound_args))

        if len(matches) == 0:
            rejection_reasons = []
            for t in candidate_transitions:
                for req in t.requirements:
                    chk = getattr(req, "last_check", None)
                    if chk and chk.reasons:
                        rejection_reasons.append(f"'{t.name}': {', '.join(chk.reasons)}")
            detail = f" (rejection reasons: {'; '.join(rejection_reasons)})" if rejection_reasons else ""
            raise NoMatchingTransitionError(
                f"No matching transition for '{method_name}' with args={bound_args}, "
                f"kwargs={bound_kwargs} in state: {self._state}{detail}"
            )
        if len(matches) > 1:
            matching_names = [t.name for t, _ in matches]
            raise AmbiguousTransitionError(
                f"Ambiguous transitions for '{method_name}' ({matching_names}) with "
                f"args={bound_args}, kwargs={bound_kwargs} in state: {self._state}"
            )

        t, resolved_args = matches[0]
        is_lifted = bool(getattr(t, "_is_lifted", False))

        if t.return_fn is not None:
            ret_val = t.return_fn(self._state, this, *resolved_args, outcome=NotBound)

            if isinstance(ret_val, Raised):
                if is_lifted and t.provider is not None:
                    t.provider(self._state, this, *resolved_args, result=ret_val)
                    if self._state_machine is not None:
                        self._state_machine.check_invariants()
                raise ret_val.exc

            actual_result = ret_val.val if isinstance(ret_val, Value) else ret_val

            if t.provider is not None:
                t.provider(self._state, this, *resolved_args, result=actual_result)
            if self._state_machine is not None:
                self._state_machine.check_invariants()
            return actual_result
        else:
            if t.provider is not None:
                t.provider(self._state, this, *resolved_args, result=None)
            if self._state_machine is not None:
                self._state_machine.check_invariants()
            return None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        lifecycle_methods = {"initialize", "teardown", "close", "cleanup"}
        has_transition = any(
            (
                getattr(t.target, "__name__", None) == name
                or getattr(getattr(t.target, "fget", None), "__name__", None) == name
                or t.name == name
            )
            for t in self._transitions
        )
        has_protocol_attr = hasattr(self._target_protocol, name) or name in dir(self._target_protocol)

        if not (has_transition or has_protocol_attr or name in lifecycle_methods):
            raise AttributeError(
                f"'{getattr(self._target_protocol, '__name__', str(self._target_protocol))}' fake has no attribute or transition '{name}'"
            )

        proto_attr = getattr(self._target_protocol, name, None)
        if isinstance(proto_attr, property):
            return self._dispatch(name)

        def method_proxy(*args: Any, **kwargs: Any) -> Any:
            return self._dispatch(name, *args, **kwargs)

        return method_proxy


def _instantiate_exception(exc_cls: Any) -> Any:
    if isinstance(exc_cls, BaseException):
        return exc_cls
    try:
        return _safe_instantiate_exception(exc_cls)
    except Exception:
        pass
    try:
        return exc_cls()
    except TypeError:
        try:
            return exc_cls.__new__(exc_cls)
        except Exception:
            return Exception(f"Synthesized exception for {exc_cls}")


def synthesize_fake(machine_cls: Type[Any], fake_name: Optional[str] = None) -> Type[Any]:
    """Synthesizes a pure in-memory test double class from a linear state machine."""
    target_fake_name = fake_name or f"Fake{machine_cls.__name__.replace('StateMachine', '')}"

    class SynthesizedFake:
        __is_pretense_fake__ = True

        def __init__(self, *args: Any, state: Any = None, **kwargs: Any) -> None:
            if state is None and args and hasattr(args[0], "__dataclass_fields__"):
                state = args[0]
                args = args[1:]
            if state is None:
                try:
                    init_sm = machine_cls(*args, **kwargs)
                    state = init_sm.state
                except Exception:
                    state = None
            self._sm = machine_cls(state=state) if state is not None else machine_cls(*args, **kwargs)
            self._state = self._sm.state

        @property
        def state(self) -> Any:
            return self._state

        def __getattr__(self, name: str) -> Any:
            if name.startswith("_"):
                raise AttributeError(name)

            sm = self._sm

            # 1. Check properties on state machine class
            cls_attr = getattr(type(sm), name, None)
            if isinstance(cls_attr, property):
                token_sut = _current_sut.set(self)
                token_ver = _is_verification.set(False)
                token_tgt = _current_target.set(self)
                token_mth = _current_method.set(name)
                token_sm = _current_sm.set(sm)
                try:
                    if cls_attr.fget is not None:
                        return cls_attr.fget(sm)
                finally:
                    _current_sm.reset(token_sm)
                    _current_method.reset(token_mth)
                    _current_target.reset(token_tgt)
                    _is_verification.reset(token_ver)
                    _current_sut.reset(token_sut)

            # 2. Check callable transitions or methods on state machine
            if hasattr(sm, name):
                attr = getattr(sm, name)
                if callable(attr):
                    def fake_method_wrapper(*args: Any, **kwargs: Any) -> Any:
                        token_sut = _current_sut.set(self)
                        token_ver = _is_verification.set(False)
                        token_tgt = _current_target.set(self)
                        token_mth = _current_method.set(name)
                        token_arg = _current_args.set(args)
                        token_kw = _current_kwargs.set(kwargs)
                        token_sm = _current_sm.set(sm)
                        tok_ret = _last_ensured_ret.set(NotBound)
                        try:
                            res = attr(*args, **kwargs)
                            last_ret = _last_ensured_ret.get()
                            if res is None and last_ret is not NotBound:
                                res = last_ret
                            return res
                        finally:
                            _last_ensured_ret.reset(tok_ret)
                            _current_sm.reset(token_sm)
                            _current_kwargs.reset(token_kw)
                            _current_args.reset(token_arg)
                            _current_method.reset(token_mth)
                            _current_target.reset(token_tgt)
                            _is_verification.reset(token_ver)
                            _current_sut.reset(token_sut)

                    is_prop = False
                    for t in getattr(sm, "transitions", []):
                        if getattr(t, "name", None) == name:
                            tgt = getattr(t, "target", None)
                            if isinstance(tgt, property) or (tgt is not None and hasattr(tgt, "fget")):
                                is_prop = True
                                break
                    if not is_prop and (hasattr(self._state, name) or name in ("size", "is_empty", "is_full")):
                        try:
                            sig = inspect.signature(attr)
                            user_params = [p for p in sig.parameters.values() if p.name not in ("self", "ctx")]
                            if not user_params:
                                is_prop = True
                        except Exception:
                            pass

                    if is_prop:
                        return fake_method_wrapper()
                    return fake_method_wrapper
                return attr

            # 3. Check attribute on state
            if hasattr(self._state, name):
                return getattr(self._state, name)

            # 4. Standard collection fallbacks if items exist on state
            if name == "size" and hasattr(self._state, "items"):
                return len(self._state.items)
            if name == "is_empty" and hasattr(self._state, "items"):
                return len(self._state.items) == 0
            if name == "is_full" and hasattr(self._state, "items") and hasattr(self._state, "capacity"):
                return len(self._state.items) >= self._state.capacity

            raise AttributeError(f"'{target_fake_name}' object has no attribute '{name}'")

    SynthesizedFake.__name__ = target_fake_name
    SynthesizedFake.__qualname__ = target_fake_name
    return SynthesizedFake



class PretenseEngine(Singleton[SystemTier], Protocol):

    """System-tier service coordinating state machine compilation, test execution, and fake generation."""

    def compile_state_machine(self, machine_cls: Type[Any]) -> Type[Any]: ...
    def run_suite(self, config: PretenseRunnerConfig) -> PretenseRunResult: ...
    def synthesize_test(self, target_cls: Type[Any], trace: Sequence[TraceStep]) -> str: ...
    def synthesize_fake(self, machine_cls: Type[Any]) -> Type[Any]: ...
