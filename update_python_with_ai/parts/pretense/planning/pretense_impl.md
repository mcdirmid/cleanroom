# pretense_impl implementation component

## Intent

Executing property-based state machine tests against neural-generated implementations requires robust test case compilation, minimal counterexample shrinking, failsafe execution bounds, and zero-maintenance test doubles. Without automatic shrinking and active step tracing, developers struggle to diagnose complex multi-step state divergence. Without execution watchdogs, runaway loops or blocking calls hang test runners indefinitely. The pretense_impl implementation component coordinates state machine compilation, active step diagnostic tracing, watchdog monitoring, coverage verification, and CLI test execution as a unified system service.

By standardizing on a dynamic Hypothesis compiler, dual-layer timeouts combining software warning timers with native faulthandler alarms, and automated unit test synthesis from shrunken traces, the component guarantees deterministic, reproducible verification of stateful contracts.

## Factored Contracts

### Typing

- A system's pretense engine coordinates state machine compilation, test suite execution, watchdog timeouts, coverage threshold checking, and fake generation.
- A state machine compiler translates declarative state machine models into executable property-based test suites.
- An active step diagnostic formats the active transition, inputs, and state snapshot for shrunken failures or timeout warnings.
- A unit test synthesizer formats shrunken counterexample sequences into standalone deterministic Python test functions.
- A watchdog monitor coordinates execution timeout enforcement using Python timers and signal-based faulthandler alarms.
- A test runner coordinator discovers test files, orchestrates pytest/pretense execution, verifies coverage thresholds, and aggregates run results.

### Contracts

- The state machine compiler translates declared state transitions into RuleBasedStateMachine rules with requires preconditions, ensures postconditions, and update assertions. [compile_state_machine_rules]
- The state machine compiler tracks active transition steps and state snapshots during execution. [track_active_steps]
- The state machine compiler formats active step diagnostics detailing failed transitions, parameter values, and contextual diagnostic reasons when return recognizers reject SUT outcomes. [format_step_diagnostics]
- The unit test synthesizer compiles minimal counterexample traces into standalone Python test functions. [synthesize_unit_test_code]
- The watchdog monitor arms a warning timer and a faulthandler timeout interrupt before test execution. [arm_execution_watchdog]
- The watchdog monitor disarms watchdog timers upon test execution completion. [disarm_execution_watchdog]
- The test runner coordinator discovers pretense test files matching naming patterns across target paths, rejecting loading errors or missing test targets. [discover_pretense_test_files]
- The test runner coordinator executes discovered test cases using configured fuzzing and coverage parameters, suppressing property fuzzing during coverage evaluation to bound execution to deterministic test suites while reserving fuzzing for QA verification, formatting and reporting all failure and error details across all executed test methods when test failures occur to prevent defect masking, and formatting auditor guidance reminders upon test failures directing the agent to formulate blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files. [run_test_cases]
- The test runner coordinator evaluates statement coverage of target implementation modules corresponding to executed test suites against configured thresholds (excluding abstract interface stubs), formatting auditor guidance reminders upon coverage deficits directing the agent to formulate blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files, and aggregates execution metrics into a run result. [evaluate_statement_coverage]
- The test runner coordinator parses command-line arguments to configure targets, fuzzing, coverage, watchdogs, and synthesis, exiting with a non-zero exit code if target loading fails, tests fail, coverage is unmet, or zero targets are discovered. [parse_runner_cli_arguments]
- The pretense engine provides access to the state machine compiler, test runner coordinator, and fake synthesis. [provide_pretense_engine]

### Woven Contracts

- State machine testing coordinates compilation, execution, active step tracking, watchdog monitoring, coverage verification, counterexample synthesis, and CLI orchestration. [compile_state_machine_rules, track_active_steps, format_step_diagnostics, synthesize_unit_test_code, arm_execution_watchdog, disarm_execution_watchdog, discover_pretense_test_files, run_test_cases, evaluate_statement_coverage, parse_runner_cli_arguments, provide_pretense_engine]

## Grounding

### Knowledge Provisions

- State machine compilation, diagnostic tracing, execution watchdogs, coverage verification, and runner orchestration service. [pretense_service]

### Inherited Deferred Requirements

- Property-based testing framework and test execution runtime.
  - Grounded: [pretense_service]

### Knowledge Requirements

- Target state machine models, execution parameters, and test paths.
  - Grounded: [caller input, pretense_service]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T22:45:00Z
LAST_CHANGED: 2026-10-29T00:30:00Z
CHANGE: Format auditor guidance reminders permitting line numbers in blamed file while forbidding exposing details of other files
SPEC_QA_AUDIT: 2026-10-26T22:45:00Z
-->
