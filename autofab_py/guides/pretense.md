# Guide: Pretense State Machine and Test Author

## Summary

The artifact is a Pretense state machine and test module (`pretense/<name>_pretense.py` or `pretense/<name>_impl_pretense.py`) modeling interface state transitions or verifying concrete implementations per `low/<name>.pyi`, submitted via `submit(target="<target_file>", change_summary="...")`. Metadata blocks under `# --- CLEANROOM METADATA ---` are managed automatically by Cleanroom tooling upon `submit`; direct edits are prohibited. Interface modules define model state (`<Iface>State`), state transitions (`<Iface>StateMachine`), synthesized fakes (`make_<iface>_fake = synthesize_fake(<Iface>StateMachine)`), fake tests (`Test<Iface>Fake`), and fake property fuzzing (`compile_hypothesis_test_case`). Implementation modules import upstream interface state machines and collaborator fakes, defining implementation pseudo-state machines overriding inner transitions (`inner_<method>`) to execute `target.method(...)` on `target: TargetClass = sut(TargetClass)`, real scenario tests (`Test<Impl>Real`), and real implementation property fuzzing. Authors proactively author scenario tests (`self.checked.violating(ExpectedError)`) for every contracted `*Error` in `low/<name>.pyi` in Round 1 alongside the state machine so statement coverage passes on initial audit.

Transitions model target methods 1:1 (`@transition(TargetClass.method)`), handling branching, domains, and contracted exceptions in a single transition body without splitting (`PN_STRICT_1_TO_1`). Interface transitions invoke an inner transition (`ret = self.inner_<method>(*args)`) to compute the fake return value, followed by model state mutations and assertions. Implementation pseudo-state machines inherit interface transitions without defining new state dataclasses or `require_arg` statements, overriding inner transitions (`inner_<method>`) to bind concrete SUT calls. Generative fuzzing operates on valid inputs gated by `require(...)` and `require_arg(...)`. In fixed scenario tests, contracted errors (`*Error`) are verified on the SUT exclusively via `self.checked.violating(ExpectedError).<method>(...)`; `self.assertRaises(...)` is strictly prohibited (`PN_NO_ASSERT_RAISES`). Direct calls on `self.real` in tests are prohibited (`PN_NO_DIRECT_REAL_ACCESS`); tests drive components exclusively through `self.checked`. Operational postcondition exceptions (`*Exception`) use `with raises(ExpectedException):` around the inner transition or target call. Components start in blank initial states with seeding transitions; state is manipulated exclusively through public operations and transitions.

> META: "Pretense 1 Next models interface state transitions 1:1 with natural branching, synthesizes verified in-memory fakes, executes fake property fuzzing, and verifies concrete implementations with concentric onion execution."

## Verification failure

Static verification diagnostics (`pretense_lint`, `pyright`) state syntax, typing, and DSL rule violations requiring targeted file edits. Diagnostic triage resolves compiler and linter diagnostics directly in code without conversational commentary. When verification passes with zero errors on modified code, conclude via `submit(target="<target_file>", change_summary="...")`. Invoking `fail` or `reject` after modifying code that passes verification is prohibited. If the target is unmodified and incoming feedback is incorrect, invoke `reject(target="<target_file>", reason="<explanation>")`. If valid feedback meets insurmountable complexity, revert incomplete edits and invoke `fail(target="<target_file>", reason="<explanation>")`.

## Lint checks

- [ ] Interface pretense modules define at least one `<Target>State` dataclass and one `StateMachine` subclass
- [ ] Interface pretense modules define a fake test suite (`Test<Target>Fake`) covering 100% of declared transitions and seeding transitions (`PRE_LINT_INTERFACE_TRANSITION_COVERAGE`)
- [ ] Interface state machines contain zero `call_target` statements (`PRE_LINT_NO_CALL_TARGET_IN_INTERFACE`)
- [ ] Implementation pretense modules define zero state dataclasses (`PN_IMPL_NO_STATE_CLASS`); implementation pseudo-state machines inherit from the interface state machine
- [ ] Implementation pseudo-state machine transitions contain zero `require_arg` statements (`PN_IMPL_NO_REQUIRE_ARG`); domain constraints and generator strategies are inherited automatically
- [ ] Implementation pretense modules do not import `require_arg`, `Domain`, or `transition` (`PN_IMPL_NO_REQUIRE_ARG_IMPORT`, `PN_IMPL_NO_TRANSITION_IMPORT`)
- [ ] Implementation pseudo-state machines must not declare `@transition` or override outer transitions (`PN_IMPL_NO_OUTER_TRANSITION`); they override inner transitions (`inner_<name>`) to bind the concrete SUT
- [ ] Implementation pretense modules define at least one `unittest.TestCase` (`Test<Impl>Real`) or compiled Hypothesis test case (`<Impl>FuzzTest`)
- [ ] Multi-interface implementation pseudo-state machines inherit from all implemented interface state machines (`PRE_LINT_MULTI_INTERFACE_INHERITANCE`)
- [ ] Direct mutation or mutating method calls on `.state` in tests is prohibited (`PRE_LINT_NO_STATE_POKING`); state changes occur via transitions
- [ ] Loops and state arguments in `make_sut()` are prohibited (`PRE_LINT_NO_PRE_SEEDING`); components start in blank default states
- [ ] Interface pretense modules import `StateMachine`, `transition`, `raises`, `require`, `require_arg`, `sut`, `sut_state`, `synthesize_fake`, and `Domain`
- [ ] Legacy symbols `ensure`, `ensure_ret`, `ensure_raises`, `TransitionContext`, and `Expr` are never imported (`PN_NO_LEGACY_IMPORT`)
- [ ] Top-level probe statements (try/except, raise, while, for, assert, \_PROBE) and executing test suites during authoring are prohibited (`PRE_LINT_NO_TOP_LEVEL_PROBE`)
- [ ] Modules import target classes and initialization functions directly from companion library implementations using package-qualified paths
- [ ] Modules pass Pyright type checking with zero errors and zero type suppression comments
- [ ] Test methods in `Test<Impl>Real` contain meaningful scenario executions; empty test methods and tautological assertions are prohibited
- [ ] Transitions never return or assign residual sentinel stubs (`NotBound`); assertions never assert equality against `NotBound`
- [ ] Strict 1:1 transitions (`PN_STRICT_1_TO_1`): each public method on the target interface is modeled by exactly one `@transition(TargetClass.method)` transition
- [ ] Transition parameters match the target method 1:1 (`self, *args`); parameters named `target`, `sut`, or `suts` are strictly prohibited (`PN003_NO_TARGET_PARAM`)
- [ ] Transition methods declare zero default parameter values (`PN008_NO_DEFAULT_ARGUMENTS`); every domain parameter must be passed explicitly
- [ ] Assertions use native single-argument `assert test` (`PRE_LINT_ASSERT_SINGLE_ARG`); failure messages (`assert test, msg`) and tuples (`assert (x, y)`) are prohibited
- [ ] Interface transitions mapped to a target method delegate to an inner transition via `ret = self.inner_<name>(...)`; implementation pseudo-state machine transition overrides invoke `target.method(...)`
- [ ] Preconditions via `require(...)` must only inspect `self.state` (`PN009`); referencing SUT objects, method arguments, or local variables inside `require(...)` is prohibited
- [ ] The first argument to `require_arg(...)` is a bare parameter name identifier matching a transition argument; expressions and lambdas are prohibited
- [ ] Transition methods contain zero `while` loops (`PN_NO_WHILE_IN_TRANSITION`); state transformations use bounded iterations or sequential transitions
- [ ] Transitions and domain definitions contain zero lambda expressions (`lambda ...`) (`PN002_NO_LAMBDA`)
- [ ] Transitions contain zero bare `try/except` statements; operational postcondition exceptions are verified around the pivot via `with raises(ExpectedException):`
- [ ] State machines operate purely on abstract model state (`self.state`) and never instantiate target service classes or invoke `get_singleton`
- [ ] State machines never define nested functions within transitions; tests never clear `sys.modules`; residual placeholders are prohibited
- [ ] Test modules contain zero calls to `assertRaises` or `assertRaisesRegex` (`PN_NO_ASSERT_RAISES`); contract violations (`*Error`) are verified exclusively via `self.checked.violating(ExpectedError).method(...)` (which self-asserts the exception and marks the adapter terminal)
- [ ] Test methods contain zero direct access to `self.real` (`PN_NO_DIRECT_REAL_ACCESS`); `self.real` is permitted only in `setUp`/`tearDown` for adapter wiring
- [ ] Pretense transition DSL `raises(...)` is prohibited inside TestCase test methods (`PRE_LINT_NO_RAISES_IN_TEST_CASE`); contract violations are verified via `self.checked.violating(...)`
- [ ] Skipping tests via `@unittest.skip*`, `@pytest.mark.skip*`, `pytest.skip()`, or `SkipTest` is strictly prohibited (`PRE_LINT_NO_SKIP`)
- [ ] Authoring handwritten mock or fake SUT implementations in pretense test files is prohibited; SUT is imported from target library modules

## Document layout and imports

- [ ] Future annotations (`from __future__ import annotations`) is the first code statement
- [ ] Imports are grouped into standard library, third-party (`hypothesis`, `pretense`), lifecycle support (`support.lib.lifecycle`), and target library imports
- [ ] Target classes and factory functions are imported from the companion library implementation using package-qualified paths
- [ ] Collaborator types and domain `NewType` wrappers are imported from interface specifications or constructed via helper functions
- [ ] Interface modules define model state, transitions, fakes, fake tests (`Test<Target>Fake`), and fake property fuzzing
- [ ] Implementation modules define implementation pseudo-state machines, scenario tests (`Test<Target>ImplReal`), and real property fuzzing

## State modeling and transitions

- [ ] Model state is declared as a dataclass ending with `State` (e.g. `<Target>State`), storing state in standard containers (`list`, `dict`, `set`) or observable collections
- [ ] State machine is declared as a subclass of `StateMachine[<Target>State]`
- [ ] Operational branches, parameter validation, and contracted exception handling are implemented via standard Python `if/else` statements within the single transition body
- [ ] Checked preconditions associated with contract violation errors (`*Error`) are gated in interface state machines via `require(...)` and `require_arg(...)`, preventing generative fuzz testing from violating caller contracts
- [ ] Existing entity preconditions (`*NotFoundError` / `*KeyError`): when an operation requires an entity to exist in model state, the transition requires non-empty state via `require(bool(self.state.<collection>))` and constrains the parameter via `require_arg(<param>, Domain.in_set(self.state.<collection>))` (optional `error=ExpectedError` serves as documentation only); `require(...)` cannot inspect method arguments (`PN009`); testing the `*NotFoundError` error path is authored in fixed scenario tests via `self.checked.violating(ExpectedError).<method>(...)`
- [ ] Contract violation testing: in fixed scenarios, contracted errors are verified on the SUT via `self.checked.violating(ExpectedError).<method>(...)`; preconditions are disabled during the transition so the library's error branch executes and achieves statement coverage; testing a contract violation marks the adapter terminal and must be strictly the final transition on that instance
- [ ] Preconditions via `require(...)` test model state invariants on `self.state` only; argument domain restrictions belong in `require_arg(arg, Domain...)`
- [ ] In interface state machines, `require_arg(arg, domain, preferred=[...])` defines caller precondition contracts: open parameters use open domains (`Domain.any()`, `Domain.type(...)`), closed sets (`Domain.sampled_from(...)`) are reserved for finite enums, and fuzz sizing uses `preferred=[...]`
- [ ] Domain factory types: primitives (`Domain.type(str)`), generics (`Domain.type(Sequence[int])`), state sets (`Domain.in_set(self.state.keys)`), composites (`Domain.optional(...)`, `Domain.list_of(...)`, `Domain.dict_of(...)`)
- [ ] Complex algorithms (graph cycle checks, topological sorting, simulation engines) are abstracted in state machine models: transitions model state changes and invariant assertions rather than re-implementing algorithmic execution with unbounded while loops
- [ ] Multi-step simulations re-initialize temporary execution states before each simulation run to prevent state pollution across repeated transition invocations
- [ ] Transitions express collaborator state preconditions or input domains via `sut_state(CollabState)` rather than inventing surrogate fields on model state
- [ ] Collaborator delegation in implementation transitions: when a delegated collaborator operation raises `*Error` on unseeded state during exploratory fuzzing, the transition override catches the error or gates caller dispatch via `sut_state(CollabState)`
- [ ] Implementation pseudo-state machines selectively override inner transitions (`def inner_<name>(self, *args):`), invoking `ret = target.method(*args)` (where `target: TargetClass = sut(TargetClass)`) or `ret = call_target(target.method(*args))`, returning `ret`
- [ ] Implementation pseudo-state machines must not duplicate `require(...)` precondition guards already present in the interface state machine; all preconditions and model state mutations are executed automatically by the inherited base interface transition
- [ ] Contracted operational postcondition exceptions (`*Exception`) requiring environmental seeding are verified around the pivot via `with raises(ExpectedException):`
- [ ] Prohibition on `raises()` for contract violations (`*Error`): `with raises(...)` is used strictly for operational postcondition exceptions (`*Exception`); contract violations (`*Error`) designate caller contract violations and must never use `with raises(...)` (`PRE_LINT_NO_RAISES_ERROR`); in suites where all exceptions end in `*Error`, there must be zero `with raises(...)` blocks across the module; contract violations are gated out of generative fuzzing via `require(...)` and `require_arg(...)` (optional `error=` serves as documentation only; fakes raise `PretenseSpecificationError` on breach), and verified in scenario tests via `self.checked.violating(ExpectedError).<method>(...)`
- [ ] Transition methods declare model state mutations directly on `self.state` using standard Python statements
- [ ] Postconditions and invariants are asserted using single-argument `assert test` verifying structural properties and observable state on `self.state`, `sut(TargetClass)`, or collaborator fakes via `sut(CollabClass)`
- [ ] Components start in blank initial states; pre-seeding in `setUp()` or `make_sut()` is prohibited (`PRE_LINT_NO_PRE_SEEDING`); state machines declare `@transition.seeding` methods to transition states during fuzzing
- [ ] State machines and tests inspect state exclusively via `@test_only` query methods or public methods, never accessing private `_*` members
- [ ] Probing Pretense runtime internals is prohibited; reading, grepping, or inspecting `pretense/parts/` source code is prohibited

## Fake synthesis and fake fuzzing

- [ ] Interface pretense modules expose `Fake<Target> = synthesize_fake(<Target>StateMachine)` and factory `make_<name>_fake(state: Optional[<Target>State] = None) -> TargetClass: return Fake<Target>(state=state or proto.make_initial_state())`
- [ ] Interface state machines define `make_initial_state(self) -> <Target>State`: open parameters unspecified in public interfaces (e.g. default capacity or buffer size) are assigned defaults for fake synthesis via overridable properties or `make_initial_state()`; inlining concrete implementation constants into interface state machines is prohibited
- [ ] Interface pretense modules define `Test<Target>Fake(unittest.TestCase)` testing the synthesized fake; every declared `@transition` and `@transition.seeding` method must be exercised (`PRE_LINT_INTERFACE_TRANSITION_COVERAGE`)
- [ ] On interface transition coverage failure: ensure required conditions can be reached by existing transitions, or add `@transition.seeding` methods
- [ ] Tests never mutate `.state` directly (`PRE_LINT_NO_STATE_POKING`); all state changes occur via public operations or seeding transitions
- [ ] Interface pretense modules compile Hypothesis stateful property tests on the synthesized fake: `Fake<Target>FuzzTest = compile_hypothesis_test_case(proto=proto, initial_state_factory=proto.make_initial_state, name="Fake<Target>FuzzTest")`
- [ ] Synthesized fakes implement their full public interface and `@test_only` accessors, evaluating assertions against the fake double during fake fuzzing

## Implementation verification and parity

- [ ] Implementation tests inherit from `unittest.TestCase` under class name `Test<Target>ImplReal`
- [ ] `setUp` initializes target instances, binds singletons into `self.sm = TargetImplPseudoStateMachine(singletons={...})`, and binds `self.checked = self.sm.as_checked(TargetClass, self.real)`; manage registry and phase scope in `setUp` and `tearDown`
- [ ] Open parameter specialization: implementation pseudo-state machines specialize uncontracted interface parameters (e.g. initial capacity or buffer limits) by overriding the corresponding property hook or `make_initial_state()`
- [ ] Implementation pseudo-state machine transition overrides assert outcomes across both SUT and collaborator fakes via `sut(CollabClass)` and `sut_state(CollabState)`
- [ ] Test methods in `Test<Target>ImplReal` drive scenarios via `self.checked.<method>(*args)` or `self.checked.violating(ExpectedError).<method>(*args)` to achieve 100% statement coverage under `--no-fuzz --cov`; `violating(ExpectedError)` self-asserts the exception and marks the adapter terminal; `self.assertRaises(...)` is prohibited (`PN_NO_ASSERT_RAISES`)
- [ ] Coverage blame resolution: coverage deficits blamed on pretense (`[from:pretense_coverage]`) are resolved strictly by adding scenario executions in `Test<Target>ImplReal` (using `self.checked.violating(ExpectedError)` for contracted errors), NEVER by adding `require()` guards to the adapter
- [ ] QA blame resolution: feedback prefixed with `[from:pretense_qa]` indicates functional assertion failures or transition mismatches, resolved by correcting test logic or adapter assertions
- [ ] Collaborator state isolation: when preceding assertions exhaust a collaborator (e.g. advancing a scheduler to `is_finished() == True`), subsequent methods on that instance exit immediately; distinct scenario flows use dedicated test methods (`def test_<flow>(self)`) with fresh `setUp()` scopes
- [ ] Operational postconditions and invariants are verified automatically on every call through `self.checked`; direct calls or attribute reads on `self.real` in test methods are strictly prohibited (`PN_NO_DIRECT_REAL_ACCESS`)
- [ ] Properties (`@property`) accessed via `self.checked.<prop>` dispatch transitions named `<prop>`; for Protocol classes, `@transition(name="<prop>")` avoids Pyright protocol property access errors
- [ ] Tests respect static type contracts and treat uncontracted failure conditions as undefined behavior: authoring tests for uncontracted non-concerns is prohibited
- [ ] Real implementation fuzz testing is compiled via `compile_hypothesis_test_case(proto=proto, collaborators=[CollabStateMachine, ...], sut_factory=make_sut, initial_state_factory=proto.make_initial_state, name="<Target>FuzzTest")`; singletons are seeded in `setUp()`
- [ ] Static verification (`bin/check_files`) only performs static syntax and type analysis (`pretense_lint`, `pyright`); executing test suites or running ad-hoc probes is prohibited; submit work via `bin/submit` for QA auditing
