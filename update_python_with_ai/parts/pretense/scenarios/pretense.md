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

## Scenario 4 — State transition definition

Given: a state transition specifying requires, arguments, returns, ensures, and update.

1. The caller evaluates the transition with satisfying inputs and target singleton.
   Observed: the requires check succeeds, the operation executes against the target singleton, ensures validates postconditions via the check helper, and update applies reference state changes.

2. The caller evaluates the transition when the requires condition is not met.
   Observed: the check flag records failure, execution is prevented, and the transition is treated as not ready to fire.

3. The caller declares `raises` after declaring `returns` on the transition context.
   Observed: a `ValueError` is raised prohibiting ambiguous outcome declarations.

4. The caller configures argument generation with a property search strategy directly or a sequence containing search strategies as values.
   Observed: when evaluated under an active draw context, arguments are drawn dynamically from each strategy; when evaluated outside a draw context, argument values are sampled from strategy examples.

5. The caller configures transition arguments using explicit domains, native primitives, dependent closures, or constructive perturbations.
   Observed: arguments are sampled according to domain strategies during fuzzing, candidate calls during fake adapter dispatch are recognized and validated against domain predicates, and unspecialized required domains raise a descriptive runtime error.

## Scenario 5 — State machine declaration and fake adapter

Given: a state machine subclass defining state transitions, singletons, and invariants.

1. The caller instantiates the state machine and compiles a fake adapter.
   Observed: the fake adapter conforms to the target interface protocol, delegates method calls to matching transitions, and omits ensures verification.

2. The caller calls a method on the fake adapter when the state machine's requires condition is not satisfied.
   Observed: the fake adapter raises a NoMatchingTransitionError indicating unsatisfied precondition state.

3. The caller invokes a method on the fake adapter configured with `raises` for an exception class requiring multiple positional parameters.
   Observed: the fake adapter instantiates and raises the contracted exception instance without constructor errors.

## Scenario 6 — Runner configuration and result reporting

Given: a runner configuration with fuzz iterations 50, coverage threshold 100.0, and timeout 30.0s.

1. The caller inspects configuration fields.
   Observed: parameters reflect configured values.

2. The caller creates a run result reporting 10 passed tests, 0 failures, and 100.0% statement coverage.
   Observed: `is_passing` returns true.
