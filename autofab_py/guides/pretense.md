# Guide: Pretense State Machine and Test Author

## Summary

The artifact is a Pretense state machine and test module (`pretense/<name>_pretense.py` or `pretense/<name>_impl_pretense.py`) modeling interface state transitions or verifying concrete implementations per `low/<name>.pyi`, submitted via `submit(...)`. Metadata blocks under `# --- CLEANROOM METADATA ---` are managed automatically by tooling; direct edits are prohibited. Interface modules define model state (`<Iface>State`), transitions (`<Iface>StateMachine`), fakes (`synthesize_fake`), fake tests (`Test<Iface>Fake`), and property fuzzing (`compile_hypothesis_test_case`). Implementation modules import upstream interface state machines and fakes, defining implementation pseudo-state machines overriding inner transitions (`inner_<method>`) to execute `target.method(...)` on `target: TargetClass = sut(TargetClass)`, real scenario tests (`Test<Impl>Real`), and real property fuzzing. Authors proactively author scenario tests (`self.checked.violating(ExpectedError)`) for every contracted `*Error` in `low/<name>.pyi` in Round 1 alongside the state machine so statement coverage passes on initial audit.

Transitions model target methods 1:1 (`@transition(TargetClass.method)`), handling branching, domains, and contracted exceptions in a single transition body without splitting (`PN_STRICT_1_TO_1`). Interface transitions invoke `ret = self.inner_<method>(*args)` to compute fake return values, followed by state mutations and assertions. Implementation pseudo-state machines inherit interface transitions without new state dataclasses or `require_arg`, overriding `inner_<method>` to bind concrete SUT calls. Generative fuzzing operates on valid inputs gated by `require(...)` and `require_arg(...)`. In fixed scenario tests, contracted errors (`*Error`) are verified on the SUT exclusively via `self.checked.violating(ExpectedError).<method>(...)`; `self.assertRaises(...)` is strictly prohibited (`PN_NO_ASSERT_RAISES`). Direct calls on `self.real` or `self.sm` in real tests are prohibited (`PN_NO_DIRECT_REAL_ACCESS`, `PN_NO_DIRECT_SM_ACCESS_IN_REAL_TEST`); tests drive components exclusively through `self.checked`. Operational postcondition exceptions (`*Exception`) use `with raises(ExpectedException):` around the inner transition or target call. Components start in blank initial states with seeding transitions; state is manipulated exclusively through public operations and transitions.

> META: "Pretense 1 Next models interface state transitions 1:1 with natural branching, synthesizes verified in-memory fakes, executes fake property fuzzing, and verifies concrete implementations with concentric onion execution."

## Verification failure

Static verification diagnostics (`pretense_lint`, `pyright`) state syntax, typing, and DSL rule violations requiring targeted file edits without conversational commentary. When verification passes with zero errors on modified code, conclude via `submit(target="<target_file>", change_summary="...")`. Invoking `fail` or `reject` after modifying code that passes verification is prohibited. If the target is unmodified and incoming feedback is incorrect, invoke `reject(target="<target_file>", reason="<explanation>")`. If valid feedback meets insurmountable complexity, revert incomplete edits and invoke `fail(target="<target_file>", reason="<explanation>")`.

## Lint checks

- [ ] Interface pretense modules define at least one `<Target>State` dataclass and one `StateMachine` subclass
- [ ] Interface pretense modules define a fake test suite (`Test<Target>Fake`) covering 100% of declared transitions and seeding transitions (`PRE_LINT_INTERFACE_TRANSITION_COVERAGE`)
- [ ] Interface state machines contain zero `call_target` statements (`PRE_LINT_NO_CALL_TARGET_IN_INTERFACE`)
- [ ] Implementation pretense modules define zero state dataclasses (`PN_IMPL_NO_STATE_CLASS`); implementation pseudo-state machines inherit from the interface state machine
- [ ] Implementation pseudo-state machine transitions contain zero `require_arg` statements (`PN_IMPL_NO_REQUIRE_ARG`); domain constraints and generator strategies are inherited automatically
- [ ] Implementation pretense modules do not import `require_arg`, `Domain`, or `transition` (`PN_IMPL_NO_REQUIRE_ARG_IMPORT`, `PN_IMPL_NO_TRANSITION_IMPORT`)
- [ ] Implementation pseudo-state machines must not declare `@transition` or override outer transitions (`PN_IMPL_NO_OUTER_TRANSITION`); they override inner transitions (`inner_<name>`) to bind the concrete SUT
- [ ] Implementation pretense modules define at least one `LifecycleTestCase` (or `unittest.TestCase`) subclass (`Test<Impl>Real`) or compiled Hypothesis test case (`<Impl>FuzzTest`)
- [ ] Multi-interface implementation pseudo-state machines inherit from all implemented interface state machines (`PRE_LINT_MULTI_INTERFACE_INHERITANCE`)
- [ ] Direct mutation or mutating method calls on `.state` in tests is prohibited (`PRE_LINT_NO_STATE_POKING`); state changes occur via transitions
- [ ] Loops and state arguments in `make_sut()` are prohibited (`PRE_LINT_NO_PRE_SEEDING`); components start in blank default states
- [ ] Interface pretense modules import `StateMachine`, `transition`, `raises`, `require`, `require_arg`, `sut`, `sut_state`, `synthesize_fake`, and `Domain`
- [ ] Legacy symbols `ensure`, `ensure_ret`, `ensure_raises`, `TransitionContext`, and `Expr` are never imported (`PN_NO_LEGACY_IMPORT`)
- [ ] Top-level probe statements (try/except, raise, while, for, assert, _PROBE) and executing test suites during authoring are prohibited (`PRE_LINT_NO_TOP_LEVEL_PROBE`)
- [ ] Modules import target classes and initialization functions directly from companion library implementations using package-qualified paths (either `from <unit>.lib.<module> import ...` or `from <package_scope>.parts.<unit>.lib.<module> import ...`); bare partial 'parts' imports and unrooted 'lib' imports are prohibited
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
- [ ] Test modules contain zero calls to `assertRaises` or `assertRaisesRegex` (`PN_NO_ASSERT_RAISES`); contract violations (`*Error`) are verified exclusively via `self.checked.violating(ExpectedError).method(...)`
- [ ] Test methods contain zero direct access to `self.real` (`PN_NO_DIRECT_REAL_ACCESS`); `self.real` is permitted only in `setUp`/`tearDown` for adapter wiring
- [ ] Test methods in `Test<Target>ImplReal` contain zero direct access to `self.sm` (`PN_NO_DIRECT_SM_ACCESS_IN_REAL_TEST`); all operations and property assertions drive exclusively through `self.checked`
- [ ] Implementation pretense modules define zero auxiliary classes (`PN_IMPL_ALLOWED_CLASSES_ONLY`); only the implementation pseudo-state machine and `Test<Target>ImplReal` test cases are permitted
- [ ] Contract violations contain zero 'with ...violating(...):' context blocks (`PN_NO_WITH_VIOLATING`); violations are invoked directly as terminal calls: `self.checked.violating(ExpectedError).<method>(*args)`
- [ ] Pretense transition DSL `raises(...)` is prohibited inside TestCase test methods (`PRE_LINT_NO_RAISES_IN_TEST_CASE`); contract violations are verified via `self.checked.violating(...)`
- [ ] Skipping tests via `@unittest.skip*`, `@pytest.mark.skip*`, `pytest.skip()`, or `SkipTest` is strictly prohibited (`PRE_LINT_NO_SKIP`)
- [ ] Authoring handwritten mock or fake SUT implementations in pretense test files is prohibited; SUT is imported from target library modules

## Document layout and imports

- [ ] Future annotations (`from __future__ import annotations`) is the first code statement
- [ ] Imports are grouped into standard library, third-party (`hypothesis`, `pretense`), lifecycle support (`support.lib.lifecycle`), and target library imports
- [ ] Target classes and factory functions are imported from the companion library implementation using package-qualified paths
- [ ] Collaborator types and domain `NewType` wrappers are imported from interface specifications or constructed via helper functions

## State modeling and transitions

- [ ] Model state is declared as a dataclass ending with `State` (e.g. `<Target>State`), storing state in standard containers (`list`, `dict`, `set`) or observable collections
- [ ] State machine is declared as a subclass of `StateMachine[<Target>State]`
- [ ] Operational branches, parameter validation, and contracted exception handling are implemented via standard Python `if/else` statements within the single transition body
- [ ] Checked preconditions associated with contract violation errors (`*Error`) are gated in interface state machines via `require(...)` and `require_arg(...)`, preventing generative fuzz testing from violating caller contracts
- [ ] Existing entity preconditions (`*NotFoundError` / `*KeyError`): require non-empty state via `require(bool(self.state.<collection>))` and parameter membership via `require_arg(<param>, Domain.in_set(self.state.<collection>))` (`PN009`); testing the error path is authored in fixed scenarios via `self.checked.violating(ExpectedError).<method>(...)`
- [ ] Contract violation testing: in fixed scenarios, contracted errors are verified on the SUT via `self.checked.violating(ExpectedError).<method>(...)`; preconditions are disabled during the transition so the library's error branch executes; testing a contract violation marks the adapter terminal and must be strictly the final transition on that instance
- [ ] Preconditions via `require(...)` test model state invariants on `self.state` only; argument domain restrictions belong in `require_arg(arg, Domain...)`
- [ ] In interface state machines, `require_arg(arg, domain, preferred=[...], fuzz_domain=Domain...)` defines caller contracts: open parameters use open domains (`Domain.any()`, `Domain.type(...)`), closed sets (`Domain.sampled_from(...)`) are for finite enums, and retry bounds use `fuzz_domain=Domain.integers(0, 5)`
- [ ] Domain factory types: primitives (`Domain.type(str)`), generics (`Domain.type(Sequence[int])`), state sets (`Domain.in_set(self.state.keys)`), composites (`Domain.optional(...)`, `Domain.list_of(...)`, `Domain.mapping_of(key_domain, val_domain)`); for invariant-constrained parameter types (such as `Optional[Collection[T]]`), use `Domain.type(...)` or `Domain.any()`
- [ ] Complex algorithms (graph cycles, topological sort) are abstracted in state machine models: transitions model state changes and invariants rather than re-implementing algorithms with while loops
- [ ] Multi-step simulations re-initialize temporary execution states before each simulation run to prevent state pollution
- [ ] Transitions express collaborator state preconditions or input domains via `sut_state(CollabState)` rather than surrogate fields on model state
- [ ] Collaborator delegation in implementation transitions: when a delegated operation raises `*Error` on unseeded state during fuzzing, the transition override catches the error or gates dispatch via `sut_state(CollabState)`
- [ ] Implementation pseudo-state machines selectively override inner transitions (`def inner_<name>(self, *args):`), invoking `ret = target.method(*args)` (where `target: TargetClass = sut(TargetClass)`) or `ret = call_target(target.method(*args))`, returning `ret`
- [ ] Implementation pseudo-state machines must not duplicate `require(...)` precondition guards present in the interface state machine
- [ ] Contracted operational postcondition exceptions (`*Exception`) requiring environmental seeding are verified around the pivot via `with raises(ExpectedException):`
- [ ] Prohibition on `raises()` for contract violations (`*Error`): `with raises(...)` is strictly for operational postconditions (`*Exception`); `*Error` must never use `with raises(...)` (`PRE_LINT_NO_RAISES_ERROR`); in suites where all exceptions end in `*Error`, there must be zero `with raises(...)` blocks; contract violations are gated out of fuzzing via `require(...)`/`require_arg(...)`, and verified in scenario tests via `self.checked.violating(ExpectedError).<method>(...)`
- [ ] Transition methods declare model state mutations directly on `self.state` using standard Python statements
- [ ] Postconditions and invariants are asserted using single-argument `assert test` verifying structural properties and observable state on `self.state`, `sut(TargetClass)`, or collaborator fakes via `sut(CollabClass)`
- [ ] State machines declare `@transition.seeding` methods to transition states during fuzzing from blank default initial states
- [ ] State machines and tests inspect state exclusively via `@test_only` query methods or public methods, never accessing private `_*` members
- [ ] Probing Pretense runtime internals is prohibited; reading, grepping, or inspecting `pretense/parts/` source code is prohibited

## Fake synthesis and fake fuzzing

- [ ] Interface pretense modules expose `Fake<Target> = synthesize_fake(<Target>StateMachine)` and factory `make_<name>_fake(state: Optional[<Target>State] = None) -> TargetClass: return Fake<Target>(state=state or proto.make_initial_state())`
- [ ] Interface state machines define `make_initial_state(self) -> <Target>State`: open parameters (e.g. initial capacity) are assigned defaults via overridable properties or `make_initial_state()`; inlining concrete constants is prohibited
- [ ] Interface pretense modules define `Test<Target>Fake(unittest.TestCase)` testing the synthesized fake; every declared `@transition` and `@transition.seeding` method must be exercised (`PRE_LINT_INTERFACE_TRANSITION_COVERAGE`)
- [ ] On interface transition coverage failure: ensure required conditions can be reached by existing transitions, or add `@transition.seeding` methods
- [ ] Interface pretense modules compile Hypothesis stateful property tests on fake: `Fake<Target>FuzzTest = compile_hypothesis_test_case(proto=proto, initial_state_factory=proto.make_initial_state, name="Fake<Target>FuzzTest")`
- [ ] Synthesized fakes implement their full public interface and `@test_only` accessors, evaluating assertions against the fake double during fake fuzzing

## Implementation verification and parity

- [ ] Implementation tests inherit from `LifecycleTestCase` (or `unittest.TestCase`) under class name `Test<Target>ImplReal`
- [ ] `setUp` initializes target instances, binds singletons into `self.sm = TargetImplPseudoStateMachine(singletons={...})`, and binds checked adapters via `self.checked = self.sm.as_checked(TargetClass, self.real)`; for multi-service components, pass all services in `singletons={ServiceA: self.service_a, ServiceB: self.service_b}` and create checked adapters for each service (`self.checked_a = self.sm.as_checked(...)`, `self.checked_b = ...`)
- [ ] Open parameter specialization: implementation pseudo-state machines specialize uncontracted interface parameters (e.g. initial capacity or buffer limits) by overriding the corresponding property hook or `make_initial_state()`
- [ ] Implementation pseudo-state machine transition overrides assert outcomes across both SUT and collaborator fakes via `sut(CollabClass)` and `sut_state(CollabState)`
- [ ] Test methods in `Test<Target>ImplReal` drive scenarios via `self.checked.<method>(*args)` or `self.checked.violating(ExpectedError).<method>(*args)` for 100% statement coverage under `--no-fuzz --cov`
- [ ] Terminal violation check: calling 'violating(...)' marks the checked adapter terminal; 'violating(...)' must be strictly the final statement of a test method and cannot be called multiple times in the same method (`PN_TERMINAL_VIOLATING`); distinct error scenarios use separate test methods
- [ ] Coverage blame resolution: deficits blamed on pretense (`[from:pretense_coverage]`) are resolved by adding scenario executions in `Test<Target>ImplReal`, NEVER by adding `require()` guards to the adapter
- [ ] QA blame resolution: feedback prefixed with `[from:pretense_qa]` indicates functional assertion failures or transition mismatches, resolved by correcting test logic or adapter assertions
- [ ] Collaborator state isolation: when preceding assertions exhaust a collaborator, subsequent methods on that instance exit immediately; distinct scenario flows use dedicated test methods with fresh `setUp()` scopes
- [ ] Properties (`@property`) accessed via `self.checked.<prop>` dispatch transitions named `<prop>`; for Protocol classes, `@transition(name="<prop>")` avoids Pyright protocol property access errors
- [ ] Tests respect static type contracts and treat uncontracted failure conditions as undefined behavior: authoring tests for uncontracted non-concerns is prohibited
- [ ] Real implementation fuzz testing is compiled via `compile_hypothesis_test_case(proto=proto, collaborators=[CollabStateMachine, ...], sut_factory=make_sut, initial_state_factory=proto.make_initial_state, name="<Target>FuzzTest")`; singletons are seeded in `setUp()`
- [ ] Static verification (`bin/check_files`) only performs static syntax and type analysis (`pretense_lint`, `pyright`); executing test suites or running ad-hoc probes is prohibited; submit work via `bin/submit` for QA auditing
