# Concrete scenarios for `pretense` (interface)

## Scenario 1 — Sentinel behavior and outcome descriptors

Given: the pretense sentinels and outcome descriptors.

1. The caller checks `NotBound`.
   Observed: `NotBound` is a unique sentinel whose boolean value evaluates to false, and its string representation is `NotBound`.

2. The caller constructs a value outcome wrapping an integer result `42`.
   Observed: the outcome represents a successful value and unwraps to `42`.

3. The caller constructs a raised outcome wrapping a `ValueError("invalid state")`.
   Observed: the outcome represents an exception outcome, records the exception type and message, and re-raises when evaluated.

## Scenario 2 — Observable collections with assertions

Given: an instance of `PretenseDict` and `PretenseSet`.

1. The caller adds entries to `PretenseDict` and verifies key presence.
   Observed: keys are tracked in insertion order, and retrieving missing keys raises an assertion error indicating an invalid state machine antecedent.

2. The caller adds elements to `PretenseSet` and verifies uniqueness.
   Observed: set elements maintain distinctness and support membership assertions.

## Scenario 3 — Draw context management and value sampling

Given: an active property-based draw function.

1. The caller binds the draw function within a `with_draw` execution scope.
   Observed: `get_current_draw` returns the active draw instance within the scope and resets upon exit.

2. The caller invokes `choose_weighted` with candidate values and weight pairs.
   Observed: the chosen element is selected according to the specified distribution.

## Scenario 4 — 1:1 State transition definition and inner transition

Given: a state transition method decorated with `@transition(TargetClass.method)` matching the target method signature, with targets and collaborators accessible via `sut(TargetClass)`.

1. The caller evaluates the transition with satisfying inputs and target singleton.
   Observed: `requires` validates state preconditions, `require_arg` validates arguments against their domain, pre-state snapshots capture values before calling the inner transition, the inner transition computes the return value, and single-argument `assert` statements verify postconditions and differentials.

2. The caller evaluates the transition when the `requires` condition is not met.
   Observed: the requirement check raises `PretenseSpecificationError` (or the contracted error when specified positionally or via keyword `error`), failing verification; in fixed scenario tests with an optional error parameter, the requirement check throws the specified error upon contract violation.

3. The caller evaluates an exception transition using `with raises(ExpectedException): self.inner_method(...)`.
   Observed: in verification mode, the context manager asserts that the target call raised `ExpectedException` and propagates the exception to callers and test runners; in Fake mode, it synthesizes and raises `ExpectedException` (including multi-argument or structured exception classes) to emulate interface failure semantics.

4. The caller defines pre-state and post-state assertions.
   Observed: assertions are written using native Python single-argument `assert condition` syntax without custom string messages.

5. The caller defines an impossible branch or block marked with `with unreachable:` or `unreachable(reason)`.
   Observed: the line or block is excluded from test coverage and raises an AssertionError if executed during fuzzing.

6. The caller constrains an argument using `Domain.type` with a subscripted generic type annotation (such as `Callable[[], Any]` or `Collection[str]`).
   Observed: `Domain.type` extracts the runtime origin to validate value conformity and generate valid samples without raising `TypeError` for subscripted generics.

7. The caller defines an argument requirement with a fuzz domain override `require_arg(arg, Domain.integers(min_value=0), fuzz_domain=Domain.integers(min_value=0, max_value=5))`.
   Observed: during fuzz generation arguments are sampled strictly from the fuzz domain to bound generation sizes and prevent runaway iterations, while values outside the fuzz domain but within the canonical domain validate successfully during fixed scenario testing.

## Scenario 5 — State machine declaration and fake adapter

Given: a state machine subclass defining 1:1 state transitions and model state.

1. The caller instantiates the state machine and compiles a fake adapter via `synthesize_fake`.
   Observed: the fake adapter conforms to the target interface protocol, delegates method calls directly to 1:1 transitions, updates model state, and validates single-argument `assert` checks against the fake's observable properties.

2. The caller calls a method on the fake adapter when the state machine's `requires` condition is not satisfied.
   Observed: the fake adapter raises `PretenseSpecificationError` (or the contracted error) indicating a contract violation, immediately failing verification.

3. The caller compiles a Hypothesis property fuzz test for the fake via `compile_hypothesis_test_case(StateMachine, FakeTarget)`.
   Observed: the test case executes property fuzzing directly against the synthesized fake double, verifying that all state contracts hold across arbitrary operation sequences.

## Scenario 6 — Runner configuration and result reporting

Given: a runner configuration with fuzz iterations 50, coverage threshold 100.0, and timeout 30.0s.

1. The caller inspects configuration fields.
   Observed: parameters reflect configured values.

2. The caller creates a run result reporting 10 passed tests, 0 failures, and 100.0% statement coverage.
   Observed: `is_passing` returns true.

## Scenario 7 — Implementation pseudo state machine and inner transition override

Given: an implementation pseudo state machine subclassing an interface state machine with zero state dataclasses, overriding inner transitions without `require_arg`.

1. The caller runs property fuzzing against the implementation pseudo state machine.
   Observed: parameter domains and preconditions are inherited from the parent interface state machine transitions, base interface transitions execute model state updates, the overridden inner transition executes target pre-assertions, calls the target, executes target post-assertions, and returns the real return value to the outer transition.

2. The caller executes a transition targeting a target property.
   Observed: the inner transition accesses the target property attribute directly and returns it.

## Scenario 8 — Checked adapter contract violation testing

Given: a state machine bound to a concrete target instance via a checked adapter.

1. The caller executes a contract-violating call using `checked.violating(ExpectedError).method(...)` or `with checked.violating(ExpectedError): checked.method(...)`.
   Observed: `require` and `require_arg` preconditions are disabled for the transition, the real target implementation is invoked, the target raises `ExpectedError`, the adapter catches and verifies the exception, and the call succeeds.

2. The caller executes an operation on the checked adapter after a contract violation occurred.
   Observed: the checked adapter is terminal and raises `PretenseSpecificationError` for subsequent operational transitions, while lifecycle teardown methods remain accessible as no-ops.

