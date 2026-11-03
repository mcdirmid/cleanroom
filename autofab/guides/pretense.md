# Guide: Pretense State Machine and Test Author

## Summary

The artifact is a Pretense state machine and test module (`pretense/<name>_pretense.py`) modeling interface state transitions or verifying concrete implementations per `low/<name>.pyi`, submitted via `submit(target="<target_file>", change_summary="...")`. In multi-node sessions, multiple targets are processed together by package-relative alias path. Interface components define model state (`<Iface>State`), state machine transitions (`<Iface>StateMachine`), synthesized fakes (`make_<iface>_fake = synthesize_fake(<Iface>StateMachine)`), and fake property fuzzing (`Fake<Iface>FuzzTest = compile_hypothesis_test_case(...)`) with zero fixed test classes. Implementation components import upstream interface state machines and collaborator fakes, define implementation pseudo-state machines (inheriting interface state machines without defining new state dataclasses and containing zero `require_arg` statements) with transition overrides invoking `call_target(target.method(...))`, real scenario tests (`Test<Impl>Real`), and real implementation Hypothesis fuzzing (`compile_hypothesis_test_case`). Operations and state assertions derive strictly from contractual invariants (`INVARIANTS:`) and operational postconditions (`POSTCONDITIONS:`) in `low/<name>.pyi`. When addressing feedback, all sibling transitions and tests must be audited for the same failure pattern before submitting. Conversational commentary without tool execution is prohibited; execution proceeds continuously via tool calls until the round concludes with `submit` or `fail`.

Transitions model public target methods 1:1 using `@transition(TargetClass.method)` accepting signature `(self, arg1: T1, ...)` matching the target method's domain parameters 1:1; parameters named `target` or `suts` are strictly prohibited. Multi-transition splitting for the same method is strictly prohibited (`PN_STRICT_1_TO_1`); branching outcomes, parameter validation, and contracted exception handling live naturally inside the single transition body. Interface transitions define an AST pivot via `ret = make_return_value(fake_ret)` (or `make_return_value()` for void methods returning `None`). Implementation pseudo-state machine transitions define an AST pivot via `ret = call_target(target.method(*args))` (or `ret = call_target(ReturnType)`), where `target: TargetClass = sut(TargetClass)` resolves the statically typed instance and preserves return type `R` without requiring `require_arg` statements; zero-argument `call_target()` is strictly prohibited. Contracted exceptions are verified around the pivot via `with raises(ExpectedException): make_return_value()` or `with raises(ExpectedException): call_target(target.method(*args))`. Checked preconditions associated with contract violation errors (`*Error`) are gated via `require(...)` (model state preconditions) and `require_arg(...)` (argument domains) so the generator is prevented from synthesizing invalid calls; preconditions cannot be tested, and authoring scenario tests or transitions asserting `*Error` exceptions is strictly prohibited. Non-contract exceptions (`*Exception`) designate operational failures under unanticipated external or non-functional conditions (e.g. timeouts or resource limits), and `raises` is used exclusively for operational postcondition exceptions requiring environmental seeding, never for precondition contract violation errors (`*Error`). All behavioral postconditions, invariants, and differential checks are asserted using native single-argument Python `assert` (`assert test`); failure message strings (`assert test, msg`) and parenthesized tuples (`assert (x, y)`) are strictly prohibited (`PRE_LINT_ASSERT_SINGLE_ARG`). Concrete targets and collaborator fakes are accessed dynamically via `sut(TargetClass)` and `sut_state(TargetClass)` or `@test_only` query methods declared in `low/<name>.pyi`. Preconditions in `require(...)` only inspect `self.state`; referencing SUT objects or input arguments in `require(...)` is prohibited (`PN009`), and input argument constraints are declared exclusively in interface state machines via `require_arg(arg, Domain...)`. Implementation tests (`Test<Impl>Real`) drive operational scenarios through checked adapters (`self.checked = self.sm.as_checked(TargetClass, self.real)`) to achieve 100% statement coverage under `--no-fuzz --cov`.

> META: "Pretense 1 Next models interface state transitions 1:1 with natural branching, synthesizes verified in-memory fakes, executes fake property fuzzing, and verifies concrete implementations with concentric onion execution."

## Guide structure

- [ ] Interface pretense modules contain three sections in order: Model State & 1:1 Transitions (`<Iface>State`, `<Iface>StateMachine`), State Machine Proto & Fakes (`proto`, `Fake<Iface> = synthesize_fake(...)`, `make_<iface>_fake`), and Fake Hypothesis Fuzzing (`Fake<Iface>FuzzTest = compile_hypothesis_test_case(proto=proto, initial_state_factory=<Iface>State, name="Fake<Iface>FuzzTest")`), with zero fixed unit test classes
- [ ] Implementation pretense modules import upstream interface state machines and collaborator fakes, containing Implementation Pseudo State Machine (`<Impl>ImplPseudoStateMachine`), Real Implementation Tests (`Test<Impl>Real`), and Real Hypothesis Fuzzing (`compile_hypothesis_test_case`), defining zero state dataclasses and zero `require_arg` statements
- [ ] Interface pretense imports include `Domain`, `StateMachine`, `make_return_value`, `raises`, `require`, `require_arg`, `sut`, `sut_state`, `synthesize_fake`, `transition`; implementation pretense imports omit `require_arg` and `Domain`
- [ ] Autofab metadata comments at the bottom of the file are preserved without manual edits
- [ ] No conversational text or commentary is emitted without accompanying tool execution

## Lint checks

- [ ] Interface pretense modules define at least one `<Target>State` dataclass and one `StateMachine` subclass
- [ ] Implementation pretense modules define zero state dataclasses (`PN_IMPL_NO_STATE_CLASS`); implementation pseudo-state machines inherit from the interface state machine and define zero state classes
- [ ] Implementation pseudo-state machine transitions contain zero `require_arg` statements (`PN_IMPL_NO_REQUIRE_ARG`); domain constraints and generator strategies are defined exclusively in the interface state machine and inherited automatically
- [ ] Implementation pretense modules do not import `require_arg` (`PN_IMPL_NO_REQUIRE_ARG_IMPORT`)
- [ ] Implementation pretense modules define at least one `unittest.TestCase` (`Test<Impl>Real`) or compiled Hypothesis test case (`<Impl>FuzzTest`)
- [ ] Interface module imports `StateMachine`, `transition`, `make_return_value`, `raises`, `require`, `require_arg`, `sut`, `sut_state`, `synthesize_fake`, and `Domain`
- [ ] Legacy symbols `ensure`, `ensure_ret`, `ensure_raises`, `TransitionContext`, and `Expr` are never imported (`PN_NO_LEGACY_IMPORT`)
- [ ] Module imports target classes and initialization functions directly from the companion library implementation
- [ ] Module imports use package-qualified paths (e.g. 'from <scope>.parts.<unit>.lib.<impl> import ...'); bare 'lib' imports and multi-dot relative parent imports ('..') are prohibited
- [ ] Module contains valid Python syntax and passes Pyright type checking with zero errors and zero type suppression comments
- [ ] Module imports public specification symbols and lifecycle hooks; importing private `_*` functions or implementation internals from library modules is prohibited
- [ ] Test methods in `Test<Impl>Real` contain meaningful scenario executions; tautological assertions and empty test methods are prohibited
- [ ] Transitions never return or assign residual sentinel stubs (`NotBound`); test assertions never assert equality against `NotBound`
- [ ] Strict 1:1 transitions (`PN_STRICT_1_TO_1`): every public method on the target interface is modeled by exactly one `@transition(TargetClass.method)` transition; declaring multiple transitions for the same method is strictly prohibited
- [ ] Transition parameter matching: transition parameters match the target method 1:1 (`self, *args`); parameters named `target`, `sut`, or `suts` are strictly prohibited (`PN003_NO_TARGET_PARAM`)
- [ ] Transition methods declare zero default parameter values (`PN008_NO_DEFAULT_ARGUMENTS`); every domain parameter must be explicitly passed
- [ ] Single-argument assertions (`PRE_LINT_ASSERT_SINGLE_ARG`): all assertions across transitions and tests use native single-argument `assert test`; failure message strings (`assert test, msg`) and parenthesized tuples (`assert (x, y)`) are strictly prohibited
- [ ] Pivot node presence: every interface transition mapped to a target method defines an AST pivot via `ret = make_return_value(...)` (or `make_return_value()` for void methods returning `None`); every implementation pseudo-state machine transition defines an AST pivot via `ret = call_target(target.method(*args))` or `ret = call_target(ReturnType)`; zero-argument `call_target()` is strictly prohibited
- [ ] Preconditions via `require(...)` must only inspect `self.state` (`PN009`); referencing SUT objects (via `sut(...)`) or input arguments inside `require(...)` is prohibited
- [ ] Argument generation capability serves as an implicit antecedent for transition eligibility during fuzzing; unpopulated argument domains (such as `Domain.in_set` on an empty collection) cause the transition to be skipped cleanly rather than raising errors
- [ ] State machine classes never instantiate target service classes under test or invoke `get_singleton`; state machines operate purely on abstract model state (`self.state`)
- [ ] State machine methods never define nested algorithmic functions (such as `backtrack`, `solve`, or `search`) or while loops within transitions
- [ ] Test modules never tamper with, delete from, or clear `sys.modules`; runtime harness isolation and module reloading are managed exclusively by Autofab harnesses
- [ ] Module contains zero residual scaffolding crash placeholders (`_unimplemented_transition`, `Domain.required`, or `self.fail`); leaving placeholder stubs in transitions or tests is strictly prohibited

## Document layout and imports

- [ ] Module begins with a module-level docstring describing the target component and specification mapping
- [ ] Future annotations (`from __future__ import annotations`) is the first code statement
- [ ] Imports are grouped into standard library (`dataclasses`, `typing`, `unittest`), third-party (`hypothesis`, `pretense`), lifecycle support (`support.lib.lifecycle`), and target library imports
- [ ] Target classes and factory functions are imported from the companion library implementation using full package-qualified paths
- [ ] Collaborator types and domain `NewType` wrappers are imported from interface specifications or constructed via helper functions
- [ ] Sections are clearly marked with separator comments

## State modeling and transitions

- [ ] Model state is declared as a dataclass ending with `State` (e.g. `<Target>State`), storing state in standard containers (`list`, `dict`, `set`) or observable collections
- [ ] State machine is declared as a subclass of `StateMachine[<Target>State]`
- [ ] Strict 1:1 transitions: each public method across target interfaces is modeled by exactly one `@transition(TargetClass.method)` method matching the method name and parameter types
- [ ] Multi-transition splitting is strictly prohibited: operational branches, hit/miss outcomes, and exception conditions are implemented via standard Python `if/else` statements within the single transition body
- [ ] Transition methods declare preconditions via `require(condition)` checking model state preconditions directly without referencing input arguments
- [ ] Checked preconditions associated with contract violation errors (`*Error`) are gated in interface state machines via `require(condition)` (model state) and `require_arg(arg, domain)` (argument domains), preventing test generators from violating caller contracts
- [ ] Preconditions cannot be tested: companion scenario tests (`Test<Impl>Real`) and state machine transitions must never violate preconditions or assert `*Error` exceptions, even if preconditions are explicitly checked in implementation code
- [ ] Transition methods in interface state machines constrain input arguments via `require_arg(arg, domain, preferred=[...])`:
  - **Caller Precondition Contract**: `require_arg` defines the method's caller precondition contract, validated at runtime on every checked adapter call as well as generating fuzz values; domains must accept every value permitted by the method signature in `low/<name>.pyi` (including non-existent IDs or edge cases passed by tests)
  - **No Artificial Restriction**: Artificially restricting parameter domains to small subsets (e.g. `Domain.regex("[a-c]")` or `Domain.sampled_from(...)`) on open parameters is strictly prohibited; narrowing the domain causes checked adapter validation to fail on valid edge cases
  - **Fuzz Sizing with Preferred**: To cluster or bound generated values during fuzzing (such as reusing node names so graphs connect), use `preferred=[...]` (e.g. `preferred=["a", "b", "c"]`); `preferred` biases generation without restricting the runtime validator
  - **Open Parameters**: Open parameters use open domains (`Domain.any()`, `Domain.type(...)`, or syntactic pattern regexes matching the specification contract); closed sets (`Domain.sampled_from(...)`) are reserved strictly for finite enums or modes contracted in `low/<name>.pyi`
  - **Generic and Subscripted Types**: `Domain.type(T)` supports primitive types and subscripted typing generics (`Callable[[], Any]`, `Collection[str]`, `Sequence[int]`, `Mapping[K, V]`)
  - **State-Relative Domains**: Use `Domain.in_set(self.state.<collection>)`, `Domain.not_in(...)`, `Domain.subset_of(...)`, `Domain.just(val)`
  - **Structured Domains**: Use `Domain.object(SpecCls, field=...)`, `Domain.newtype(NewType, inner)`, `Domain.list_of(...)`, `Domain.set_of(...)`, `Domain.mapping_of(...)`, `Domain.optional(...)`
- [ ] Implementation pseudo-state machine transitions MUST NOT contain `require_arg(...)`; domain constraints and generation strategies belong exclusively to the interface state machine and are inherited automatically
- [ ] Interface transitions declare return values and AST pivots via `ret = make_return_value(fake_val)` (or `make_return_value()` for void methods returning `None`)
- [ ] Implementation pseudo-state machines selectively override transitions requiring SUT observation, capturing pre-state metrics before invoking `ret = call_target(target.method(*args))` (where `target: TargetClass = sut(TargetClass)`) or `ret = call_target(ReturnType)`, which executes target methods or queries target `@property` accessors directly with static return type preservation
- [ ] Contracted non-contract exceptions (`*Exception`) are verified around the pivot via `with raises(ExpectedException): make_return_value()` (interface SM) or `with raises(ExpectedException): call_target(target.method(*args))` (impl pseudo-SM); `raises` is used exclusively for operational postcondition exceptions requiring environmental seeding, never for precondition contract violation errors (`*Error`)
- [ ] Transition methods declare state mutations directly on `self.state` using normal Python statements
- [ ] Postconditions and invariants are asserted using single-argument `assert` (`assert test`) verifying structural properties and observable state on `self.state`, `sut(TargetClass)`, or collaborator fakes
- [ ] Seeding transitions: state machines declare `@transition.seeding` methods to initialize model state outside default initialization; seeding transitions are fake-only and are skipped during real SUT property fuzzing
- [ ] Test-only methods: state machines and tests inspect internal state exclusively via `@test_only` query methods contracted in `low/<name>.pyi` or public methods, never accessing private `_*` members
- [ ] Probing Pretense runtime internals is prohibited: reading, grepping, decompiling, or inspecting `pretense/parts/` or Pretense library source code is strictly prohibited; all API signatures and rules are documented directly in this guide

## Domain and synthesis quick reference

- [ ] Domain factory reference:
  - Primitive types: `Domain.type(str)`, `Domain.type(int)`, `Domain.type(float)`, `Domain.type(bool)`
  - Subscripted generic types: `Domain.type(Callable[[], Any])`, `Domain.type(Collection[str])`, `Domain.type(Sequence[int])`, `Domain.type(Mapping[str, int])`
  - Finite choices: `Domain.elements("a", "b", "c")`, `Domain.sampled_from(["x", "y"])`
  - State collections: `Domain.in_set(self.state.keys)`, `Domain.not_in(self.state.keys)`, `Domain.subset_of(self.state.keys)`
  - Composite types: `Domain.optional(Domain.type(str))`, `Domain.list_of(Domain.type(str), min_size=0, max_size=5)`, `Domain.dict_of(Domain.type(str), Domain.type(int))`
  - Open domains: `Domain.any()` for unconstrained inputs
  - Fuzz generation biasing: `require_arg(arg, Domain.type(str), preferred=["a", "b", "c"])`
- [ ] Interface fake and fuzz test structure:
  - State machine definition: `@dataclass class <Iface>State:` followed by `class <Iface>StateMachine(StateMachine[<Iface>State]):`
  - Transitions: `@transition(IfaceClass.method)` accepting domain parameters, evaluating `require(self.state.initialized)`, constraining arguments via `require_arg(arg, Domain...)`, mutating abstract state, and returning `make_return_value(result)` (or `make_return_value()` for None)
  - Fake synthesis: `Fake<Iface> = synthesize_fake(<Iface>StateMachine)` and `make_<iface>_fake(state: Optional[<Iface>State] = None) -> IfaceClass: return Fake<Iface>(state=state or <Iface>State())`
  - Fake fuzzing: `proto = <Iface>StateMachine()` (or `.to_proto()`), `Fake<Iface>FuzzTest = compile_hypothesis_test_case(proto=proto, initial_state_factory=<Iface>State, name="Fake<Iface>FuzzTest")`
- [ ] Implementation pseudo-state machine structure:
  - Definition: `class <Impl>ImplPseudoStateMachine(<Iface>StateMachine):` inheriting interface state machine without new state classes and containing zero `require_arg` statements
  - Overridden transitions: invoke `ret = call_target(target.method(*args))` (where `target: TargetClass = sut(TargetClass)`) or `ret = call_target(ReturnType)`, assert postconditions against `self.state` or `sut(<Impl>)`, and return `ret`; zero-argument `call_target()` and zero-argument `sut()` are strictly prohibited
  - Prohibition on model state mutation: implementation pseudo-state machine transition overrides must NEVER mutate `self.state` (`PN_IMPL_NO_STATE_MUTATION`). Model state updates and bookkeeping are owned exclusively by the inherited outer interface transition that runs first before delegating to `call_target`. Overrides only observe/assert postconditions against the real SUT.
  - Real test case: `class Test<Impl>Real(unittest.TestCase):` initializing SUT in `setUp()`, binding `self.sm = <Impl>ImplPseudoStateMachine(singletons={...})`, wrapping `self.checked = self.sm.as_checked(IfaceClass, self.real)`, and executing scenario methods
  - Real implementation fuzzing: `<Impl>FuzzTest = compile_hypothesis_test_case(proto=proto, sut_factory=make_sut, initial_state_factory=<Iface>State, name="<Impl>FuzzTest")`

## Fake synthesis and fake fuzzing

- [ ] Interface pretense modules expose synthesized fake classes `Fake<Target> = synthesize_fake(<Target>StateMachine)` and factory function `make_<name>_fake(state: Optional[<Target>State] = None) -> TargetClass` returning `Fake<Target>(state=state or <Target>State())`
- [ ] For modules with multiple service classes sharing model state, fake factory `make_<name>_fakes` synthesizes fakes backed by one shared `StateMachine` instance
- [ ] Interface pretense modules compile Hypothesis stateful property tests directly on the synthesized fake: `Fake<Target>FuzzTest = compile_hypothesis_test_case(proto=proto, initial_state_factory=<Target>State, name="Fake<Target>FuzzTest")`
- [ ] Synthesized fakes implement their full public interface and `@test_only` accessors, evaluating assertions against the fake double during fake fuzzing

## Implementation verification and parity

- [ ] Real implementation tests inherit from `unittest.TestCase` under class name `Test<Target>ImplReal`
- [ ] `setUp` initializes target instances, binds singletons into `self.sm = TargetImplPseudoStateMachine(singletons={...})`, and binds `self.checked = self.sm.as_checked(TargetClass, self.real)`. For lifecycle suites, manage registry and phase scope in `setUp` and `tearDown`
- [ ] Test methods in `Test<Target>ImplReal` drive operational scenarios via `self.checked.<method>(*args)` to achieve 100% statement coverage under `--no-fuzz --cov`
- [ ] Operational postconditions and invariants are verified automatically by transition `assert` checks on every call through `self.checked`; test methods contain zero redundant return-value assertions, reserving manual assertions strictly for `assertRaises` on contracted error branches; direct calls bypassing `self.checked` are prohibited
- [ ] Properties (`@property`) accessed via `self.checked.<prop>` dispatch transitions named `<prop>`; for Protocol classes, `@transition(name="<prop>")` avoids Pyright protocol property access errors
- [ ] Test methods in `Test<Target>ImplReal` are granular and single-concept, testing distinct error branches, precedence tiers, or algorithmic scenarios in dedicated test methods
- [ ] Tests respect static type contracts: passing `None` or invalid data types into parameters typed as non-optional is prohibited unless `Optional` or explicit runtime type validation is contracted in `low/<name>.pyi`
- [ ] Tests treat uncontracted failure conditions as undefined behavior: authoring tests for uncontracted non-concerns or asserting uncontracted defensive fallback outcomes is prohibited
- [ ] Real implementation fuzz testing is compiled via `compile_hypothesis_test_case(proto=proto, sut_factory=make_sut, initial_state_factory=<Target>State, name="<Target>FuzzTest")`
- [ ] Property fuzzing verifies invariant preservation and output equivalence between the real implementation and model transitions across pseudo-random action sequences

## Strict Prohibition on Test Skipping and Handwritten Mocks

- [ ] Skipping tests via `@unittest.skip*`, `@pytest.mark.skip*`, `pytest.skip()`, `unittest.SkipTest`, `__unittest_skip__`, or conditional skip guards (`@unittest.skipUnless(...)`) is strictly prohibited. Linters reject test skips with `PRE_LINT_NO_SKIP` / `TEST_LINT_NO_SKIP`.
- [ ] Authoring handwritten mock or fake SUT implementations inside companion pretense test files (`*_impl_pretense.py`) is strictly prohibited. The SUT must be imported directly from the target library module (`from <pkg>.lib.<unit_name> import <Target>Impl`).
- [ ] In the pretense authoring role, static verification (`bin/check_files`) only performs static syntax and type analysis (`pretense_lint` and `pyright`). It does NOT execute test suites or smoke fuzzing against compilation stubs. Test suites execute exclusively in QA (`pretense_qa`).

