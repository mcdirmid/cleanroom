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
- A state transition defines a single atomic operation step within a state machine, registered 1:1 against a target class method or seeding transition using a transition decorator.
- A requirement assertion (requires) gates transition eligibility over state preconditions, where state preconditions are extracted statically to gate transition eligibility before execution, runtime precondition failures raise a specification error failing the test, and fixed scenario testing mode accepts an optional error parameter that throws the specified error upon contract violation.
- An exception context (raises) asserts that an operation under test raises a contracted exception during verification mode and propagates the exception to callers and test runners, while synthesizing an instance of the contracted exception (including multi-argument or structured exception classes) in Fake mode.
- An argument domain unifies generative sampling with analytical validation for an operation parameter or return outcome, parameterized generically over value types (`Domain[T]`) across scalar domains and collection combinators (`list_of`, `set_of`, `mapping_of`, `optional`), supporting categoricals, discrete ranges, set membership, set exclusion, unconstrained values, domain specializations, and empty collection defaults.
- An argument requirement (require_arg) binds an operation parameter of type `T` strictly to a matching argument domain of type `Domain[T]`, generating valid values by construction during fuzz testing mode, failing immediately with a specification error upon runtime violation, supporting an optional error parameter in fixed scenario testing mode (passed positionally or via keyword argument `error`), and supporting an optional fuzz domain override (`fuzz_domain=Domain...`) used exclusively for fuzz generation to bound generative sampling sizes and prevent runaway test iterations while validating against the canonical domain.
- An inner transition executes the core operation and yields its return value to the outer transition: the interface state machine defines an inner transition method computing and returning fake values in Fake mode; the implementation pseudo state machine overrides the inner transition to evaluate target pre-assertions, call the real target, evaluate target post-assertions, and return the real return value (ignoring any fake return value returned from calling super).
- A postcondition assertion verifies operational contracts, state differentials, and system invariants using native single-argument assert statements evaluated uniformly across real targets and synthesized fakes.
- A defensive dead-end (unreachable) marks impossible branches or blocks and is exempt from test coverage.
- A test-only query (@test_only) declares an observability query accessor on an interface specification for black-box state verification.
- A transition decorator registers a transition method 1:1 against a target singleton class operation.
- A state machine declares the complete behavioral contract of an interface through state transitions and system invariants, providing checked adapters (`sm.bind(target)`) and synthesized fake adapters.
- An implementation pseudo state machine inherits from an interface state machine, defining zero state dataclasses of its own, omitting argument requirements (require_arg), and overriding inner transition methods to execute target calls and evaluate target-specific pre- and post-assertions while inheriting parameter domains, preconditions, and model state updates directly through standard method polymorphism without onion wrappers.
- A checked adapter acts as a verification proxy conforming to an interface protocol, executing transitions around target invocations, providing contract violation testing (`adapter.violating(exc_type, match="")` and context manager `with adapter.violating(...)`) that disables preconditions, verifies and captures the contracted exception from the real target, and marks the instance terminal so subsequent operations raise specification errors.
- A fake adapter acts as a dynamic test double conforming to an interface protocol, backed by the state machine and verified by compiled Hypothesis fake property fuzz tests.
- A trace step records the operation name, arguments, and outcome of an executed transition within a state machine run.
- A runner configuration specifies test execution parameters including target paths, fuzzing iterations, statement coverage thresholds, execution timeout durations, and active step diagnostic reporting.
- A run result reports execution metrics, including passed test counts, failure counts, statement coverage percentages, and synthesized counterexamples.
- A system's pretense engine coordinates state machine compilation, test suite execution, and fake generation.

### Contracts

- A pretense sentinel evaluates equality and string representation distinct from standard values. [sentinel_evaluation]
- A draw context provides sample values using active draw functions and binds current draw instances within execution scopes. [manage_draw_context]
- A pretense collection provides state mutation tracking, size reporting, and invariant verification. [track_collection_state]
- A state transition defines gating preconditions, argument requirements, an inner transition invocation, model state updates, and single-argument postcondition assertions. [define_state_transition]
- An argument requirement binds an operation parameter strictly to a matching generic argument domain with analytical validation, resolving runtime type origins across subscripted generic types. [constrain_argument_domain]
- A state machine exposes declared 1:1 transitions, system invariants, step traces, and compiles dynamic fake adapters and checked verification adapters. [declare_state_machine]
- A checked adapter executes transitions around target invocations and supports contract violation testing with disabled preconditions, contracted exception verification, and terminal instance closure. [adapt_checked_protocol]
- A fake adapter delegates method invocations to 1:1 state transitions, evaluates single-argument assertions against fake properties, and is verified by compiled property fuzz tests. [adapt_fake_protocol]
- A system's pretense engine compiles state machines into executable test suites. [compile_state_machine]
- A system's pretense engine executes test suites and evaluates statement coverage against configured thresholds. [execute_test_suite]
- A system's pretense engine synthesizes minimal unit tests from counterexample traces. [synthesize_counterexample_test]

### Woven Contracts

- The pretense engine coordinates state machine compilation, test suite execution, coverage evaluation, fake adapter generation, checked adapter verification, and unit test synthesis. [sentinel_evaluation, manage_draw_context, track_collection_state, define_state_transition, constrain_argument_domain, declare_state_machine, adapt_checked_protocol, adapt_fake_protocol, compile_state_machine, execute_test_suite, synthesize_counterexample_test]

## Grounding

### Knowledge Provisions

- Pretense sentinels, collection types, state transitions, state machines, fake adapters, and pretense engine service. [pretense_service]

### Knowledge Requirements

- Property-based testing framework and test execution runtime.
  - Deferred: Provided by runtime implementation in pretense_impl.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-31T00:50:00Z
LAST_CHANGED: 2026-11-01T21:15:00Z
CHANGE: Strict generic typing for require_arg and Domain combinators
SPEC_QA_AUDIT: 2026-10-31T00:50:00Z
-->
