# pretense interface component

## Intent

Software verification driven purely by example-based unit tests or AST statement coverage suffers from blind spots when validating neural implementations: subtle off-by-one errors, state desynchronizations, and omitted recovery branches easily bypass static test sequences. The pretense interface component establishes declarative, state-machine-driven testing abstractions, sentinels, observable collection models, transition specifications, dynamic fake doubles, and verification engine contracts for Cleanroom.

By structuring stateful contracts as executable state transition systems, the component guarantees that property fuzzing explores diverse operation interleavings and minimal counterexample sequences while enabling zero-maintenance interface doubles.

## Factored Contracts

### Typing

- A pretense sentinel distinguishes unprovided inputs and specific runtime states from standard program values.
- A not bound sentinel indicates that a parameter was omitted by a caller.
- An execution outcome encapsulates the result of evaluating an operation against an implementation under test.
- A value outcome wraps a successful return value.
- A raised outcome wraps an expected or intercepted exception instance.
- A specification error indicates that a state machine contract, transition invariant, or antecedent predicate was violated.
- A draw context provides a dynamically bound generator for sampling values during property-based test exploration.
- A pretense collection provides an observable state container that tracks mutations and verifies invariants.
- A pretense dictionary provides an observable key-value mapping with existence assertions and weighted key selection.
- A pretense set provides an observable unique item container with element sampling and existence assertions.
- A state transition defines a single atomic operation step within a state machine.
- A requires condition defines a precondition predicate that must hold before a state transition executes.
- An argument domain unifies generative sampling with analytical validation for an operation parameter, supporting scalar categoricals, discrete ranges, lexical patterns, structural types, dependent parameter domains derived from preceding arguments, and constructive perturbations derived from anchor values.
- An argument binder generates or recognizes operation arguments, supporting explicit domains, native collections, ranges, patterns, data types, dependent domain functions, keyword domain mappings, and property strategies treated directly as values, automatically drawing randomized instances when an active draw context is present and sampling examples otherwise.
- An ensures condition defines a postcondition verified against the concrete singleton under test during real test execution.
- An update condition defines model state mutations applied to reference state.
- A check helper evaluates conditions and captures diagnostics without exception overhead in requirements, and asserts postconditions in ensures.
- A transition context provides methods for specifying requires preconditions, argument binders, expected returns, contracted exceptions, ensures postconditions, and model updates for a single transition method, enforcing mutual exclusivity between returns and raises, and safely instantiating multi-argument exceptions for fakes.
- A transition decorator registers a transition method against a target singleton class operation.
- A state machine declares the complete behavioral contract of an interface or implementation through a collection of state transitions and system invariants, storing singletons under test directly in its state representation.
- A fake adapter acts as a dynamic test double conforming to an interface protocol, delegating method invocations directly to matching state transitions and verifying preconditions.
- A trace step records the operation name, arguments, and outcome of an executed transition within a state machine run.
- A runner configuration specifies test execution parameters including target paths, fuzzing iterations, statement coverage thresholds, execution timeout durations, and active step diagnostic reporting.
- A run result reports execution metrics, including passed test counts, failure counts, statement coverage percentages, and synthesized counterexamples.
- A system's pretense engine coordinates state machine compilation, test suite execution, and fake generation.

### Contracts

- A pretense sentinel evaluates equality and string representation distinct from standard values. [sentinel_evaluation]
- A draw context provides sample values using active draw functions and binds current draw instances within execution scopes. [manage_draw_context]
- A pretense collection provides state mutation tracking, size reporting, and invariant verification. [track_collection_state]
- A state transition defines requires preconditions, argument providers, execution logic, ensures postconditions, and update mutations. [define_state_transition]
- A transition context manages requires, argument, return, ensures, and update handlers for a transition method, enforcing mutual exclusivity between returns and raises, and safely instantiating multi-argument exceptions. [manage_transition_context]
- A state machine exposes declared transitions, system invariants, step traces, and compiles dynamic fake adapters. [declare_state_machine]
- A fake adapter delegates method invocations to matching state transitions, enforces requires preconditions, and omits ensures verification. [adapt_fake_protocol]
- A system's pretense engine compiles state machines into executable test suites. [compile_state_machine]
- A system's pretense engine executes test suites and evaluates statement coverage against configured thresholds. [execute_test_suite]
- A system's pretense engine synthesizes minimal unit tests from counterexample traces. [synthesize_counterexample_test]

### Woven Contracts

- The pretense engine coordinates state machine compilation, test suite execution, coverage evaluation, fake adapter generation, and unit test synthesis. [sentinel_evaluation, manage_draw_context, track_collection_state, define_state_transition, manage_transition_context, declare_state_machine, adapt_fake_protocol, compile_state_machine, execute_test_suite, synthesize_counterexample_test]

## Grounding

### Knowledge Provisions

- Pretense sentinels, collection types, state transitions, state machines, fake adapters, and pretense engine service. [pretense_service]

### Knowledge Requirements

- Property-based testing framework and test execution runtime.
  - Deferred: Provided by runtime implementation in pretense_impl.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T22:45:00Z
LAST_CHANGED: 2026-10-26T22:45:00Z
CHANGE: Initial pretense interface specification
SPEC_QA_AUDIT: 2026-10-26T22:45:00Z
-->
