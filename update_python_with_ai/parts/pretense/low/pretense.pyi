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
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
    runtime_checkable,
)
from support.lib.framework import data_type, operation, poly_type, singleton_type
from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T")
Target = TypeVar("Target")
P = ParamSpec("P")
R = TypeVar("R")
StateT = TypeVar("StateT")
SelfT = TypeVar("SelfT")


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
    def range(cls, start: int, stop: int, step: int = 1) -> Domain[int]: ...
    @classmethod
    def regex(cls, pattern: Union[str, Any]) -> Domain[str]: ...
    @classmethod
    def type(cls, target_cls: Type[T]) -> Domain[T]: ...
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
class TransitionContext(Generic[Target, P, R]):
    """Context for specifying requires, argument, return, ensures, and update handlers for a transition."""

    def requires(self, fn: Union[Callable[[RequiresCheck], Any], Callable[[], bool]]) -> None: ...
    def antecedent(self, predicate: Callable[[], bool]) -> None: ...

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
        fn: Callable[[SelfT, TransitionContext[Target, P, R]], None],
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
    def arguments(self, fn: Callable[..., Any]) -> Callable[..., Any]: ...
    def returns(self, fn: Callable[..., Any]) -> Callable[..., Any]: ...
    def provide(self, fn: Callable[..., None]) -> Callable[..., None]: ...


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
    state: Any
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

    def bind_singleton(self, target_type: Type[Any], instance: Any) -> None: ...
    def get_singleton(self, target_type: Type[T]) -> T: ...
    def as_fake(self, protocol_type: Optional[Type[Any]] = None) -> Any: ...
    def make_state_machine(self, initial_state: Any) -> StateMachine: ...
    def check_invariants(self) -> None: ...
    def dispatch_transition(self, transition_name: str, *args: Any, **kwargs: Any) -> Any: ...
    def to_hypothesis_test_case(self, settings: Optional[Any] = None, name: Optional[str] = None) -> Type[Any]: ...
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
