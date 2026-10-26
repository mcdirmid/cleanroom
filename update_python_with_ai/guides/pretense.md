# Guide: Pretense State Machine and Test Author

## Summary

The artifact is a Pretense test and fake synthesis module (`pretense/<name>_pretense.py`) that models and tests `lib/<name>.py` per `low/<name>.pyi`, submitted via `submit(target="<target_file>", change_summary="...")`. In multi-node sessions, multiple targets are processed together by package-relative alias path. When starting from a template or missing artifact, pretense scaffolding (`uv run python -m update_python_with_ai.support.lib.pretense_lint --scaffold <target> --pyi low/<name>.pyi --impl lib/<name>.py`) generates a canonical 5-section skeleton with model state, transitions, fake synthesis, unit tests, and property fuzzing. Cleanroom metadata blocks at the bottom of the file (under `# --- CLEANROOM METADATA ---` and `# --- END CLEANROOM METADATA ---`) are managed automatically by Cleanroom tooling upon `submit(change_summary=...)`; direct edits to metadata blocks are prohibited and rejected by editing tools. All operations and state assertions derive directly from contractual invariants (`INVARIANTS:`) and operational postconditions (`POSTCONDITIONS:`) in `low/<name>.pyi` across the transitive inheritance hierarchy. Only singletons and data types can be tested; poly types without singletons have nothing to test and are instantiated only to supply collaborator instances needed by singletons.

The pretense module consolidates state modeling, fake generation, unit tests, parity verification, and stateful fuzzing into a single cohesive module containing five canonical sections. Section 1 defines a dataclass representing the model state (`<Target>State`) alongside pure transition specifications decorated with `@proto.transition(TargetClass.method)` mapping arguments to expected return outcomes (`Value`, `Raised`) and state mutations. Section 2 defines the state machine protocol (`proto = StateMachineProto[<Target>State]()`) and fake factory functions returning synthesized in-memory fakes. Section 3 defines deterministic unit tests (`Test<Target>Unit`) inheriting from `unittest.TestCase` asserting that synthesized fakes execute valid state transitions and raise contracted exceptions on error conditions. Section 4 defines concrete implementation tests (`Test<Target>ImplReal`) executing real library classes within isolated test lifecycle registries, asserting full behavioral parity against the state model and achieving 100% statement coverage of the companion library implementation under `--no-fuzz --cov`. Section 5 defines Hypothesis stateful property tests (`Test<Target>Fuzz` or `compile_hypothesis_test_case`) verifying equivalence invariants and absence of uncaught crashes across arbitrary interaction sequences. Time-dependent operations use fast sub-second durations (`0.01` to `0.05`s) or mock time progression rather than wall-clock delays. Conversational commentary without tool execution is prohibited; execution proceeds continuously via tool calls until the round concludes with `submit` or `fail`.

> META: "Pretense modules model interface state transitions, synthesize in-memory fakes, verify concrete implementations with full coverage, and execute bounded property fuzzing."

## Guide structure

- [ ] File contains five sections in order: Model State & Transitions, State Machine Proto & Fakes, Fake Unit Tests, Real Implementation Tests, and Hypothesis Fuzzing
- [ ] Imports include standard typing tools, `unittest`, `hypothesis`, `pretense.proto`, `pretense.sentinels`, `support.lib.lifecycle`, and the target library classes
- [ ] Cleanroom metadata comments at the bottom of the file are preserved without manual edits
- [ ] No conversational text or commentary is emitted without accompanying tool execution

## Lint checks

- [ ] Module defines at least one dataclass whose name ends with `State` representing model state
- [ ] Module defines at least one `unittest.TestCase` subclass or compiled Hypothesis test case
- [ ] Module imports `StateMachineProto` and sentinels (`NotBound`, `NotBoundType`, `Outcome`, `Raised`, `Value`) from `pretense.proto` and `pretense.sentinels`
- [ ] Module imports target classes and initialization functions directly from the companion library implementation
- [ ] Module contains valid Python syntax and passes Pyright type checking with zero errors
- [ ] Scaffolding command `uv run python -m update_python_with_ai.support.lib.pretense_lint --scaffold` generates a valid skeleton for uninitialized modules

## Document layout and imports

- [ ] Module begins with a module-level docstring describing the target component and specification mapping
- [ ] Future annotations (`from __future__ import annotations`) is the first code statement
- [ ] Imports are grouped into standard library (`dataclasses`, `typing`, `unittest`), third-party (`hypothesis`, `pretense`), lifecycle support (`support.lib.lifecycle`), and target library imports
- [ ] Target classes and factory functions are imported from the companion library implementation using full package-qualified paths
- [ ] Collaborator types and domain `NewType` wrappers are imported from interface specifications or constructed via helper functions
- [ ] Sections are clearly marked with separator comments matching the five canonical sections

## State modeling and transitions

- [ ] Model state is declared as a dataclass ending with `State` (e.g. `<Target>State`), storing state collections and tracking flags
- [ ] Collections within model state use standard containers (`list`, `dict`, `set`) or Pretense observable collections
- [ ] Proto instance is initialized as `proto = StateMachineProto[<Target>State]()`
- [ ] Each public method across all target interfaces has an associated `@proto.transition(TargetClass.method)` transition definition
- [ ] Transition `@<method>.arguments` handler accepts `(state: <Target>State, this: Any, <arg>: Any | NotBoundType = NotBound, ...)` and returns a tuple of resolved arguments or `NotBound` fallback values
- [ ] Transition `@<method>.returns` handler accepts `(state: <Target>State, this: Any, <arg>: Any, ..., outcome: object = NotBound)` and returns `Value(expected_return)` for successful calls or `Raised(ExpectedException)` for contracted exceptions
- [ ] In the `@<method>.returns` handler, when `outcome` is not `NotBound`, returning `outcome if isinstance(outcome, Outcome) else Value(outcome)` preserves dispatched outcomes (Outcome is an unparameterized base class; subscripting it with type parameters in `isinstance` checks is prohibited)
- [ ] Transition `@<method>.returns` and `@<method>.arguments` handlers for entity creation or addition (such as `add_node`) do not perform eager validation of referenced entities unless explicitly specified; validation belongs in explicit validation operations (`validate`) when specified
- [ ] Transition `@<method>.returns` handlers for non-deterministic fields (such as elapsed wall-clock durations or random tokens) match outcome types or structural shapes rather than asserting fixed constant values
- [ ] Transition `@<method>.provide` handler accepts `(state: <Target>State, this: Any, <arg>: Any, ..., result: Any) -> None` and applies state mutations to the model state reflecting postconditions
- [ ] In composite state machines with multiple interconnected services, entity lifecycle creation or addition transitions (such as adding nodes or tasks) initialize corresponding lifecycle tracking states across all constituent sub-states in `@<method>.provide` (e.g. initializing new nodes into scheduler state as ready or pending)
- [ ] Transition `@<method>.provide` handlers for composite operations mutate model state collections and entity lifecycle states reflecting operation completion
- [ ] Caller assumptions (`ASSUMPTIONS:`) in specifications are accepted axiomatically; modeling assumption violations is prohibited

## Fake synthesis and unit tests

- [ ] Synthesized fake is created via `proto.make_state_machine(state).as_fake(TargetClass)` or an explicit fake factory function `make_<name>_fake`
- [ ] For modules with multiple service classes sharing model state, fake factory `make_<name>_fakes` synthesizes a tuple of fakes backed by one shared `StateMachineProto` instance
- [ ] Fake unit tests inherit from `unittest.TestCase` under class name `Test<Target>Unit`
- [ ] `setUp` initializes a fresh model state instance and state machine fake for each test method
- [ ] In `Test<Target>Unit` for multi-service modules, `setUp` unpacks synthesized fakes into distinct instance attributes (e.g. `self.dag`, `self.scheduler`, `self.runner`)
- [ ] Test methods verify each transition through the fake, asserting returned values match expected state outcomes
- [ ] Test methods verify that invalid inputs or error preconditions trigger contracted exceptions wrapped in `Raised`
- [ ] Test assertions verify that mutator operations update the backing model state correctly

## Implementation verification and parity

- [ ] Real implementation tests inherit from `unittest.TestCase` under class name `Test<Target>ImplReal`
- [ ] For lifecycle-managed components declaring a tier, `setUp` initializes an isolated `LifecycleRegistry`, calls `__initialize__(self.registry)`, enters `self.phase_scope = enter_phase(system, registry=self.registry)`, and resolves `self.real = get_singleton(TargetClass)`
- [ ] In `Test<Target>ImplReal` for multi-service modules, `setUp` resolves each singleton service from the active lifecycle registry into corresponding instance attributes
- [ ] In `Test<Target>ImplReal`, `tearDown` exits the phase scope via `self.phase_scope.__exit__(None, None, None)`
- [ ] Real target instances for non-lifecycle classes are obtained by direct instantiation
- [ ] Test methods exercise all operational branches, optional parameters, error raising branches, and edge cases on the real implementation to achieve 100% statement coverage under `--no-fuzz --cov`
- [ ] Assertions on complex reports or structured objects where item order is unspecified or implementation-dependent (such as node execution sequences, collections of completed targets, or parallel wave results) verify set membership or set equality (e.g. `set(report.succeeded) == expected_set`) rather than enforcing strict list or tuple sequence equality unless sequence ordering is explicitly contracted
- [ ] Parity tests execute matching operations against both the real implementation and the fake, asserting identical return values and exception types
- [ ] Timeouts and delays use fast sub-second intervals (`0.01` to `0.05`s) or mocked time functions; multi-second sleeps are prohibited

## Hypothesis fuzz testing

- [ ] Fuzz testing is compiled via `compile_hypothesis_test_case(proto=proto, sut_factory=make_sut, initial_state_factory=<Target>State, name="<Target>FuzzTest")` or defined under `Test<Target>Fuzz`
- [ ] `sut_factory` supplies a cleanly initialized real target instance (with lifecycle phase scope entered if applicable)
- [ ] For modules exposing multiple singleton services, `sut_factory` supplies an aggregate SUT class declaring class attribute `tier = system`, declaring typed instance attributes (`_services: tuple[Any, ...]`), initializing member services inside an active phase scope into `self.__dict__["_services"]`, and delegating method lookup across constituent services in `__getattr__`
- [ ] In multi-singleton aggregate SUT classes, `__getattr__` ignores dunder lookups (`if name.startswith('__'): raise AttributeError(name)`) and inspects `self.__dict__.get("_services", ())` to avoid infinite recursion or attribute errors during caller tier introspection
- [ ] `initial_state_factory` returns a fresh model state dataclass instance
- [ ] Property fuzzing verifies invariant preservation and output equivalence between the real implementation and model transitions across pseudo-random action sequences
- [ ] Fuzz tests complete within bounded test budgets (default `--max-examples 50`) without indefinite loops or hangs; while loops in target methods implement progress checks or break conditions when no executable work items remain to prevent infinite busy-loops
