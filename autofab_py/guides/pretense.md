# Guide: Pretense State Machine and Test Author

## Summary

The artifact is a Pretense state machine and test module (`pretense/<name>_pretense.py` or `pretense/<name>_impl_pretense.py`) modeling interface state transitions or verifying concrete implementations per `low/<name>.pyi`, submitted via `submit(target="<target_file>", change_summary="...")`. Metadata blocks are managed automatically by Cleanroom tooling upon `submit`; direct edits are prohibited. Interface components define model state (`<Iface>State`), state machine transitions (`<Iface>StateMachine`), synthesized fakes (`make_<iface>_fake = synthesize_fake(<Iface>StateMachine)`), fixed fake tests (`Test<Iface>Fake(unittest.TestCase)`) exercising 100% of transitions and seeding transitions, and fake property fuzzing (`Fake<Iface>FuzzTest = compile_hypothesis_test_case(...)`). Implementation components import upstream interface state machines and collaborator fakes, define implementation pseudo-state machines (inheriting interface state machines without defining new state dataclasses and containing zero `require_arg` statements) with transition overrides invoking `call_target(target.method(...))`, real scenario tests (`Test<Impl>Real`), and real implementation Hypothesis fuzzing (`compile_hypothesis_test_case`). When addressing feedback, sibling transitions and tests across the module must be audited for the same defect pattern before submitting. Conversational commentary without tool execution is prohibited; execution proceeds continuously via tool calls until the round concludes with `submit` or `fail`.

Transitions model public target methods 1:1 using `@transition(TargetClass.method)` accepting `(self, *args)` matching domain parameters 1:1; parameters named `target`, `sut`, or `suts` are strictly prohibited (`PN003_NO_TARGET_PARAM`). Transition splitting for the same method is strictly prohibited (`PN_STRICT_1_TO_1`); branching outcomes, parameter validation, and contracted exception handling live naturally inside the single transition body. Interface transitions define an AST pivot via `ret = make_return_value(...)`; interface state machines contain zero `call_target` calls (`PRE_LINT_NO_CALL_TARGET_IN_INTERFACE`). Implementation pseudo-state machine transitions define an AST pivot via `ret = call_target(target.method(*args))` (where `target: TargetClass = sut(TargetClass)`) or `ret = call_target(ReturnType)`; zero-argument `call_target()` and zero-argument `sut()` are strictly prohibited. Multi-interface implementation pseudo-state machines inherit from all implemented interface state machines (`PRE_LINT_MULTI_INTERFACE_INHERITANCE`). Implementation pseudo-state machine overrides observe/assert postconditions against the real SUT and must NEVER mutate `self.state` (`PN_IMPL_NO_STATE_MUTATION`). Checked preconditions (`*Error`) are gated via `require(...)` (model state) and `require_arg(...)` (argument domains); preconditions cannot be tested, and asserting `*Error` exceptions is strictly prohibited. Operational postcondition exceptions (`*Exception`) are verified around the pivot via `with raises(ExpectedException):`. Native single-argument `assert test` is used exclusively (`PRE_LINT_ASSERT_SINGLE_ARG`). Components start in blank initial states; static pre-seeding or passing state in `make_sut()` is prohibited (`PRE_LINT_NO_PRE_SEEDING`). Direct mutation or method calls on `.state` in test methods is strictly prohibited (`PRE_LINT_NO_STATE_POKING`); state is manipulated exclusively via transitions and public operations. Test skipping (`PRE_LINT_NO_SKIP`) and handwritten mock SUT implementations are strictly prohibited.

> META: "Pretense 1 Next models interface state transitions 1:1 with natural branching, synthesizes verified in-memory fakes, executes fake property fuzzing, and verifies concrete implementations with concentric onion execution."

## Lint checks

- [ ] Interface pretense modules define at least one `<Target>State` dataclass and one `StateMachine` subclass
- [ ] Interface pretense modules define a fixed fake test suite (`Test<Target>Fake`) covering 100% of declared transitions and seeding transitions (`PRE_LINT_INTERFACE_TRANSITION_COVERAGE`)
- [ ] Interface state machines contain zero `call_target` statements (`PRE_LINT_NO_CALL_TARGET_IN_INTERFACE`)
- [ ] Implementation pretense modules define zero state dataclasses (`PN_IMPL_NO_STATE_CLASS`); implementation pseudo-state machines inherit from the interface state machine without defining new state classes
- [ ] Implementation pseudo-state machine transitions contain zero `require_arg` statements (`PN_IMPL_NO_REQUIRE_ARG`); domain constraints and generator strategies are inherited automatically
- [ ] Implementation pretense modules do not import `require_arg` or `Domain` (`PN_IMPL_NO_REQUIRE_ARG_IMPORT`)
- [ ] Implementation pretense modules define at least one `unittest.TestCase` (`Test<Impl>Real`) or compiled Hypothesis test case (`<Impl>FuzzTest`)
- [ ] Multi-interface implementation pseudo-state machines inherit from all implemented interface state machines (`PRE_LINT_MULTI_INTERFACE_INHERITANCE`)
- [ ] Direct mutation or mutating method calls on `.state` in test methods is strictly prohibited (`PRE_LINT_NO_STATE_POKING`); state is manipulated exclusively via transitions and public operations
- [ ] Loops, passing state arguments to fake factories, and mutating method calls in `make_sut()` are strictly prohibited (`PRE_LINT_NO_PRE_SEEDING`); components and collaborator fakes start in blank default initial states
- [ ] Interface pretense modules import `StateMachine`, `transition`, `make_return_value`, `raises`, `require`, `require_arg`, `sut`, `sut_state`, `synthesize_fake`, and `Domain`
- [ ] Legacy symbols `ensure`, `ensure_ret`, `ensure_raises`, `TransitionContext`, and `Expr` are never imported (`PN_NO_LEGACY_IMPORT`)
- [ ] Top-level probe statements (try/except, raise, while, for, assert, or _PROBE symbols) are prohibited; executing test suites or probing runtime behavior during authoring is prohibited (`PRE_LINT_NO_TOP_LEVEL_PROBE`)
- [ ] Modules import target classes and initialization functions directly from the companion library implementation using package-qualified paths
- [ ] Modules pass Pyright type checking with zero errors and zero type suppression comments
- [ ] Test methods in `Test<Impl>Real` contain meaningful scenario executions; empty test methods and tautological assertions are prohibited
- [ ] Transitions never return or assign residual sentinel stubs (`NotBound`); assertions never assert equality against `NotBound`
- [ ] Strict 1:1 transitions (`PN_STRICT_1_TO_1`): each public method on the target interface is modeled by exactly one `@transition(TargetClass.method)` transition
- [ ] Transition parameters match the target method 1:1 (`self, *args`); parameters named `target`, `sut`, or `suts` are strictly prohibited (`PN003_NO_TARGET_PARAM`)
- [ ] Transition methods declare zero default parameter values (`PN008_NO_DEFAULT_ARGUMENTS`); every domain parameter must be passed explicitly
- [ ] All assertions across transitions and tests use native single-argument `assert test` (`PRE_LINT_ASSERT_SINGLE_ARG`); failure messages (`assert test, msg`) and tuples (`assert (x, y)`) are prohibited
- [ ] Every interface transition mapped to a target method defines an AST pivot via `ret = make_return_value(...)`; every implementation pseudo-state machine transition defines an AST pivot via `ret = call_target(...)`; zero-argument `call_target()` is strictly prohibited
- [ ] Preconditions via `require(...)` must only inspect `self.state` (`PN009`); referencing SUT objects or input arguments inside `require(...)` is prohibited
- [ ] State machines operate purely on abstract model state (`self.state`) and never instantiate target service classes or invoke `get_singleton`
- [ ] State machines never define nested algorithmic functions or while loops within transitions; tests never clear `sys.modules`; residual placeholders (`_unimplemented_transition`, `Domain.required`, `self.fail`) are prohibited

## Document layout and imports

- [ ] Future annotations (`from __future__ import annotations`) is the first code statement
- [ ] Imports are grouped into standard library (`dataclasses`, `typing`, `unittest`), third-party (`hypothesis`, `pretense`), lifecycle support (`support.lib.lifecycle`), and target library imports
- [ ] Target classes and factory functions are imported from the companion library implementation using full package-qualified paths
- [ ] Collaborator types and domain `NewType` wrappers are imported from interface specifications or constructed via helper functions
- [ ] Interface modules contain Model State & 1:1 Transitions, State Machine Proto & Fakes, Fixed Scenarios on Fake (`Test<Target>Fake`), and Fake Hypothesis Fuzzing
- [ ] Implementation modules contain Implementation Pseudo State Machine, Real Implementation Tests, and Real Hypothesis Fuzzing

## State modeling and transitions

- [ ] Model state is declared as a dataclass ending with `State` (e.g. `<Target>State`), storing state in standard containers (`list`, `dict`, `set`) or observable collections
- [ ] State machine is declared as a subclass of `StateMachine[<Target>State]`
- [ ] Operational branches, parameter validation, and contracted exception handling are implemented via standard Python `if/else` statements within the single transition body
- [ ] Checked preconditions associated with contract violation errors (`*Error`) are gated in interface state machines via `require(...)` (model state) and `require_arg(...)` (argument domains), preventing test generators from violating caller contracts
- [ ] Preconditions cannot be tested: companion scenario tests (`Test<Impl>Real`, `Test<Target>Fake`) and state machine transitions must never violate preconditions or assert `*Error` exceptions
- [ ] In interface state machines, `require_arg(arg, domain, preferred=[...])` defines caller precondition contracts: open parameters use open domains (`Domain.any()`, `Domain.type(...)`), closed sets (`Domain.sampled_from(...)`) are reserved for finite enums, and fuzz sizing uses `preferred=[...]`
- [ ] Domain factory types: primitives (`Domain.type(str)`), generics (`Domain.type(Sequence[int])`), state collections (`Domain.in_set(self.state.keys)`), composites (`Domain.optional(...)`, `Domain.list_of(...)`, `Domain.dict_of(...)`)
- [ ] Transitions express collaborator state preconditions or input domains via `sut_state(CollabState)` rather than inventing surrogate fields on model state
- [ ] Collaborator delegation in implementation transitions: when a delegated collaborator operation raises *Error on unseeded state during exploratory fuzzing, the transition override catches the error or gates caller dispatch via sut_state(CollabState)
- [ ] Implementation pseudo-state machine transitions contain zero `require_arg(...)` statements and zero `self.state` mutations (`PN_IMPL_NO_STATE_MUTATION`)
- [ ] Implementation pseudo-state machines must not duplicate `require(...)` precondition guards already present in the interface state machine; all preconditions and model state mutations are executed automatically by the inherited base interface transition
- [ ] When checking boolean status or configuration mappings (e.g. `failing_tasks: dict[str, bool]`), evaluate `self.state.failing_tasks.get(key, False)` rather than `key in self.state.failing_tasks` to avoid treating False entries as active failure states
- [ ] Implementation pseudo-state machines selectively override transitions requiring SUT observation, invoking `ret = call_target(target.method(*args))` (where `target: TargetClass = sut(TargetClass)`) or `ret = call_target(ReturnType)`, returning `ret`
- [ ] Contracted operational postcondition exceptions (`*Exception`) requiring environmental seeding are verified around the pivot via `with raises(ExpectedException):`
- [ ] Transition methods declare model state mutations directly on `self.state` using standard Python statements
- [ ] Postconditions and invariants are asserted using single-argument `assert test` verifying structural properties and observable state on `self.state`, `sut(TargetClass)`, or collaborator fakes via `sut(CollabClass)`
- [ ] Components and collaborator fakes start in blank initial states; static pre-seeding in `setUp()` or `make_sut()` is prohibited (`PRE_LINT_NO_PRE_SEEDING`); state machines declare `@transition.seeding` methods to transition blank states dynamically during fuzzing and simulate operational failures
- [ ] State machines and tests inspect internal state exclusively via `@test_only` query methods contracted in `low/<name>.pyi` or public methods, never accessing private `_*` members
- [ ] Probing Pretense runtime internals is prohibited; reading, grepping, or inspecting `pretense/parts/` source code is prohibited

## Fake synthesis and fake fuzzing

- [ ] Interface pretense modules expose synthesized fake classes `Fake<Target> = synthesize_fake(<Target>StateMachine)` and factory function `make_<name>_fake(state: Optional[<Target>State] = None) -> TargetClass: return Fake<Target>(state=state or <Target>State())`
- [ ] Interface pretense modules define a fixed test suite `Test<Target>Fake(unittest.TestCase)` testing the synthesized fake double; every declared `@transition` and `@transition.seeding` method must be exercised to verify reachability and prevent dead preconditions (`PRE_LINT_INTERFACE_TRANSITION_COVERAGE`)
- [ ] On interface transition coverage failure: ensure required conditions can be properly reached by existing transitions, or add `@transition.seeding` methods if coverage is difficult
- [ ] Fixed fake tests and real scenario tests never mutate or call mutating methods on `.state` directly (`PRE_LINT_NO_STATE_POKING`); all state changes occur via public operations or declared seeding transitions
- [ ] Interface pretense modules compile Hypothesis stateful property tests directly on the synthesized fake: `Fake<Target>FuzzTest = compile_hypothesis_test_case(proto=proto, initial_state_factory=<Target>State, name="Fake<Target>FuzzTest")`
- [ ] Synthesized fakes implement their full public interface and `@test_only` accessors, evaluating assertions against the fake double during fake fuzzing

## Implementation verification and parity

- [ ] Real implementation tests inherit from `unittest.TestCase` under class name `Test<Target>ImplReal`
- [ ] `setUp` initializes target instances, binds singletons into `self.sm = TargetImplPseudoStateMachine(singletons={...})`, and binds `self.checked = self.sm.as_checked(TargetClass, self.real)`. For lifecycle suites, manage registry and phase scope in `setUp` and `tearDown`
- [ ] Multi-interface implementation pseudo-state machines inherit from all implemented interface state machines (e.g. `class MultiImplPseudoStateMachine(ReaderStateMachine, WriterStateMachine): ...`) (`PRE_LINT_MULTI_INTERFACE_INHERITANCE`)
- [ ] Implementation pseudo-state machine transition overrides assert outcomes across both SUT and collaborator fakes via `sut(CollabClass)` and `sut_state(CollabState)`
- [ ] Test methods in `Test<Target>ImplReal` drive operational scenarios via `self.checked.<method>(*args)` to achieve 100% statement coverage under `--no-fuzz --cov`
- [ ] Operational postconditions and invariants are verified automatically by transition `assert` checks on every call through `self.checked`; direct calls bypassing `self.checked` are prohibited
- [ ] Properties (`@property`) accessed via `self.checked.<prop>` dispatch transitions named `<prop>`; for Protocol classes, `@transition(name="<prop>")` avoids Pyright protocol property access errors
- [ ] Tests respect static type contracts and treat uncontracted failure conditions as undefined behavior: authoring tests for uncontracted non-concerns is prohibited
- [ ] Real implementation fuzz testing is compiled via `compile_hypothesis_test_case(proto=proto, collaborators=[Collab1StateMachine, ...], sut_factory=make_sut, initial_state_factory=<Target>State, name="<Target>FuzzTest")`
- [ ] Collaborator state coordination: tests seed collaborator singletons in setUp() or prior to consuming calls; fuzz suites declare collaborators=[CollabStateMachine, ...] in compile_hypothesis_test_case when tracking multi-component state
- [ ] Skipping tests via `@unittest.skip*`, `@pytest.mark.skip*`, `pytest.skip()`, or `SkipTest` is strictly prohibited (`PRE_LINT_NO_SKIP`)
- [ ] Authoring handwritten mock or fake SUT implementations inside companion pretense test files is strictly prohibited; SUT must be imported directly from the target library module
- [ ] In the pretense authoring role, static verification (`bin/check_files`) only performs static syntax and type analysis (`pretense_lint` and `pyright`). Executing test suites or running ad-hoc probes is prohibited; submit work via `bin/submit` so a downstream QA auditor can execute the test suite.
