"""Low-level interface specification for pretense."""

from dataclasses import dataclass
from typing import (
    Annotated,
    Any,
    Callable,
    Collection,
    Concatenate,
    Dict,
    Generic,
    List,
    Mapping,
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
T_co = TypeVar("T_co", covariant=True, default=Any)
Target = TypeVar("Target", default=Any)
P = ParamSpec("P", default=...)
R = TypeVar("R", default=Any)
E = TypeVar("E", default=Any)
K = TypeVar("K", default=Any)
S_Dom = TypeVar("S_Dom")
T_Dom = TypeVar("T_Dom")
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
class _EnvStateMarker:
    """Marker metadata distinguishing environmental state fields on State dataclasses."""
    ...


Env = Annotated[T, _EnvStateMarker]


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
class require:
    """Precondition requirement assertion enforcing state machine antecedents."""
    def __init__(
        self,
        condition: bool,
        reason_or_exc: Union[str, Type[BaseException]] = "",
        exc_class: Optional[Type[BaseException]] = None,
        error: Optional[Union[Type[BaseException], BaseException]] = None,
    ) -> None: ...
    def __call__(
        self,
        condition: bool,
        reason_or_exc: Union[str, Type[BaseException]] = "",
        exc_class: Optional[Type[BaseException]] = None,
        error: Optional[Union[Type[BaseException], BaseException]] = None,
    ) -> None: ...


@data_type
class requires(require):
    """Precondition requirement assertion enforcing state machine antecedents."""
    ...


@data_type
class require_env:
    """Virtual environmental requirement enforcing external operational conditions.

    When `condition` is False: in Fake mode, immediately raises `exception_cls(*args, **kwargs)`;
    in Implementation mode, expects the real SUT to raise `exception_cls` (failing if it returns normally).
    """
    def __init__(
        self,
        condition: bool,
        exception_cls: Union[Type[BaseException], BaseException],
        *args: Any,
        **kwargs: Any,
    ) -> None: ...
    def __call__(
        self,
        condition: bool,
        exception_cls: Union[Type[BaseException], BaseException],
        *args: Any,
        **kwargs: Any,
    ) -> None: ...


class DomainWrapper(Generic[S_Dom, T_Dom]):
    """Bound or unbound procedural domain recognizer with finite-sequence candidate producers."""
    fn: Callable[[S_Dom, T_Dom], bool]
    valid: Optional[Callable[[S_Dom], Sequence[T_Dom]]]
    invalid: Optional[Callable[[S_Dom], Sequence[object]]]

    def __init__(
        self,
        fn: Callable[[S_Dom, T_Dom], bool],
        valid: Optional[Callable[[S_Dom], Sequence[T_Dom]]] = None,
        invalid: Optional[Callable[[S_Dom], Sequence[object]]] = None,
    ) -> None: ...
    @overload
    def __get__(self, instance: None, owner: type[S_Dom]) -> "DomainWrapper[S_Dom, T_Dom]": ...
    @overload
    def __get__(self, instance: S_Dom, owner: type[S_Dom]) -> "DomainWrapper[S_Dom, T_Dom]": ...
    def __call__(self, val: object) -> bool: ...
    def validate(self, val: object) -> bool: ...


def domain(
    valid: Optional[Callable[[S_Dom], Sequence[T_Dom]]] = None,
    invalid: Optional[Callable[[S_Dom], Sequence[object]]] = None,
) -> Callable[[Callable[[S_Dom, T_Dom], bool]], DomainWrapper[S_Dom, T_Dom]]: ...


@data_type
class require_arg(Generic[T]):
    """Argument requirement validation and candidate generation binding."""
    def __init__(
        self,
        val: Any,
        requirement: Any,
        error: Optional[Union[Type[BaseException], BaseException]] = None,
        *,
        fuzz_domain: Optional[Any] = None,
    ) -> None: ...
    def __call__(
        self,
        val: Any,
        requirement: Any,
        error: Optional[Union[Type[BaseException], BaseException]] = None,
        *,
        fuzz_domain: Optional[Any] = None,
    ) -> None: ...


@data_type
class raises:
    """Context manager asserting that an operation under test raises a contracted exception, or synthesizing the exception in Fake mode."""
    def __init__(self, exc_type: Type[BaseException]) -> None: ...
    def __enter__(self) -> raises: ...
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool: ...


@data_type
class sut(Generic[T]):
    """Resolves a registered singleton under test or collaborator from dynamic context."""
    def __new__(cls, singleton_type: Type[T]) -> T: ...
    def __call__(self, singleton_type: Type[T]) -> T: ...


@data_type
class test_only:
    """Decorator marking an interface method or property as test-only observability query."""
    def __new__(cls, fn: T) -> T: ...
    def __call__(self, fn: T) -> T: ...


@data_type
class unreachable:
    """Marks an unreachable code path, impossible branch, or defensive dead-end.

    `__enter__()` raises `UnreachableBranchError` unconditionally on entry; always
    place `with unreachable:` INSIDE the impossible conditional branch, never
    wrapping an `if` block.
    """
    def __new__(cls, reason: str = ...) -> Any: ...
    def __call__(self, reason: str = ...) -> Any: ...
    def __enter__(self) -> None: ...
    def __exit__(self, *args: Any) -> None: ...


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
        fn: Callable[..., Any],
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
    def sut(self, target_type: Type[T]) -> T:
        """Resolves `target_type` from `self.singletons` (or active lifecycle registry/fakes). Raises if unbound or None."""
        ...
    def as_fake(self, protocol_type: Optional[Type[T]] = None) -> T: ...
    def as_checked(self, protocol_type: Type[T], real_instance: Optional[T] = None) -> CheckedAdapter[T]:
        """Returns a CheckedAdapter wrapping `real_instance` (and binding it into `singletons[protocol_type]` if provided)."""
        ...
    def bind(self, target: T) -> CheckedAdapter[T]: ...
    def make_state_machine(self, initial_state: Any) -> StateMachine: ...
    def check_invariants(self) -> None: ...
    def dispatch_transition(self, transition_name: Any, *args: Any, **kwargs: Any) -> Any: ...
    def to_hypothesis_test_case(self, settings: Optional[Any] = None, name: Optional[str] = None) -> Type[Any]: ...


@data_type
class CheckedAdapter(Generic[T]):
    """Verification proxy conforming to an interface protocol that dispatches through a state machine and real singleton."""

    def __init__(
        self,
        target_protocol: Type[Any],
        state_machine: Any,
        real_instance: Optional[Any] = None,
    ) -> None: ...

    def violating(self, exc_type: Optional[Type[BaseException]] = None, match: str = "") -> T: ...

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


def synthesize_fake(
    machine_cls: Type[StateMachine[Any]],
    fake_name: Optional[str] = None,
) -> Type[Any]:
    """Synthesizes a pure in-memory test double class from a state machine.

    On transition calls: `require(...)` / `require_arg(...)` guard failures raise `NoMatchingTransitionError`;
    `require_env(...)` guard failures raise `exception_cls(*args, **kwargs)`.
    """
    ...


@data_type
class compile_hypothesis_test_case:
    """Compiles a StateMachine into an executable Hypothesis test case."""
    def __new__(
        cls,
        machine_cls: Type[StateMachine[Any]],
        target_cls: Optional[Type[Any]] = None,
        *,
        sut_factory: Optional[Callable[[], Any]] = None,
        name: Optional[str] = None,
        max_examples: int = 50,
        collaborators: Optional[Sequence[Any]] = None,
    ) -> Type[Any]: ...
    def __call__(
        self,
        machine_cls: Type[StateMachine[Any]],
        target_cls: Optional[Type[Any]] = None,
        *,
        sut_factory: Optional[Callable[[], Any]] = None,
        name: Optional[str] = None,
        max_examples: int = 50,
        collaborators: Optional[Sequence[Any]] = None,
    ) -> Type[Any]: ...



