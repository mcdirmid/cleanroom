# Concrete scenarios for `pretense_impl` (implementation)

## Scenario 1 — Compiling state machine to Hypothesis test case

Given: a state machine class defining linear transitions, preconditions, argument domains, wrapped calls, and invariants.

1. The compiler transforms the class into a `RuleBasedStateMachine` test case.
   Observed: rules are generated for each declared transition, require guards are mapped to assumption preconditions, argument domains generate values with preferred weighting, wrapped calls verify returns and exceptions, ensures validate postconditions against concrete singletons, and invariants are attached.

2. The strategy validator analyzes transition argument requirements against candidate states.
   Observed: argument existence preconditions are verified statically, preventing empty domain generation failures during fuzzing.

3. The runner executes the compiled test case across 50 iterations.
   Observed: random valid operation sequences execute without invariant violations.

## Scenario 2 — Pure fake double synthesis

Given: a state machine class defining linear transitions with wrapped calls and postconditions.

1. The fake synthesizer compiles the state machine into an in-memory test double class.
   Observed: parameters target and suts are removed, wrapped calls and ensure assertions are stripped, argument validation is preserved, model state updates are preserved, and expected return values or contracted exceptions are emitted.

## Scenario 3 — Active step diagnostic tracking

Given: a state machine executing an operation that encounters an invariant failure.

1. The active step diagnostic tracker records the transition name and argument values.
   Observed: `get_active_step` returns the active transition context.

2. The diagnostic formatter generates a failure summary.
   Observed: the formatted output details the transition name, arguments, state snapshot, and contextual diagnostic reasons when return recognizers reject SUT outcomes.

## Scenario 4 — Unit test synthesis from counterexample trace

Given: a shrunken sequence of trace steps leading to an assertion violation.

1. The unit test synthesizer compiles the trace steps into standalone Python source code.
   Observed: the output contains a valid Python test function instantiating the implementation under test and reproducing the step sequence with literal arguments.

## Scenario 5 — Execution watchdog timeout protection

Given: a test suite containing an infinite loop or hanging operation.

1. The watchdog monitor arms a timer warning and a faulthandler timeout.
   Observed: the timer prints an active step warning before expiration, and faulthandler dumps the active traceback to standard error and terminates execution if the timeout limit is reached.

2. The watchdog monitor executes a quick test that completes before timeout.
   Observed: watchdog timers are cleanly disarmed upon completion without interrupting the process.

## Scenario 6 — Test discovery and coverage evaluation

Given: a directory containing `*_pretense.py` test files.

1. The test runner discovers target test files and runs them with coverage tracking enabled.
   Observed: discovered tests execute with property fuzzing suppressed during coverage evaluation to bound execution to deterministic test suites while reserving fuzzing for QA verification, statement coverage is measured for corresponding implementation modules (excluding abstract interface stubs), and any lines missing coverage below the threshold are reported along with auditor guidance reminders directing the agent to formulate blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files, and instructing the agent when an uncovered line persists across rounds or after test updates to examine the library implementation closely to determine whether the line is structurally or logically unreachable.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-31T00:50:00Z
LAST_CHANGED: 2026-11-03T23:45:00Z
CHANGE: Instruct coverage auditor when uncovered lines persist to examine library implementation for unreachable code
-->

2. A target test file has import or syntax errors or contains no executable test targets.
   Observed: the test runner raises or reports target loading errors and exits with a non-zero status code rather than reporting success.

## Scenario 7 — CLI entry point execution

Given: command-line arguments specifying `--cov`, `--no-fuzz`, `--timeout 10.0`, and target test paths.

1. The CLI entry point parses the arguments and invokes the test runner.
   Observed: the runner executes the specified suite with the configured timeout, fuzzing disabled, and coverage verification active, exiting with code 0 on success.

2. A test suite fails, a target module fails to import, or zero test targets are found.
   Observed: the runner outputs diagnostic error messages containing formatted failure and error details across failed test methods, prioritizing the shortest failure traceback when multiple failures or an exception group occurs to isolate the minimal reproduction, includes auditor guidance reminders directing the agent to formulate blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files, and exits with a non-zero status code.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-31T00:50:00Z
LAST_CHANGED: 2026-11-09T12:35:00Z
CHANGE: Prioritize shortest failure traceback in runner error reporting when multiple failures or exception groups occur
SPEC_QA_AUDIT: 2026-10-31T00:50:00Z
-->
