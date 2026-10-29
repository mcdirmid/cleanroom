# pretense_impl implementation component

implements: pretense

## Purpose

The pretense_impl implementation component realizes the state machine compiler, diagnostic tracer, fake adapter proxy, execution watchdog, and test runner for the pretense engine.

Executing stateful test suites against neural implementations requires robust test case synthesis, minimal counterexample shrinking, and failsafe execution bounds. Without automatic shrinking and active step tracing, developers and models struggle to debug complex multi-step failures. Without execution watchdogs, unbounded loops or blocking operations hang test runners indefinitely. This component bridges abstract state models to property-based test engines, synthesizes reproducible unit test files from minimized counterexamples, and guarantees execution termination through signal-based watchdogs.

**Out of scope:** Static type checking, code generation templates, and language server protocols; these are handled by other components.

## Types and Behavior

The *pretense engine realization* implements the pretense engine service on the system tier.

A *state machine compiler* translates declarative state machine specifications into executable property-based test suites. The compiler inspects each declared state transition on a state machine, binding requires guards to test generation preconditions, and evaluating ensures postconditions against the concrete system under test after invocation and outcome recognition, while applying model update mutations to backing state. When a postcondition or invariant fails during property search, the compiler shrinks the failure sequence to a minimal sequence of trace steps and formats an *active step diagnostic* detailing the active transition, input arguments, and current state snapshot. When the system under test produces an outcome rejected by the transition's return recognizer, the active step diagnostic details whether the transition was configured expecting an exception or a return value.

A *unit test synthesizer* generates a standalone, reproducible Python test function from a shrunken counterexample sequence. The synthesized test instantiates the system under test, applies each step in sequence with literal arguments, and verifies that the failure reproduces deterministically.

A *watchdog monitor* oversees test execution using a dual-layer timeout mechanism. A software timer emits a warning before expiration, dumping active step diagnostics to standard error. Concurrently, a system-level fault handler registers an abrupt termination alarm that interrupts blocking system calls or infinite loops, exiting with a non-zero status code to prevent test runner hangs.

A *test runner coordinator* scans target directories for state machine test files, rejecting loading errors or missing test targets with diagnostics and a non-zero exit status code rather than reporting success. The coordinator executes test cases within configured execution phases, verifies statement coverage thresholds against the corresponding implementation modules under test (excluding abstract interface stubs), suppresses property fuzzing during coverage evaluation to bound execution to deterministic test suites while reserving fuzzing for QA verification, formats and reports all failure and error details across all executed test methods in failing test targets to prevent defect masking, formats auditor guidance reminders upon test failures and coverage deficits directing the agent to formulate blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files, and reports aggregated test outcomes through a run result payload, exiting with a non-zero exit status code whenever any test fails, any test target fails to load, zero test targets are executed, or coverage thresholds are not met.
