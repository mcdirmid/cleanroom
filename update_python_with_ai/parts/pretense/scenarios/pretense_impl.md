# Concrete scenarios for `pretense_impl` (implementation)

## Scenario 1 — Compiling state machine to Hypothesis test case

Given: a state machine class defining transitions, preconditions, and invariants.

1. The compiler transforms the class into a `RuleBasedStateMachine` test case.
   Observed: rules are generated for each declared transition, requires guards are mapped to rule preconditions, ensures postconditions are verified against the concrete system under test, and invariants are attached.

2. The runner executes the compiled test case across 50 iterations.
   Observed: random valid operation sequences execute without invariant violations.

## Scenario 2 — Active step diagnostic tracking

Given: a state machine executing an operation that encounters an invariant failure.

1. The active step diagnostic tracker records the transition name and argument values.
   Observed: `get_active_step` returns the active transition context.

2. The diagnostic formatter generates a failure summary.
   Observed: the formatted output details the transition name, arguments, state snapshot, and contextual diagnostic reasons when return recognizers reject SUT outcomes.

## Scenario 3 — Unit test synthesis from counterexample trace

Given: a shrunken sequence of trace steps leading to an assertion violation.

1. The unit test synthesizer compiles the trace steps into standalone Python source code.
   Observed: the output contains a valid Python test function instantiating the implementation under test and reproducing the step sequence with literal arguments.

## Scenario 4 — Execution watchdog timeout protection

Given: a test suite containing an infinite loop or hanging operation.

1. The watchdog monitor arms a timer warning and a faulthandler timeout.
   Observed: the timer prints an active step warning before expiration, and faulthandler dumps the active traceback to standard error and terminates execution if the timeout limit is reached.

2. The watchdog monitor executes a quick test that completes before timeout.
   Observed: watchdog timers are cleanly disarmed upon completion without interrupting the process.

## Scenario 5 — Test discovery and coverage evaluation

Given: a directory containing `*_pretense.py` test files.

1. The test runner discovers target test files and runs them with coverage tracking enabled.
   Observed: discovered tests execute with property fuzzing suppressed during coverage evaluation to bound execution to deterministic test suites while reserving fuzzing for QA verification, statement coverage is measured for corresponding implementation modules (excluding abstract interface stubs), and any lines missing coverage below the threshold are reported along with auditor guidance reminders directing the agent to formulate blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files.

2. A target test file has import or syntax errors or contains no executable test targets.
   Observed: the test runner raises or reports target loading errors and exits with a non-zero status code rather than reporting success.

## Scenario 6 — CLI entry point execution

Given: command-line arguments specifying `--cov`, `--no-fuzz`, `--timeout 10.0`, and target test paths.

1. The CLI entry point parses the arguments and invokes the test runner.
   Observed: the runner executes the specified suite with the configured timeout, fuzzing disabled, and coverage verification active, exiting with code 0 on success.

2. A test suite fails, a target module fails to import, or zero test targets are found.
   Observed: the runner outputs diagnostic error messages containing all formatted failure and error details across all failed test methods rather than truncating to the first failure, includes auditor guidance reminders directing the agent to formulate blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files, and exits with a non-zero status code.
