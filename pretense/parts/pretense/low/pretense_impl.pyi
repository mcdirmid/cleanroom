"""Low-level implementation specification for pretense_impl."""

from typing import Any, Mapping, Optional, Sequence, Tuple, Type
import hypothesis
from support.lib.framework import data_type, operation, override, singleton_type
from support.lib.lifecycle import Singleton, SystemTier
import pretense


@singleton_type("system")
class PretenseEngine(pretense.PretenseEngine):
    """Realizes state machine compilation, test suite execution, watchdog timeouts, and fake synthesis.

    GROUNDING:
    - Realizes pretense.PretenseEngine as the pretense_service knowledge provision using hypothesis
      to compile declarative state machines into hypothesis RuleBasedStateMachine test cases,
      tracking active transition steps, enforcing dual-layer execution watchdogs, and evaluating coverage.
    """

    @operation
    @override
    def compile_state_machine(self, machine_cls: Type[Any]) -> Type[Any]:
        """Compiles a declarative state machine class into an executable Hypothesis test case.

        GROUNDING:
        - Inspects declared transitions and constructs a dynamic RuleBasedStateMachine subclass.

        POSTCONDITIONS:
        - MUST return an executable test case class.
        """
        ...

    @operation
    @override
    def run_suite(self, config: pretense.PretenseRunnerConfig) -> pretense.PretenseRunResult:
        """Executes pretense test suites according to runner configuration.

        GROUNDING:
        - Discovers test targets, arms watchdogs, runs pytest/pretense, and verifies coverage
          (against implementation modules excluding abstract interface stubs, or strictly against the interface pretense file itself for pure interface pretense modules),
          suppressing property fuzzing during implementation coverage evaluation to bound execution to deterministic test suites while keeping fuzzing enabled for interface pretense coverage and QA verification,
          formatting and reporting test failure details across failed test methods to prevent defect masking while prioritizing the shortest failure traceback when multiple failures or an exception group occurs to isolate the minimal reproduction,
          formatting auditor guidance reminders upon test failures and coverage deficits directing the agent to formulate blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files, and instructing the agent when an uncovered line persists across rounds or after test updates to examine the library implementation closely to determine whether the line is structurally or logically unreachable,
          failing when test files cannot be loaded, tests fail, coverage is unmet, or zero targets are discovered.

        POSTCONDITIONS:
        - MUST return a populated PretenseRunResult.
        """
        ...

    @operation
    @override
    def synthesize_test(self, target_cls: Type[Any], trace: Sequence[pretense.TraceStep]) -> str:
        """Synthesizes a minimal standalone unit test from a counterexample trace.

        GROUNDING:
        - Formats trace steps into Python source code with literal inputs.

        POSTCONDITIONS:
        - MUST return valid Python test code as a string.
        """
        ...

    @operation
    @override
    def synthesize_fake(self, machine_cls: Type[Any]) -> Type[Any]:
        """Synthesizes a pure in-memory test double class from a linear state machine.

        GROUNDING:
        - Inspects AST of the state machine, strips SUT parameters and assertions, and returns an in-memory double class.

        POSTCONDITIONS:
        - MUST return an executable test double class.
        """
        ...


@data_type
class ActiveStepTracker:
    """Tracks active transition steps and state snapshots for diagnostics."""

    @staticmethod
    def get_active_step() -> Optional[Tuple[str, Tuple[Any, ...], Mapping[str, Any]]]: ...

    @staticmethod
    def format_active_step_diagnostic(
        prefix: str = "Active Step at failure",
        target_name: Optional[str] = None,
    ) -> str: ...


@data_type
class WatchdogMonitor:
    """Coordinates execution watchdogs using software timers and faulthandler alarms."""

    @staticmethod
    def resolve_timeout(default: float = 45.0) -> float: ...

    @staticmethod
    def arm(timeout_seconds: float, target_name: Optional[str] = None) -> Any: ...

    @staticmethod
    def disarm(handle: Any) -> None: ...
