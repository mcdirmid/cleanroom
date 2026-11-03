"""Low-level interface specification for pretense."""

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Collection,
    Concatenate,
    Dict,
    Generic,
    List,
    Optional,
    ParamSpec,
    Protocol,
    Sequence,
     Set,
    Tuple,
    Type,
    Union,
    overload,
    runtime_checkable,
)
from typing_extensions import ParamSpec, TypeVar
from support.lib.framework import data_type, operation, poly_type, singleton_type
from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T", default=Any)
Target = TypeVar("Target", default=Any)
P = ParamSpec("P", default=...)
R = TypeVar("R", default=Any)
E = TypeVar("E", default=Any)
K = TypeVar("K", default=Any)
V = TypeVar("V", default=Any)
StateT = TypeVar("StateT", default=Any)
SelfT = TypeVar("SelfT", default=Any)


@data_type
class NotBoundType:
    """Pretense sentinel distinguishing omitted parameters from explicit None values."""

    def __repr__(self) -> str: ...
    def __bool__(self) -> bool: ...


NotBound: NotBoundType


@data_type
@dataclass(frozen=True)
class Outcome(Generic[T]):
    """Encapsulates the result of evaluating an operation."""
    ...


@data_type
@dataclass(frozen=True)
class Value(Outcome[T], Generic[T]):
    """Wraps a successful return value."""
    val: T

    def unwrap(self) -> T: ...


@data_type
@dataclass(frozen=True)
class Raised(Outcome[Any]):
    """Wraps an expected or intercepted exception."""
    exc: BaseException
    message: str = ""

    def unwrap(self) -> Any: ...


@data_type
class PretenseError(Exception):
    """Base exception for all Pretense errors."""
    ...


@data_type
class UnsatisfiedAntecedentError(PretenseError):
    """Raised when an argument domain cannot generate values in the current state."""
    ...


@data_type
class NoMatchingTransitionError(PretenseError):
    """Raised when no transition's requirements and argument recognizers match a call."""
    ...


@data_type
class AmbiguousTransitionError(PretenseError):
    """Raised when more than one candidate transition matches a call."""
    ...


@data_type
class DrawContext:
    """Manages dynamic scope binding for property-based test sampling."""

    def get_current_draw(self) -> Optional[Callable[..., Any]]: ...
    def with_draw(self, draw_fn: Optional[Callable[..., Any]]) -> Any: ...


@data_type
class PretenseSpecificationError(PretenseError):
    """Raised when a state machine contract, transition invariant, or antecedent predicate is violated."""
    ...


@data_type
@dataclass(frozen=True)
class TraceStep:
    """Records an executed state transition step within a run trace."""
    transition_name: str
    target_name: Optional[str] = None
    is_seeding: bool = False
    args: Tuple[Any, ...] = ...
    kwargs: Dict[str, Any] = ...
    outcome: Optional[Any] = None


@data_type
@dataclass
class PretenseRunnerConfig:
    """Configuration governing test discovery, fuzzing, coverage, and watchdogs."""
    target_paths: List[str]
    fuzz: bool = True
    cov: bool = False
    cov_threshold: float = 100.0
    timeout: float = 45.0
    synthesize: bool = False


@data_type
@dataclass
class PretenseRunResult:
    """Summary metrics of test execution."""
    passed: int = 0
    failed: int = 0
    coverage_pct: float = 0.0
    counterexamples: List[List[TraceStep]] = ...
    is_passing: bool = True


@data_type
class RequiresCheck:
    """Precondition check helper that records failure flags and reasons without exception overhead."""
    ok: bool
    reasons: List[str]

    def __init__(self) -> None: ...
    def __call__(self, condition: bool, reason: str = "") -> bool: ...


@data_type
class require:
    """Precondition requirement assertion enforcing state machine antecedents."""
    def __init__(
        self,
        condition: bool,
        reason_or_exc: Union[str, Type[PretenseSpecificationError]] = "",
        exc_class: Optional[Type[PretenseSpecificationError]] = None,
    ) -> None: ...
    def __call__(
        self,
        condition: bool,
        reason_or_exc: Union[str, Type[PretenseSpecificationError]] = "",
        exc_class: Optional[Type[PretenseSpecificationError]] = None,
    ) -> None: ...


@data_type
class requires(require):
    """Precondition requirement assertion enforcing state machine antecedents."""
    ...


@data_type
class require_arg(Generic[T]):
    """Argument domain validation and preferred candidate binding."""
    @overload
    def __init__(
        self,
        val: Sequence[E],
        domain: Union[Domain[Sequence[E]], Domain[List[E]], Domain[Tuple[E, ...]]],
        preferred: Optional[Sequence[Sequence[E]]] = None,
    ) -> None: ...
    @overload
    def __init__(
        self,
        val: Optional[Sequence[E]],
        domain: Union[Domain[Optional[Sequence[E]]], Domain[Optional[List[E]]], Domain[Optional[Tuple[E, ...]]]],
        preferred: Optional[Sequence[Optional[Sequence[E]]]] = None,
    ) -> None: ...
    @overload
    def __init__(
        self,
        val: T,
        domain: Domain[T],
        preferred: Optional[Sequence[T]] = None,
    ) -> None: ...
    @overload
    def __call__(
        self,
        val: Sequence[E],
        domain: Union[Domain[Sequence[E]], Domain[List[E]], Domain[Tuple[E, ...]]],
        preferred: Optional[Sequence[Sequence[E]]] = None,
    ) -> None: ...
    @overload
    def __call__(
        self,
        val: Optional[Sequence[E]],
        domain: Union[Domain[Optional[Sequence[E]]], Domain[Optional[List[E]]], Domain[Optional[Tuple[E, ...]]]],
        preferred: Optional[Sequence[Optional[Sequence[E]]]] = None,
    ) -> None: ...
    @overload
    def __call__(
        self,
        val: T,
        domain: Domain[T],
        preferred: Optional[Sequence[T]] = None,
    ) -> None: ...


@data_type
class ensure:
    """Postcondition assertion verifying invariants over model state and test singletons."""
    def __init__(self, condition: bool, reason: str = "") -> None: ...
    def __call__(self, condition: bool, reason: str = "") -> None: ...


@data_type
class make_return_value:
    """Pivot in an interface state machine transition."""
    def __new__(cls, fake_val: Optional[Any] = None) -> Any: ...
    def __call__(self, fake_val: Optional[Any] = None) -> Any: ...


@data_type
class call_target(Generic[R]):
    """Pivot in an implementation pseudo state machine transition."""
    @overload
    def __new__(cls, target_call: Type[R]) -> R: ...
    @overload
    def __new__(cls, target_call: R) -> R: ...
    @overload
    def __call__(self, target_call: Type[R]) -> R: ...
    @overload
    def __call__(self, target_call: R) -> R: ...


@data_type
class raises:
    """Context manager asserting that an operation under test raises a contracted exception."""
    def __init__(self, exc_type: Type[BaseException]) -> None: ...
    def __enter__(self) -> raises: ...
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool: ...


@data_type
class sut(Generic[T]):
    """Resolves a registered singleton under test or collaborator from dynamic context."""
    def __new__(cls, singleton_type: Type[T]) -> T: ...
    def __call__(self, singleton_type: Type[T]) -> T: ...


@data_type
class sut_state:
    """Resolves active state model for a collaborator or target."""
    def __new__(cls, state_cls: Type[StateT]) -> StateT: ...
    def __call__(self, state_cls: Type[StateT]) -> StateT: ...


@data_type
class test_only:
    """Decorator marking an interface method or property as test-only observability query."""
    def __new__(cls, fn: T) -> T: ...
    def __call__(self, fn: T) -> T: ...


@data_type
class unreachable:
    """Marks an unreachable code path, impossible branch, or defensive dead-end."""
    def __new__(cls, reason: str = ...) -> Any: ...
    def __call__(self, reason: str = ...) -> Any: ...


@data_type
class ensure_ret(Generic[T]):
    """Wrapped execution verifying return value against an expected domain or value."""
    def __new__(
        cls,
        call_expr: T,
        domain: Optional[Domain[T]] = None,
        preferred: Optional[Sequence[T]] = None,
    ) -> T: ...
    def __init__(
        self,
        call_expr: T,
        domain: Optional[Domain[T]] = None,
        preferred: Optional[Sequence[T]] = None,
    ) -> None: ...


@data_type
class ensure_raises:
    """Wrapped execution verifying that an operation under test raises a contracted exception."""
    def __init__(
        self,
        call_expr: Any,
        exc_type: Type[BaseException],
        match: str = "",
    ) -> None: ...


@data_type
class EnsuresCheck:
    """Postcondition check helper providing assertion checks, equality diffs, and singleton lookup."""
    singletons: Dict[Type[Any], Any]

    def __init__(self, singletons: Optional[Dict[Type[Any], Any]] = None) -> None: ...
    def __call__(self, condition: bool, msg: str = "") -> None: ...
    def equal(self, actual: Any, expected: Any, msg: str = "") -> None: ...
    def get(self, singleton_type: Type[T]) -> T: ...


@data_type
class Domain(Generic[T]):
    """Specification of an argument domain uniting generative sampling and analytical validation."""
    strategy: Any
    validator: Optional[Callable[[T], bool]]
    default: Any

    def __init__(
        self,
        strategy: Union[Callable[..., T], Any],
        validator: Optional[Callable[[T], bool]] = None,
        default: Any = ...,
    ) -> None: ...
    def to_strategy(self) -> Any: ...
    def validate(self, val: Any) -> bool: ...

    @classmethod
    def set(cls, items: Collection[T]) -> Domain[T]: ...
    @classmethod
    def in_set(cls, items: Collection[T]) -> Domain[T]: ...
    @classmethod
    def not_in(
        cls,
        items: Collection[T],
        base: Optional[Any] = None,
        base_type: Optional[Type[T]] = None,
        prefix: str = "item_",
    ) -> Domain[T]: ...
    @classmethod
    def any(cls) -> Domain[Any]: ...
    @classmethod
    def subset_of(cls, items: Collection[T]) -> Domain[Set[T]]: ...
    @classmethod
    def sampled_from(cls, items: Collection[T]) -> Domain[T]: ...
    @classmethod
    def just(cls, val: Union[T, Expr[T]]) -> Domain[T]: ...
    @classmethod
    def range(cls, start: Any, stop: Any, step: int = 1) -> Domain[int]: ...
    @classmethod
    def integers(cls, min_value: Optional[int] = None, max_value: Optional[int] = None) -> Domain[int]: ...
    @classmethod
    def regex(cls, pattern: Union[str, Any]) -> Domain[str]: ...
    @overload
    @classmethod
    def type(cls, target_cls: Type[T], validator: Optional[Callable[[Any], bool]] = None, **kwargs: Any) -> Domain[T]: ...
    @overload
    @classmethod
    def type(cls, target_cls: Any, validator: Optional[Callable[[Any], bool]] = None, **kwargs: Any) -> Domain[Any]: ...
    @classmethod
    def tuple_of(cls, *elem_domains: Any) -> Domain[Tuple[Any, ...]]: ...
    @classmethod
    def object(cls, target_cls: Type[T], **field_domains: Any) -> Domain[T]: ...
    @classmethod
    def newtype(cls, newtype_cls: Any, inner_domain: Any) -> Domain[Any]: ...
    @classmethod
    def list_of(cls, elem_domain: Union[Domain[E], Type[E]], min_size: int = 0, max_size: int = 5, unique: bool = False) -> Domain[List[E]]: ...
    @classmethod
    def set_of(cls, elem_domain: Union[Domain[E], Type[E]], min_size: int = 0, max_size: int = 5) -> Domain[Set[E]]: ...
    @classmethod
    def mapping_of(cls, key_domain: Union[Domain[K], Type[K]], val_domain: Union[Domain[V], Type[V]], min_size: int = 0, max_size: int = 5) -> Domain[Dict[K, V]]: ...
    @classmethod
    def optional(cls, inner_domain: Union[Domain[E], Type[E]]) -> Domain[Optional[E]]: ...
    @classmethod
    def none(cls) -> Domain[None]: ...
    @classmethod
    def boolean(cls) -> Domain[bool]: ...
    @classmethod
    def text(cls, min_size: int = 0, max_size: Optional[int] = None, alphabet: Any = None) -> Domain[str]: ...
    @classmethod
    def perturb(
        cls,
        anchor: Any,
        mutations: Sequence[Any],
        validator: Callable[[Any], bool],
    ) -> Domain[T]: ...
    @classmethod
    def required(cls, name: str = "") -> Domain[Any]: ...
    @classmethod
    def of(cls, val: Any) -> Domain[Any]: ...


@data_type
class Expr(Generic[T]):
    """Lifted symbolic parameter or return outcome expression for a state transition."""
    name: str
    is_return: bool

    def __init__(self, name: str = "", is_return: bool = False) -> None: ...
    def constrain(self, domain_or_val: Any) -> None: ...
    def raises(self, exc_type: Type[BaseException], match: Any = "") -> None: ...
    def value(self) -> T: ...
    def is_bound(self) -> bool: ...
    def __add__(self, other: Any) -> Expr[Any]: ...
    def __radd__(self, other: Any) -> Expr[Any]: ...
    def __sub__(self, other: Any) -> Expr[Any]: ...
    def __rsub__(self, other: Any) -> Expr[Any]: ...
    def __mul__(self, other: Any) -> Expr[Any]: ...
    def __rmul__(self, other: Any) -> Expr[Any]: ...
    def __getattr__(self, attr: str) -> Expr[Any]: ...
    def __getitem__(self, key: Any) -> Expr[Any]: ...


@data_type
class TransitionContext(Generic[Target, P, R]):
    """Context for specifying requires, argument, return, ensures, and update handlers for a transition."""
    updates: bool
    target: Optional[Target]
    check: EnsuresCheck

    def requires(self, fn: Union[bool, Callable[[RequiresCheck], Any], Callable[[], bool]], reason: str = "") -> None: ...
    def antecedent(self, predicate: Union[bool, Callable[[], bool]], reason: str = "") -> None: ...
    def check_equal(self, actual: Any, expected: Any, msg: str = "") -> None: ...
    def get(self, singleton_type: Type[T]) -> T: ...

    def arguments(self, *domains: Any, **kw_domains: Any) -> None: ...

    @overload
    def returns(self, fn: Callable[P, Union[R, Outcome[R], Outcome[Any], None]]) -> None: ...

    @overload
    def returns(self, fn: Callable[[], Union[R, Outcome[R], Outcome[Any], None]]) -> None: ...

    @overload
    def returns(self, fn: Callable[..., Union[R, Outcome[R], Outcome[Any], None]]) -> None: ...

    @overload
    def returns(self, fn: Union[R, Outcome[R], Outcome[Any]]) -> None: ...

    def ensures(self, fn: Callable[..., Any]) -> None: ...

    @overload
    def update(self, fn: Callable[Concatenate[Any, P], Any]) -> None: ...

    @overload
    def update(self, fn: Callable[[Any], Any]) -> None: ...

    @overload
    def update(self, fn: Callable[[], Any]) -> None: ...

    @overload
    def update(self, fn: Callable[..., Any]) -> None: ...

    @overload
    def consequent(self, fn: Callable[Concatenate[Any, P], Any]) -> None: ...

    @overload
    def consequent(self, fn: Callable[[Any], Any]) -> None: ...

    @overload
    def consequent(self, fn: Callable[[], Any]) -> None: ...

    @overload
    def consequent(self, fn: Callable[..., Any]) -> None: ...

    def raises(self, exc_type: Type[Exception], match: str = "") -> None:
        """Declares an expected exception outcome for this transition.

        Raises:
            ValueError: If ctx.returns has already been declared on this context.
        """
        ...


@data_type
class transition:
    """Decorator registering a transition method against a target singleton operation."""
    target: Optional[Any]
    name: Optional[str]
    is_seeding: bool

    @overload
    def __init__(self, target: Callable[Concatenate[Target, P], R], *, name: Optional[str] = None, is_seeding: bool = False) -> None: ...

    @overload
    def __init__(self, target: Callable[P, R], *, name: Optional[str] = None, is_seeding: bool = False) -> None: ...

    @overload
    def __init__(self, target: None = None, *, name: Optional[str] = None, is_seeding: bool = False) -> None: ...

    @staticmethod
    def seeding(*, name: Optional[str] = None) -> transition: ...

    def __call__(
        self,
        fn: Callable[..., None],
    ) -> Any: ...


@data_type
class Transition:
    """Declarative state transition model."""
    name: str
    target: Optional[Any]
    is_seeding: bool
    requirements: List[Callable[..., bool]]
    args_fn: Optional[Callable[..., Any]]
    return_fn: Optional[Callable[..., Any]]
    ensure_fn: Optional[Callable[..., Any]]
    provider: Optional[Callable[..., Any]]

    def __init__(
        self,
        name: str,
        target: Optional[Any] = None,
        is_seeding: bool = False,
    ) -> None: ...

    def require(self, fn: Callable[..., bool]) -> Callable[..., bool]: ...
    def requires(self, fn: Callable[..., bool]) -> Callable[..., bool]: ...
    def arguments(self, fn: Callable[..., Any]) -> Callable[..., Any]: ...
    def returns(self, fn: Callable[..., Any]) -> Callable[..., Any]: ...
    def ensures(self, fn: Callable[..., Any]) -> Callable[..., Any]: ...
    def provide(self, fn: Callable[..., None]) -> Callable[..., None]: ...
    def update(self, fn: Callable[..., None]) -> Callable[..., None]: ...


@data_type
class StateMachineProto(Generic[StateT]):
    """Structural prototype for Pretense state machine definitions."""

    transitions: List[Transition]
    invariants: List[Callable[..., None]]

    @operation
    def __init__(self) -> None: ...

    @operation
    def transition(
        self,
        method: Optional[Any] = None,
        *,
        name: Optional[str] = None,
    ) -> Callable[[Callable[..., Any]], Transition]:
        """Declare an object method or property transition matching an interface Protocol."""
        ...

    @operation
    def seeding(self) -> Callable[[Callable[..., Any]], Transition]:
        """Declare a seeding transition for environment and test configuration."""
        ...

    @operation
    def invariant(self, fn: Callable[..., None]) -> Callable[..., None]:
        """Register a cross-cutting invariant."""
        ...

    @operation
    def as_fake(self) -> Any:
        """Compiles this state machine into a dynamic test double conforming to an interface protocol."""
        ...

    @operation
    def make_state_machine(self, initial_state: Any) -> StateMachine:
        """Instantiates an active state machine from this prototype."""
        ...

    @operation
    def make_fake(self, protocol_type: Type[Any], initial_state: Any) -> Any:
        """Instantiates a fake directly for the target protocol."""
        ...


@data_type
class StateMachine(Generic[StateT]):
    """Base class for Pretense state machines."""
    state: StateT
    transitions: List[Transition]
    invariants: List[Callable[..., None]]
    singletons: Dict[Type[Any], Any]

    def __init__(
        self,
        state: Any = None,
        transitions: Optional[List[Transition]] = None,
        invariants: Optional[List[Callable[..., None]]] = None,
        singletons: Optional[Dict[Type[Any], Any]] = None,
    ) -> None: ...

    @classmethod
    def register_compiler(cls, compiler: Callable[..., Any]) -> None: ...
    def bind_singleton(self, target_type: Type[Any], instance: Any) -> None: ...
    def get_singleton(self, target_type: Type[T]) -> T: ...
    def sut(self, target_type: Type[T]) -> T: ...
    def as_fake(self, protocol_type: Optional[Type[T]] = None) -> T: ...
    def as_checked(self, protocol_type: Type[T], real_instance: Optional[T] = None) -> T: ...
    def bind(self, target: Any) -> Any: ...
    def make_state_machine(self, initial_state: Any) -> StateMachine: ...
    def check_invariants(self) -> None: ...
    def dispatch_transition(self, transition_name: Any, *args: Any, **kwargs: Any) -> Any: ...
    def to_hypothesis_test_case(self, settings: Optional[Any] = None, name: Optional[str] = None) -> Type[Any]: ...


@data_type
class CheckedAdapter:
    """Verification proxy conforming to an interface protocol that dispatches through a state machine and real singleton."""

    def __init__(
        self,
        target_protocol: Type[Any],
        state_machine: Any,
        real_instance: Optional[Any] = None,
    ) -> None: ...

    def __getattr__(self, name: str) -> Any: ...


@data_type
class FakeAdapter:
    """Dynamic test double conforming to an interface protocol."""

    def __init__(
        self,
        target_protocol: Type[Any],
        state: Any = None,
        transitions: Optional[List[Transition]] = None,
        state_machine: Any = None,
    ) -> None: ...

    def __getattr__(self, name: str) -> Any: ...


@singleton_type("system")
class PretenseEngine(Singleton[SystemTier], Protocol):
    """System-tier service coordinating state machine compilation, test execution, and fake generation."""

    @operation
    def compile_state_machine(self, machine_cls: Type[Any]) -> Type[Any]:
        """Compiles a declarative state machine class into an executable Hypothesis test case.

        POSTCONDITIONS:
        - MUST return an executable test case class.
        """
        ...

    @operation
    def run_suite(self, config: PretenseRunnerConfig) -> PretenseRunResult:
        """Executes pretense test suites according to runner configuration.

        POSTCONDITIONS:
        - MUST return a populated PretenseRunResult.
        """
        ...

    @operation
    def synthesize_test(self, target_cls: Type[Any], trace: Sequence[TraceStep]) -> str:
        """Synthesizes a minimal standalone unit test from a counterexample trace.

        POSTCONDITIONS:
        - MUST return valid Python test code as a string.
        """
        ...

    @operation
    def synthesize_fake(self, machine_cls: Type[Any]) -> Type[Any]:
        """Synthesizes a pure in-memory test double class from a linear state machine.

        POSTCONDITIONS:
        - MUST return an executable test double class.
        """
        ...


@data_type
class synthesize_fake:
    """Synthesizes a pure in-memory test double class from a state machine."""
    def __new__(cls, machine_cls: Type[StateMachine[Any]], fake_name: Optional[str] = None) -> Type[Any]: ...
    def __call__(self, machine_cls: Type[StateMachine[Any]], fake_name: Optional[str] = None) -> Type[Any]: ...


@data_type
class compile_hypothesis_test_case:
    """Compiles a StateMachine into an executable Hypothesis test case."""
    def __new__(
        cls,
        machine_cls: Type[StateMachine[Any]],
        target_cls: Optional[Type[Any]] = None,
        *,
        name: Optional[str] = None,
        max_examples: int = 50,
    ) -> Type[Any]: ...
    def __call__(
        self,
        machine_cls: Type[StateMachine[Any]],
        target_cls: Optional[Type[Any]] = None,
        *,
        name: Optional[str] = None,
        max_examples: int = 50,
    ) -> Type[Any]: ...



