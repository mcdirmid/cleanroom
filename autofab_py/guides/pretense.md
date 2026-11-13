# Guide: Pretense State Machine and Test Author

## Summary

The artifact is a Pretense state machine module (`pretense/<name>_pretense.py` or `pretense/<name>_impl_pretense.py`) modeling interface transitions or verifying implementations per `low/<name>.pyi`, submitted via `submit(...)`. Tool-managed metadata must not be edited manually. Interface modules define `<Iface>State`, `<Iface>StateMachine`, `Fake<Iface> = synthesize_fake(...)`, `Fake<Iface>FuzzTest = compile_hypothesis_test_case(...)`, and optional `Test<Iface>Fake` fixed tests limited to transitions or branches not covered by fuzzing. Implementation modules import interface state machines and fakes, defining an implementation pseudo-state machine overriding `inner_<method>` to call `target.method(...)` on `target: TargetClass = sut(TargetClass)`, plus `<Impl>FuzzTest`. Fixed scenario tests (`Test<Impl>Real`) are not authored upfront; they are added only when instructed by coverage feedback (`[from:pretense_coverage]`).

Transitions model target methods 1:1 (`@transition(TargetClass.method)`), handling branching, domains, and exceptions in one transition body. Interface transitions call `ret = self.inner_<method>(*args)` for fake return values, followed by state mutations and `assert` checks. Implementation pseudo-state machines inherit interface transitions without new state dataclasses or `require_arg`, overriding `inner_<method>` to bind the concrete SUT. Fuzzing operates on valid inputs gated by `require(...)` and `require_arg(...)`. Contracted errors (`*Error`) are verified in `Test<Impl>Real` only when requested by coverage feedback via `self.checked.violating(ExpectedError).<method>(...)` (never `self.assertRaises(*Error)`, and never accessing `self.real` or `self.sm` directly in test methods). Operational exceptions (`*Exception`) use `require_env(healthy_cond, ExpectedException, *args)`, bound in impl pseudo-SM via `self.bind(attr_name, lambda: ...)`, and asserted via `with self.assertRaises(ExpectedException):`. Components start in blank initial states with `@transition.seeding` transitions.

> META: "Pretense 1 Next models interface state transitions 1:1 with natural branching, synthesizes verified in-memory fakes, executes fake property fuzzing, and verifies concrete implementations with concentric onion execution."

## Verification failure

Interface pretense targets are verified in `bin/check_files` via static checks (`pretense_lint`, `pyright`) and runtime fake verification (`uv run pretense`), exercising fixed fake tests (`Test<Target>Fake`) and Hypothesis fake fuzzing (`Fake<Target>FuzzTest`). Implementation pretense targets (`*_impl_pretense.py`) are verified statically in `bin/check_files` and audited against the concrete SUT by downstream `pretense_qa`. When verification passes with zero errors on modified code, conclude via `submit(target="<target_file>", change_summary="...")`. Invoking `fail` or `reject` after modifying code that passes verification is prohibited. If the target is unmodified and incoming feedback is incorrect, invoke `reject(target="<target_file>", reason="<explanation>")`. If valid feedback meets insurmountable complexity, revert incomplete edits and invoke `fail(target="<target_file>", reason="<explanation>")`.

## Lint checks

- [ ] Interface modules define a `<Target>State` dataclass, a `StateMachine` subclass, and `Fake<Target>FuzzTest = compile_hypothesis_test_case(...)` (or `Test<Target>Fake` covering 100% of `@transition` and `@transition.seeding` methods if `compile_hypothesis_test_case` is absent, `PRE_LINT_INTERFACE_TRANSITION_COVERAGE`)
- [ ] Interface state machines contain zero `call_target` statements, zero `sut(...)` or `raise` in `inner_<name>`, and zero SUT calls outside `assert` (`PRE_LINT_NO_CALL_TARGET_IN_INTERFACE`)
- [ ] Implementation modules define zero state dataclasses (`PN_IMPL_NO_STATE_CLASS`) and inherit from the interface state machine(s); multi-interface impls inherit all implemented interface SMs (`PRE_LINT_MULTI_INTERFACE_INHERITANCE`)
- [ ] Implementation pseudo-SMs contain zero `require_arg` (`PN_IMPL_NO_REQUIRE_ARG`), zero `@transition` or outer transition overrides (`PN_IMPL_NO_OUTER_TRANSITION`), and do not import `require_arg`, `Domain`, or `transition` (`PN_IMPL_NO_REQUIRE_ARG_IMPORT`, `PN_IMPL_NO_TRANSITION_IMPORT`)
- [ ] Implementation modules define at least one `LifecycleTestCase` (or `unittest.TestCase`) subclass (`Test<Impl>Real`) or compiled Hypothesis test case (`<Impl>FuzzTest`)
- [ ] Direct mutation or mutating calls on `.state` in tests are prohibited (`PRE_LINT_NO_STATE_POKING`)
- [ ] Loops and state arguments in `make_sut()` are prohibited (`PRE_LINT_NO_PRE_SEEDING`)
- [ ] Interface modules import `Env`, `StateMachine`, `transition`, `raises`, `require`, `require_arg`, `require_env`, `sut`, `sut_state`, `synthesize_fake`, and `Domain`
- [ ] `require`/`require_arg` and `.violating(...)` stick to `*Error` (`PRE_LINT_REQUIRE_MUST_BE_ERROR`, `PRE_LINT_VIOLATING_MUST_BE_ERROR`); `*Exception` uses `require_env(...)` (`PRE_LINT_REQUIRE_ENV_MUST_BE_EXCEPTION`) referencing an `Env[T]` field (`PRE_LINT_REQUIRE_ENV_NEEDS_ENV_STATE`)
- [ ] State machines contain zero explicit `raise` statements (`PRE_LINT_NO_RAISE`) and zero bare `try/except` statements
- [ ] Legacy symbols (`ensure`, `ensure_ret`, `ensure_raises`, `TransitionContext`, `Expr`) are never imported (`PN_NO_LEGACY_IMPORT`)
- [ ] Top-level probes (`try/except`, `raise`, `while`, `for`, `assert`, `_PROBE`) and test execution during authoring are prohibited (`PRE_LINT_NO_TOP_LEVEL_PROBE`)
- [ ] Target imports use package-qualified paths (`from <package_scope>.parts.<unit>.lib.<module> import ...`); Pyright passes with zero errors and zero type suppressions
- [ ] Any test methods in `Test<Impl>Real` contain meaningful scenario executions (no empty bodies or tautological assertions)
- [ ] Transitions and assertions never return, assign, or compare against `NotBound`
- [ ] Strict 1:1 transitions (`PN_STRICT_1_TO_1`): one `@transition(TargetClass.method)` per public method, matching parameters 1:1 with zero defaults (`PN008_NO_DEFAULT_ARGUMENTS`) and no `target`/`sut`/`suts` parameter (`PN003_NO_TARGET_PARAM`)
- [ ] Assertions use single-argument `assert test` (`PRE_LINT_ASSERT_SINGLE_ARG`); failure messages (`assert test, msg`) and tuples (`assert (x, y)`) are prohibited
- [ ] `require(...)` inspects `self.state` only (`PN009`); `require_arg(...)` first argument is a bare parameter identifier
- [ ] Transitions contain zero `while` loops (`PN_NO_WHILE_IN_TRANSITION`), zero `lambda` expressions (`PN002_NO_LAMBDA`), and zero nested functions; tests never clear `sys.modules`
- [ ] `assertRaises`/`assertRaisesRegex` is prohibited for `*Error` (`PN_NO_ASSERT_RAISES`; use `self.checked.violating(ExpectedError).method(...)`); `with self.assertRaises(ExpectedException):` is used for `*Exception`
- [ ] Test methods in `Test<Target>ImplReal` contain zero direct access to `self.real` (`PN_NO_DIRECT_REAL_ACCESS`) or `self.sm` (`PN_NO_DIRECT_SM_ACCESS_IN_REAL_TEST`)
- [ ] Implementation modules define zero auxiliary classes (`PN_IMPL_ALLOWED_CLASSES_ONLY`); only the impl pseudo-SM and `Test<Target>ImplReal` are permitted
- [ ] Contract violations prohibit `with ...violating(...):` (`PN_NO_WITH_VIOLATING`) and `raises(...)` in `TestCase` methods (`PRE_LINT_NO_RAISES_IN_TEST_CASE`); use terminal `self.checked.violating(ExpectedError).<method>(*args)`
- [ ] Skipping tests (`@unittest.skip*`, `@pytest.mark.skip*`, `pytest.skip()`, `SkipTest`) and handwritten mock/fake SUTs in pretense tests are prohibited (`PRE_LINT_NO_SKIP`)

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
- [ ] Existing entity preconditions (`*NotFoundError` / `*KeyError`): require non-empty state via `require(bool(self.state.<col>))` and membership via `require_arg(<param>, Domain.in_set(self.state.<col>))` (`PN009`)
- [ ] Contract violation testing: in fixed scenarios, contracted errors are verified on the SUT via `self.checked.violating(ExpectedError).<method>(...)`, which bypasses `require(...)` and `require_arg(...)` precondition gates for that single call, asserts that `ExpectedError` is raised (failing if no error or a different exception is raised), skips postcondition and state-mutation assertions, and marks that adapter terminal for the test method
- [ ] `require(...)` gates fuzzing and raises on normal calls (only bypassed by `.violating(E)` on `self.checked` in `Test*ImplReal`); it tests `self.state` only, while argument domains belong in `require_arg(...)`
- [ ] Dynamic argument-to-state gating: dynamic membership preconditions use `require_arg(param, Domain.in_set(self.state.items))` or non-membership `require_arg(param, Domain.not_in(self.state.items), error=DuplicateItemError)`; `require(...)` cannot reference arguments (`PN009`)
- [ ] In interface state machines, `require_arg(arg, domain, preferred=[...], fuzz_domain=Domain...)` defines caller contracts: open parameters use typed domains (`Domain.type(...)`), closed sets (`Domain.sampled_from(...)`) for enums; `Domain.any()` is banned (`PRE_LINT_NO_DOMAIN_ANY`); `preferred=[...]` seeds candidates, and `fuzz_domain` overrides fuzz generation only (never runtime validation)
- [ ] Domain factory types: primitives (`Domain.type(...)`), bounded strings/ints (`Domain.text(min_size=1)`, `Domain.integers(...)`), state sets (`Domain.in_set(...)`), composites (`Domain.optional(...)`, `Domain.list_of(...)`, `Domain.collection(...)`, `Domain.mapping(...)`)
- [ ] Complex algorithms (graph cycles, topological sort) are abstracted in state machine models: transitions model state changes and invariants rather than re-implementing algorithms with while loops
- [ ] Multi-step simulations re-initialize temporary execution states before each simulation run to prevent state pollution
- [ ] Transitions express collaborator state preconditions or input domains via `sut_state(CollabState)` rather than surrogate fields on model state
- [ ] Collaborator delegation in impl transitions: when a delegated call raises `*Error` on unseeded state during fuzzing, the transition override catches the error or gates dispatch via `sut_state(CollabState)`
- [ ] Implementation pseudo-state machines override inner transitions (`def inner_<name>(self, *args):`) to invoke `target.method(*args)` (where `target: TargetClass = sut(TargetClass)`), returning `ret`; invoking `super().inner_<name>(...)` is prohibited (`PRE_LINT_NO_SUPER_IN_IMPL_INNER`); interface state machines must never call target methods or `sut(...)` in `inner_<name>`, must never mutate `self.state` (`PRE_LINT_NO_STATE_MUTATION_IN_INNER`), and must never contain `assert` (`PRE_LINT_NO_ASSERT_IN_INNER`)
- [ ] Implementation pseudo-state machines must not duplicate `require(...)` precondition guards present in the interface state machine
- [ ] Contracted operational exceptions (`*Exception`): external/collaborator faults; annotate virtual fields on `<Iface>State` as `attr: Env[bool] = True` (type alias, not constructor) and gate via `require_env(healthy_cond, ExpectedException, *args)` (`PRE_LINT_REQUIRE_ENV_MUST_BE_EXCEPTION`, `PRE_LINT_REQUIRE_ENV_NEEDS_ENV_STATE`); impl pseudo-SMs bind every inherited `Env` field in `__init__` via `self.bind("attr", lambda: ...)` (`PRE_LINT_UNBOUND_ENV_STATE`)
- [ ] Prohibition on `raises()` for contract violations (`*Error`): `*Error` must never use `with raises(...)` (`PRE_LINT_NO_RAISES_ERROR`); contract violations are gated out of fuzzing via `require(...)`/`require_arg(...)`, and verified in scenario tests via `self.checked.violating(ExpectedError).<method>(...)`
- [ ] Transition methods declare model state mutations directly on `self.state` using standard Python statements
- [ ] Postconditions and invariants use single-argument `assert test`; in interface state machines, `sut(TargetClass)` is permitted exclusively within `assert` statements to check observable properties on synthesized fakes
- [ ] State machines declare `@transition.seeding` methods to transition states during fuzzing from blank default initial states
- [ ] State machines and tests inspect state exclusively via `@test_only` query methods or public methods, never accessing private `_*` members
- [ ] Interface state machines and fake assertions inspect raw fields on interface data types rather than calling unimplemented data-type methods, properties, or `str()`/f-string formatting that may raise `NotImplementedError` on interface stubs
- [ ] Probing Pretense runtime internals is prohibited; reading, grepping, or inspecting `pretense/parts/` source code is prohibited

## Fake synthesis and fake fuzzing

- [ ] Interface pretense modules expose `Fake<Target> = synthesize_fake(<Target>StateMachine)` and `make_<name>_fake(state: Optional[<Target>State] = None) -> TargetClass` defaulting `state` via `proto.make_initial_state()`; pass `singletons={Collab: fake_collab}` to `Fake<Target>(state=..., singletons=...)` when fixed fake tests need `sut_state(CollabState)`
- [ ] Interface state machines define `make_initial_state(self) -> <Target>State`: open parameters (e.g. initial capacity) are assigned defaults via overridable properties or `make_initial_state()`; inlining concrete constants is prohibited
- [ ] Interface pretense modules compile Hypothesis stateful property tests on fake: `Fake<Target>FuzzTest = compile_hypothesis_test_case(proto=proto, initial_state_factory=proto.make_initial_state, name="Fake<Target>FuzzTest")`; `Fake<Target>FuzzTest` runs under `--cov` to cover all code in the interface state machine
- [ ] Optional `Test<Target>Fake(unittest.TestCase)` fixed tests are limited to transitions, seeding transitions, or edge branches not covered by `Fake<Target>FuzzTest` (statically required for 100% of transitions only when `compile_hypothesis_test_case` is absent)
- [ ] Interface state machines must not hardcode closed module-level fixture tables (such as fixed resolution dictionaries) that downstream `*_impl_pretense.py` modules cannot extend; parameterize or register fixture entries via `StateMachine` state, `@transition.seeding`, or overridable hooks
- [ ] Synthesized fakes implement their full public interface and `@test_only` accessors, evaluating assertions against the fake double during fake fuzzing

## Implementation verification and parity

- [ ] `Test<Target>ImplReal` inherits `LifecycleTestCase` (auto-registers imported `*_impl` targets/collaborators when `super().setUp()` runs, without `__initialize__`); `get_singleton(...)` and `sut(T)` must be called after `super().setUp()` (`PRE_LINT_SETUP_SUPER_ORDER`) and resolve `T` from the active `LifecycleRegistry` scope (or explicit `StateMachine(singletons={...})` in fixed tests); import all transitive `*_impl` collaborator modules used by the SUT, and wire `self.sm = TargetImplPseudoStateMachine(singletons={...})` + `self.checked = self.sm.as_checked(...)` (for multi-service state machines, `self.sm.as_checked(ServiceA)` and `self.sm.as_checked(ServiceB)` bind separate checked proxy adapters sharing `self.sm`)
- [ ] Open parameter specialization: implementation pseudo-state machines specialize uncontracted interface parameters by overriding the corresponding property hook or `make_initial_state()`
- [ ] Implementation pseudo-state machine transition overrides assert outcomes across both SUT and collaborator fakes via `sut(CollabClass)` and `sut_state(CollabState)`
- [ ] Fixed scenario tests in `Test<Target>ImplReal` are omitted unless requested by coverage feedback (`[from:pretense_coverage]`); initial verification relies on Hypothesis fuzzing (`<Target>FuzzTest`)
- [ ] When coverage feedback requests fixed tests (`[from:pretense_coverage]`): add scenario methods in `Test<Target>ImplReal` via `self.checked.<method>(*args)` or terminal `self.checked.violating(ExpectedError).<method>(*args)` (`PN_TERMINAL_VIOLATING`; one violation per test method), and/or modify transitions (e.g., `require`, `require_arg`, `fuzz_domain`, `preferred`, or `@transition.seeding`) to reach uncovered parts of the spec; never add `require()` guards to the adapter
- [ ] QA blame resolution: feedback prefixed with `[from:pretense_qa]` indicates functional assertion failures or transition mismatches, resolved by correcting test logic or adapter assertions
- [ ] Collaborator state isolation: when preceding assertions exhaust a collaborator, subsequent methods on that instance exit immediately; distinct scenario flows use dedicated test methods with fresh `setUp()` scopes
- [ ] Properties (`@property`) accessed via `self.checked.<prop>` dispatch transitions named `<prop>`; for Protocol classes, `@transition(name="<prop>")` avoids Pyright protocol property access errors
- [ ] Tests respect static type contracts and treat uncontracted failure conditions as undefined behavior: authoring tests for uncontracted non-concerns is prohibited
- [ ] Real fuzzing uses `compile_hypothesis_test_case(proto=proto, collaborators=[CollabStateMachine, ...], sut_factory=make_sut, initial_state_factory=proto.make_initial_state, name="<Target>FuzzTest")` (passing a bound `proto.make_initial_state`, never an unbound `Class.make_initial_state`, `PRE_LINT_UNBOUND_INITIAL_STATE_FACTORY`); `compile_hypothesis_test_case` auto-registers imported `*_impl` and `*_asm` modules from `make_sut`'s module globals into `get_default_registry()` before calling `make_sut()`, and `make_sut()` registers any extra/fake singletons via `LifecycleRegistry.register_singleton(...)` (never `__initialize__`)
- [ ] Static verification (`bin/check_files`) performs syntax and type analysis (`pretense_lint`, `pyright`); submit work via `bin/submit` for QA auditing
