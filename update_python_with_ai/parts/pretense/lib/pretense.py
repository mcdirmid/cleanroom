"""Pretense core interfaces, models, and stateful testing primitives."""

from __future__ import annotations

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
    ParamSpec,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
    runtime_checkable,
)

from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T")
Target = TypeVar("Target")
P = ParamSpec("P")
R = TypeVar("R")
StateT = TypeVar("StateT", covariant=True)
SelfT = TypeVar("SelfT")


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


class NoMatchingTransitionError(PretenseError):
    """Raised when no transition's requirements and argument recognizers match a call."""


class AmbiguousTransitionError(PretenseError):
    """Raised when more than one candidate transition matches a call."""


_CURRENT_DRAW: ContextVar[Optional[Callable[..., Any]]] = ContextVar(
    "_CURRENT_DRAW", default=None
)


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
        seq = tuple(items)
        from hypothesis import strategies as st
        return Domain[T](
            strategy=st.sampled_from(seq) if seq else st.nothing(),
            validator=lambda val: val in seq,
        )

    @classmethod
    def range(cls, start: int, stop: int, step: int = 1) -> Domain[int]:
        from hypothesis import strategies as st
        r = range(start, stop, step)
        return Domain[int](
            strategy=st.integers(min_value=start, max_value=stop - 1),
            validator=lambda val: isinstance(val, int) and not isinstance(val, bool) and val in r,
        )

    @classmethod
    def regex(cls, pattern: Union[str, Any]) -> Domain[str]:
        from hypothesis import strategies as st
        import re
        pat = re.compile(pattern) if isinstance(pattern, str) else pattern
        return Domain[str](
            strategy=st.from_regex(pat, fullmatch=True),
            validator=lambda val: isinstance(val, str) and bool(pat.fullmatch(val)),
        )

    @classmethod
    def type(cls, target_cls: Type[T]) -> Domain[T]:
        from hypothesis import strategies as st
        strat: Any
        if target_cls is bool:
            strat = st.booleans()
        elif target_cls is int:
            strat = st.integers()
        elif target_cls is float:
            strat = st.floats()
        elif target_cls is str:
            strat = st.text()
        else:
            try:
                strat = st.builds(target_cls)
            except Exception:
                strat = st.from_type(target_cls)
        return Domain[T](
            strategy=strat,
            validator=lambda val: isinstance(val, target_cls),
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
        if isinstance(val, Domain):
            return val
        if isinstance(val, set):
            return cls.set(val)
        if isinstance(val, range):
            return cls.range(val.start, val.stop, val.step)
        import re
        if isinstance(val, re.Pattern):
            return cls.regex(val)
        if isinstance(val, type):
            return cls.type(val)
        if _is_strategy(val):
            return cls(strategy=val, validator=None)
        if isinstance(val, (list, tuple)) and not callable(val):
            return cls.set(val)
        return cls(strategy=val, validator=None)


class TransitionContext(Generic[Target, P, R]):
    """Context for specifying requires, argument, return, ensures, and update handlers for a transition."""

    def __init__(self, target: Any = None, name: Optional[str] = None, is_seeding: bool = False) -> None:
        self.target: Any = target
        self.name: Optional[str] = name
        self.is_seeding: bool = is_seeding
        self.predicate: Optional[Callable[..., Any]] = None
        self.domains: list[tuple[str, Any]] = []
        self.returns_fn: Optional[Any] = None
        self.ensures_fn: Optional[Callable[..., Any]] = None
        self.consequent_fn: Optional[Callable[..., Any]] = None
        self.expected_exception: Optional[Tuple[Type[Exception], str]] = None

    def requires(self, fn: Union[Callable[[RequiresCheck], Any], Callable[[], bool]]) -> None:
        self.predicate = fn

    def antecedent(self, predicate: Callable[[], bool]) -> None:
        self.requires(predicate)

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
    def seeding(cls, *, name: Optional[str] = None) -> transition:
        return cls(name=name, is_seeding=True)

    def __call__(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        self.fn = fn
        tr_self = self

        def method_proxy(instance: Any, *args: Any, **kwargs: Any) -> Any:
            if len(args) == 1 and not kwargs and isinstance(args[0], TransitionContext):
                return fn(instance, args[0])
            tr_name = tr_self.name or getattr(tr_self.target, "__name__", None) or getattr(getattr(tr_self.target, "fget", None), "__name__", fn.__name__)
            return instance.dispatch_transition(tr_name, *args, **kwargs)

        setattr(method_proxy, "__transition_spec__", self)
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
                req_wrapper.last_check = chk  # type: ignore[attr-defined]
                res = pred(chk)
                if res is False:
                    chk.ok = False
                return chk.ok
            req_wrapper.last_check = None  # type: ignore[attr-defined]
            t.requirements.append(req_wrapper)
        else:
            def req_wrapper_noarg(state: Any, this: Any) -> bool:
                chk = RequiresCheck()
                req_wrapper_noarg.last_check = chk  # type: ignore[attr-defined]
                ok = bool(pred())
                if not ok:
                    chk(False, "Precondition returned False")
                return ok
            req_wrapper_noarg.last_check = None  # type: ignore[attr-defined]
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

    t.ctx = ctx  # type: ignore[attr-defined]
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

        # Auto-discover @transition methods on self
        for attr_name in dir(self.__class__):
            if attr_name.startswith("__"):
                continue
            attr = getattr(self.__class__, attr_name, None)
            spec = getattr(attr, "__transition_spec__", None)
            if spec is not None:
                tr_name = spec.name or getattr(spec.target, "__name__", None) or getattr(getattr(spec.target, "fget", None), "__name__", attr_name)
                ctx = TransitionContext(target=spec.target, name=tr_name, is_seeding=getattr(spec, "is_seeding", False))
                method = getattr(self, attr_name)
                method(ctx)
                t = _build_transition_from_context(ctx)
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

    def as_fake(self, protocol_type: Optional[Type[Any]] = None) -> Any:
        target = protocol_type if protocol_type is not None else object
        return FakeAdapter(
            target_protocol=target,
            state=self.state,
            transitions=self.transitions,
            state_machine=self,
        )

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

    def dispatch_transition(self, target_or_name: Any, *args: Any, **kwargs: Any) -> Any:
        matches = [
            t for t in self.transitions
            if t.name == target_or_name
            or t.target == target_or_name
            or getattr(t.target, "__name__", None) == target_or_name
        ]
        if not matches:
            raise KeyError(f"No transition matching '{target_or_name}' in state machine")
        t = matches[0]

        for req in t.requirements:
            assert req(self.state, self), f"Requirement failed for transition '{t.name}'"

        if t.args_fn is not None:
            parsed = t.args_fn(self.state, self, *args, **kwargs)
            assert parsed is not None, f"Argument generation/recognition failed for '{t.name}'"
            resolved_args = parsed
        else:
            resolved_args = args

        target_obj = _resolve_target_singleton(self.singletons, t.target)
        res = None
        raised_exc: Optional[Exception] = None

        if target_obj is not None and t.target is not None:
            target_method_name = getattr(t.target, "__name__", str(t.name))
            try:
                if hasattr(target_obj, target_method_name):
                    method = getattr(target_obj, target_method_name)
                    res = method(*resolved_args, **kwargs)
                elif callable(t.target):
                    res = t.target(target_obj, *resolved_args, **kwargs)
            except Exception as e:
                raised_exc = e
        elif t.return_fn is not None:
            try:
                ret_val = t.return_fn(self.state, self, *resolved_args)
                res = ret_val.unwrap() if isinstance(ret_val, Value) else ret_val
            except Exception as e:
                raised_exc = e

        if raised_exc is not None:
            outcome = Raised(raised_exc)
            if t.return_fn is not None:
                recognized = t.return_fn(self.state, self, *resolved_args, outcome=outcome)
                if recognized is not None:
                    return outcome
            raise raised_exc

        if t.ensure_fn is not None and (target_obj is not None or self.singletons):
            check_obj = EnsuresCheck(self.singletons)
            t.ensure_fn(res, target_obj, check_obj, *resolved_args, **kwargs)

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

        if t.return_fn is not None:
            ret_val = t.return_fn(self._state, this, *resolved_args, outcome=NotBound)

            if isinstance(ret_val, Raised):
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
            (getattr(t.target, "__name__", None) == name or t.name == name)
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


class PretenseEngine(Singleton[SystemTier], Protocol):
    """System-tier service coordinating state machine compilation, test execution, and fake generation."""

    def compile_state_machine(self, machine_cls: Type[Any]) -> Type[Any]: ...
    def run_suite(self, config: PretenseRunnerConfig) -> PretenseRunResult: ...
    def synthesize_test(self, target_cls: Type[Any], trace: Sequence[TraceStep]) -> str: ...
