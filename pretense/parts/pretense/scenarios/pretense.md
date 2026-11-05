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

## Scenario 4 — 1:1 State transition definition and AST pivot

Given: a state transition method decorated with `@transition(TargetClass.method)` matching the target method signature, with targets and collaborators accessible via `sut(TargetClass)`.

1. The caller evaluates the transition with satisfying inputs and target singleton.
   Observed: `requires` validates state preconditions, `require_arg` validates arguments against their domain, pre-state snapshots capture values before the pivot, the AST pivot executes the method on target, and single-argument `assert` statements verify postconditions and differentials.

2. The caller evaluates the transition when the `requires` condition is not met.
   Observed: the requirement check raises `PretenseSpecificationError` (or the contracted error when specified), failing verification; in fixed scenario tests with an optional error parameter, the requirement check throws the specified error upon contract violation.

3. The caller evaluates an exception transition using `with raises(ExpectedException): make_return_value(None)`.
   Observed: in verification mode, the context manager asserts that the target call raised `ExpectedException` and propagates the exception to callers and test runners; in Fake mode, it raises `ExpectedException` to emulate interface failure semantics.

4. The caller defines pre-state and post-state assertions.
   Observed: assertions are written using native Python single-argument `assert condition` syntax without custom string messages.

5. The caller defines an impossible branch marked with `unreachable(reason)`.
   Observed: the line is excluded from test coverage and raises an AssertionError if executed during fuzzing.

6. The caller constrains an argument using `Domain.type` with a subscripted generic type annotation (such as `Callable[[], Any]` or `Collection[str]`).
   Observed: `Domain.type` extracts the runtime origin to validate value conformity and generate valid samples without raising `TypeError` for subscripted generics.

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

## Scenario 7 — Implementation pseudo state machine and property pivots

Given: an implementation pseudo state machine subclassing an interface state machine with zero state dataclasses, overriding transitions without `require_arg`.

1. The caller runs property fuzzing against the implementation pseudo state machine.
   Observed: parameter domains and preconditions are inherited from the parent interface state machine transitions, base interface transitions execute model state updates, pre-state assertions execute before `call_target(target.method(*args))`, the target executes, and post-state assertions verify private internal invariants.

2. The caller executes a transition targeting a non-callable target property using `call_target(target.property)`.
   Observed: `call_target(target.property)` returns the property attribute value directly without attempting function invocation.

