# Guide: Low-Level Specification to Unit Test Alignment

## Summary

The artifact is a Python unit test module (`tests/<name>_test.py` or `tests/<name>_impl_test.py`) that tests `lib/<name>.py`, submitted via `submit(target="<target_file>", change_summary="...")`. In multi-node sessions, multiple test modules are processed together by package-relative alias path. Cleanroom metadata blocks at the bottom of the file (under `# --- CLEANROOM METADATA ---` and `# --- END CLEANROOM METADATA ---`) are managed automatically by Cleanroom tooling upon `submit(change_summary=...)`; direct edits to metadata blocks are prohibited and rejected by editing tools. ONLY SINGLETONS AND DATA TYPES CAN BE TESTED. An `_impl` component that has no singletons has nothing to test. Classes decorated with `@poly_type` are purely abstract and cannot be refined by a poly type with the same short name (though they may be extended by other poly types with distinct names to create new abstract object types); poly types can be instantiated in tests only to test singletons that need instances of poly types to be tested with (such as mock or stub collaborator inputs). Tests never attempt to instantiate or test poly types directly as standalone units of verification. Tests are derived directly by cross-referencing contractual invariants (`INVARIANTS:`) and operational postconditions (`POSTCONDITIONS:`) in `low/<name>.pyi` (and `low/<name>_impl.pyi`) across the full transitive inheritance hierarchy. Target classes share the exact specification class name (`from <package>.lib.<target_impl> import <TargetClass>`). Tests must instantiate and exercise the concrete target classes directly from the companion library implementation; creating mock doubles, dummy subclasses, or test replacements of any class under test is prohibited, while collaborator interface protocols from dependencies are mocked. Library modules imported from role dependencies serve as read-only Cleanroom compilation stubs (`CLEANROOM TEST STUB v4`) in the test workspace to support static import resolution and type checking; asserting stub error outcomes (`NotImplementedError` or uninitialized exceptions) is prohibited, as tests execute against the full library implementation during downstream verification.

The test suite systematically covers the primary execution pathway and all alternate or error paths contracted in `low/<name>.pyi`. Happy-path test cases execute primary collaborator wiring, verifying valid inputs produce contracted responses and state transitions. Alternate and error test cases target each postcondition condition (`WHEN <condition>, MUST <outcome>.`): unknown identifiers, missing required parameters (with and without diagnostic notes), default value substitution, wire conversion failures, domain exceptions, and collaborator failure propagation. Diagnostic assertions verify exact contracted status flags, return values, error messages, and advisory reminders specified in quotes. Caller assumptions (`ASSUMPTIONS:`) define caller obligations accepted axiomatically; testing assumption violations or expecting defensive checks for assumptions is strictly prohibited. Test methods include brief comments or docstrings indicating how each test corresponds to the low-level specification postconditions, invariants, or scenarios being verified. Overriding operations in low-level specifications omit redundant copy-down of base docstrings; tests verify that implementation classes satisfy all inherited supertype contracts transitively. Tests construct mock collaborators using scripted return values matching contracted property types and method signatures exactly without phantom types. For lifecycle-managed components declaring a tier, tests initialize target modules into isolated test lifecycle registries and execute within an active phase scope via `enter_phase(phase, registry=...)`; a phase scope is ephemeral and disposes of all singleton instances upon exit. Each test method executes its entire interaction sequence (setup, operations, and assertions) within a single phase scope rather than across multiple sequential phase scopes where singleton state does not persist. Helper methods that construct or operate on target singletons receive the active scope as a parameter rather than opening independent phase scopes that close upon return. For standalone components without lifecycle tiering, target classes are instantiated directly without lifecycle registries. Domain contracts enforce strict nominal typing via `typing.NewType`; raw primitive literals (`str`, `int`) passed into dataclasses, messages, and collaborator arguments fail static type-checking unless explicitly wrapped in their domain `NewType` constructors or created via module-level factory helpers. Invariant collections (such as `Set[DagMessage]`) require explicit container type annotations or element casts when populated with subtype instances. When test setup requires types from external packages omitted from read-only role dependencies, type-erased casts (`cast(Any, ...)`) construct values without importing undeclared dependencies; accessing attributes or invoking methods on `cast(Any, ...)` is prohibited. Tests interact with target instances strictly through their public contracts in `low/<name>.pyi`; accessing private attributes (`obj._*`) or calling uncontracted multi-phase configuration methods (such as ad-hoc `configure()` or `setup()` methods) is prohibited. Target singletons are resolved via `scope.get_singleton(TargetClass)` and parameterized through contracted operations or lifecycle phase setup. Test verification enforces a strict 10-second per-test execution timeout (`--timeout=10`). Tests verifying time-dependent behaviors (such as timeouts, deadlines, delays, retries, or mid-execution cancellation) never consume real wall-clock time through multi-second sleeps, blocking loops, or timeouts that approach or exceed the 10-second limit. Time-dependent contracts are tested without consuming wall-clock time: operations accepting timeout durations use fast sub-second values (e.g. `0.01` to `0.05` seconds); time progression across larger durations is simulated via standard library mocks (`unittest.mock.patch` targeting time functions imported in the companion module); asynchronous or mid-execution interruptions (such as cancellation) are triggered deterministically through action callbacks or synchronization events rather than sleeping threads; and tests assert exact contracted signals (e.g. timeout or cancellation exceptions) rather than uncontracted fallback states. In multi-threaded test setups, lifecycle phase scopes entered via `enter_phase` are thread-local; background helper threads avoid looking up singletons across threads without an active phase scope. Conversational commentary without tool execution is prohibited; step execution continues exclusively via tool calls until the round concludes with `submit` or `fail`.

> META: "Unit tests systematically verify library implementations against low-level contract specifications, covering happy-path flows and every conditional postcondition branch."

## Lint checks

- [ ] Test modules define at least one `unittest.TestCase` subclass containing test methods whose names start with `test_`
- [ ] Imports of library modules use full package-qualified paths (e.g. `from <package_scope>.parts.<unit>.lib.<module> import ...`); bare partial 'parts' imports and unrooted 'lib' imports are prohibited
- [ ] Test modules only import from their companion target module and never import foreign implementation modules (`*_impl.py`) or class names ending with an `Impl` suffix
- [ ] All imported library modules and third-party packages are declared in role dependencies (or belong to standard library, lifecycle, framework, unittest, or pytest)
- [ ] Test modules never define or redefine the class under test, and never mock the target class or target module (neither as `Mock<Target>` classes nor via `@patch`)
- [ ] Calls and decorators using `patch()` never target standard library modules directly, and `@patch` decorators on test methods have matching injected parameters on the test method
- [ ] Dynamic reflection (`getattr()`, `setattr()`, `hasattr()`), attribute or method access on `cast(Any, ...)`, and accessing non-dunder private members (`obj._*`) on target or collaborator objects are prohibited
- [ ] Test modules contain valid Python syntax, load cleanly into unittest during dry-run test discovery without runtime import or decorator crashes, and pass Pyright type checking with zero errors

## Document layout and imports

- [ ] Test modules import `unittest`, standard typing tools, and collection primitives
- [ ] For lifecycle-managed components, test modules import lifecycle test helpers (`LifecycleRegistry`, `enter_phase`, `system`) from `support.lib.lifecycle`; standalone component tests omit lifecycle imports
- [ ] Test modules import target classes and initialization functions directly from the companion library implementation module
- [ ] Test modules import collaborator interfaces from their respective interface packages
- [ ] Module-level factory helpers (e.g. `_make_dag_node`, `_make_response`) wrap primitive inputs into domain `NewType` instances
- [ ] Invariant collections of polymorphic base types (e.g. `Set[BaseType]`) use explicit collection type annotations or element casts to prevent type invariance errors
- [ ] Collaborator types omitted from read-only role dependencies use type-erased casts (`cast(Any, ...)`)
- [ ] Mock classes and helper definitions are placed above the test case class
- [ ] Test cases are separated by two blank lines, and test methods are separated by one blank line

## Happy-path test derivation

- [ ] Happy-path tests exercise the primary collaborator interaction sequence established in `low/<name>.pyi`
- [ ] Target class instantiation: tests instantiate and exercise the concrete target class from the companion library implementation; creating mock doubles, dummy subclasses, or test replacements of the target class under test is prohibited
- [ ] Collaborator interfaces are mocked using lightweight protocol implementations or test doubles matching property return types and method signatures exactly
- [ ] Mock classes and test doubles avoid phantom types or non-existent symbols not declared in interface specifications
- [ ] Mock collaborators record incoming arguments and return scripted domain responses
- [ ] Mock properties return exact contracted types (e.g. `Mapping[ParameterName, ...]` rather than `Mapping[str, ...]`)
- [ ] Input parameter bindings supply valid wire values for all required and optional parameters with domain `NewType`s explicitly wrapped
- [ ] Assertions verify that collaborator methods are invoked with properly converted actual values
- [ ] Assertions verify that the operation returns the expected successful response record or value
- [ ] Assertions verify that mutator operations preserve type-level consistency invariants (`INVARIANTS:`)
- [ ] Every test method asserts explicit postconditions contracted in `low/<name>.pyi` or inherited from supertype protocols
- [ ] Happy-path test methods include brief comments or docstrings identifying the primary flow and postconditions in `low/<name>.pyi` being verified
- [ ] Tests are structured to execute cleanly against real implementations in downstream verification

## Alternate and error branch test derivation

- [ ] Tests explicitly target each conditional postcondition (`WHEN <condition>, MUST <outcome>.`) contracted in `low/<name>.pyi`
- [ ] Alternate and error test methods include brief comments or docstrings identifying the specific conditional postconditions or failure modes in `low/<name>.pyi` being verified
- [ ] Tests verify inherited supertype postconditions across the full inheritance hierarchy, accounting for stubs that omit redundant copy-down
- [ ] Tests target unknown entity lookups where contracts specify unknown identifier postconditions
- [ ] Tests target omitted required parameters where contracts specify missing parameter postconditions
- [ ] Tests target missing parameter callbacks where contracts specify missing note postconditions
- [ ] Tests target omitted optional parameters where contracts specify default value postconditions, verifying default binding
- [ ] Tests target parameter conversion failures asserting contracted error feedback
- [ ] Tests target collaborator failure responses asserting failure propagation
- [ ] Tests target operations specifying domain exceptions, verifying that exceptions are raised with exact quoted error messages
- [ ] Diagnostic assertions verify exact error content, status flags, and advisory reminders quoted in `low/<name>.pyi` postconditions
- [ ] Tests accept caller assumptions under `ASSUMPTIONS:` axiomatically; testing assumption violations or negative branch handling for assumed caller invariants is prohibited
- [ ] Test verification enforces a strict 10-second per-test timeout limit; tests verifying timeouts, delays, or cancellation never use multi-second sleeps or duration parameters that approach or exceed the 10-second limit
- [ ] Operations with configurable timeout parameters are tested using fast sub-second intervals (e.g. 0.01 to 0.05 seconds) with minimal action delays, verifying that timeout postconditions trigger deterministically in milliseconds
- [ ] Time progression across long durations is simulated without consuming wall-clock time by patching imported time functions (e.g. via `unittest.mock.patch`) in the target module
- [ ] Tests verifying mid-execution cancellation or interruption trigger the interrupt deterministically through collaborator action callbacks or synchronization events rather than asynchronous sleep races, asserting exact contracted exception signals rather than uncontracted return values

## Lifecycle scoping and mock registration

- [ ] Only singletons and data types are tested; an _impl component with no singletons has nothing to test; poly types are instantiated in tests only to supply collaborator instances needed to test singletons, and tests never attempt to test poly types directly as standalone units of verification
- [ ] For lifecycle-managed components, each test execution creates an isolated `LifecycleRegistry` in `setUp`
- [ ] For lifecycle-managed components, target module `__initialize__(registry)` is called to register the implementation
- [ ] For lifecycle-managed components, mock collaborator instances are registered using `registry.register_instance(mock, keys=[...], tier=...)`
- [ ] For lifecycle-managed components, test assertions execute within a `with enter_phase(tier, registry=registry) as scope:` context block
- [ ] For lifecycle-managed components, each test method executes setup, operations, and assertions within a single phase scope rather than across multiple sequential phase scopes where previous singleton mutations do not persist
- [ ] Helper methods that construct, register, or operate on target singletons receive the active `LifecycleScope` as an argument rather than opening independent phase contexts that close upon helper return
- [ ] For lifecycle-managed components, target singletons are resolved from the active scope via `scope.get_singleton(TargetClass)`
- [ ] Tests interact with target instances strictly through their public contracts declared in `low/<name>.pyi`
- [ ] Singletons are resolved from `scope.get_singleton(...)` or instantiated directly, and parameterized via contracted operations or `enter_phase(tier, setup=...)`; invoking uncontracted multi-phase configuration methods (such as ad-hoc `configure()` or `setup()` methods) not declared in `low/<name>.pyi` is prohibited
- [ ] For standalone components, target classes are instantiated directly without lifecycle registry setup or scoping blocks
- [ ] Lifecycle phase scopes entered via `enter_phase` are thread-local; background helper threads avoid resolving singletons across threads without an active phase scope

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T05:04:27Z
LAST_CHANGED: 2026-10-04T02:03:40Z
CHANGE: Clarify that cleanroom metadata headers are managed automatically by submit
CODE_HASH: 262cc56a6a86
-->
