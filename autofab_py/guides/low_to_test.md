# Guide: Low-Level Specification to Unit Test Alignment

## Summary

The artifact is a Python unit test module (`tests/<name>_test.py` or `tests/<name>_impl_test.py`) that tests `lib/<name>.py`, submitted via `submit(target="<target_file>", change_summary="...")`. Metadata blocks under `# --- CLEANROOM METADATA ---` are managed automatically by Cleanroom tooling upon `submit`; direct edits are prohibited. ONLY SINGLETONS AND DATA TYPES CAN BE TESTED. An `_impl` component with no singletons has nothing to test. Classes decorated with `@poly_type` are purely abstract and cannot be instantiated as standalone test targets; poly types are instantiated in tests only to supply collaborator instances needed to test singletons. Tests instantiate and exercise concrete target classes directly from the companion library implementation; creating mock doubles or test replacements of the target class under test is prohibited. Collaborator interface protocols are mocked. Library modules imported from role dependencies serve as read-only compilation stubs; asserting stub error outcomes (`NotImplementedError`) is prohibited.

Tests systematically verify contractual invariants (`INVARIANTS:`), checked preconditions (`PRECONDITIONS: - WHEN ... MUST raise ...Error`), and operational postconditions (`POSTCONDITIONS:`) from `low/<name>.pyi` across the transitive inheritance hierarchy. Happy-path tests verify primary collaborator wiring and valid returns. Alternate and error tests cover every conditional postcondition (`WHEN/MUST`) and checked precondition error. Uncontracted caller precondition violations (preconditions without an error in `PRECONDITIONS:`) cannot be tested; authoring tests that assert uncontracted precondition violations is strictly prohibited. Operational postcondition exceptions (`*Exception`) designate external failures and are tested via seeding. Caller preconditions without errors and static type contracts are accepted axiomatically; testing negative branches for uncontracted invalid inputs or non-concerns is prohibited. For lifecycle-managed components, each test method executes setup, operations, and assertions within an active phase scope (opened in `setUp` and closed in `tearDown` via `self.phase_scope = enter_phase(...)`, or enclosing each test method in a single `with enter_phase(...)` block); test helper methods must never open separate ephemeral `with enter_phase(...)` blocks or return singletons outside an active phase scope, as exiting `enter_phase` closes the scope and destroys instantiated singletons. Test execution enforces a strict 10-second timeout (`--timeout=10`); tests never consume wall-clock time with multi-second sleeps, testing time progression via fast sub-second intervals (`0.01`-`0.05`s), time patching, or deterministic synchronization events.

> META: "Unit tests systematically verify library implementations against low-level contract specifications, covering happy-path flows and every conditional postcondition branch."

## Lint checks

- [ ] Test modules define at least one `unittest.TestCase` subclass containing test methods whose names start with `test_`
- [ ] Imports of library modules use full package-qualified paths (e.g. `from <package_scope>.parts.<unit>.lib.<module> import ...`); bare partial 'parts' imports, unrooted 'lib' imports, and parent relative imports (`from ..`) are prohibited
- [ ] Test modules only import from their companion target module and never import foreign implementation modules (`*_impl.py`) or class names ending with an `Impl` suffix
- [ ] All imported library modules and third-party packages are declared in role dependencies (or belong to standard library, lifecycle, framework, unittest, or pytest)
- [ ] Test modules never define or redefine the class under test, and never mock the target class or target module (neither as `Mock<Target>` classes nor via `@patch`)
- [ ] Calls and decorators using `patch()` never target standard library modules directly, and `@patch` decorators on test methods have matching injected parameters on the test method
- [ ] Dynamic reflection (`getattr()`, `setattr()`, `hasattr()`), attribute or method access on `cast(Any, ...)`, and accessing non-dunder private members (`obj._*`) on target or collaborator objects are prohibited
- [ ] Top-level probe statements (try/except, raise, while, for, assert, or _PROBE symbols) are prohibited; executing the test suite or probing runtime behavior during authoring is prohibited (`TEST_LINT_NO_TOP_LEVEL_PROBE`)
- [ ] Testing expected exceptions uses `with self.assertRaises(ContractedError):` (or `with pytest.raises(ContractedError):`) for fail-closed assertion semantics; using try/except blocks in test methods is prohibited (`NO_TRY_EXCEPT_IN_TESTS`)
- [ ] Tests assert only contracted operational exceptions declared in companion specifications; asserting uncontracted caller preconditions is prohibited (`NO_ERROR_TESTING`)
- [ ] Test modules contain valid Python syntax, load cleanly into unittest during dry-run discovery without runtime crashes, and pass Pyright type checking with zero errors; executing test suites or running ad-hoc probes is prohibited; submit work via `bin/submit` so a downstream QA auditor can execute the test suite

## Document layout and imports

- [ ] Test modules import `unittest`, standard typing tools, and collection primitives
- [ ] For lifecycle-managed components, test modules import lifecycle test helpers (`LifecycleRegistry`, `enter_phase`, `system`) from `support.lib.lifecycle`; standalone component tests omit lifecycle imports
- [ ] Test modules import target classes and initialization functions directly from the companion library implementation module
- [ ] Test modules import collaborator interfaces from their respective interface packages
- [ ] Module-level factory helpers wrap primitive inputs into domain `NewType` instances
- [ ] Invariant collections of polymorphic base types (e.g. `Set[BaseType]`) use explicit collection type annotations or element casts to prevent type invariance errors
- [ ] Collaborator types omitted from read-only role dependencies use type-erased casts (`cast(Any, ...)`)
- [ ] Mock classes and helper definitions are placed above the test case class
- [ ] Test cases are separated by two blank lines, and test methods are separated by one blank line

## Happy-path test derivation

- [ ] Happy-path tests exercise the primary collaborator interaction sequence established in `low/<name>.pyi`
- [ ] Tests instantiate and exercise the concrete target class from the companion library implementation; creating mock doubles, dummy subclasses, or test replacements of the class under test is prohibited
- [ ] Collaborator interfaces are mocked using lightweight protocol implementations or test doubles matching property return types and method signatures exactly without phantom types
- [ ] Mock collaborators record incoming arguments and return scripted domain responses
- [ ] Input parameter bindings supply valid wire values for all required and optional parameters with domain `NewType`s explicitly wrapped
- [ ] Assertions verify that collaborator methods are invoked with properly converted actual values and return contracted successful records or values
- [ ] Assertions verify that mutator operations preserve type-level consistency invariants (`INVARIANTS:`)
- [ ] Every test method asserts explicit postconditions contracted in `low/<name>.pyi` or inherited from supertype protocols
- [ ] Happy-path test methods include brief comments or docstrings identifying the primary flow and postconditions in `low/<name>.pyi` being verified

## Alternate and error branch test derivation

- [ ] Tests explicitly target each conditional postcondition (`WHEN <condition>, MUST <outcome>.`) contracted in `low/<name>.pyi`
- [ ] Alternate and error test methods include brief comments or docstrings identifying the specific conditional postconditions or failure modes being verified
- [ ] Tests verify inherited supertype postconditions across the full inheritance hierarchy, accounting for stubs that omit redundant copy-down
- [ ] Tests target unknown entity lookups, omitted required parameters, missing message callbacks, default value fallbacks, parameter conversion failures, and collaborator failure propagation
- [ ] Tests target operations specifying domain exceptions, verifying that exceptions are raised with exact quoted error messages
- [ ] Diagnostic assertions verify exact error content, status flags, and advisory reminders quoted in `low/<name>.pyi` postconditions
- [ ] Contract violations with a contracted Error must be reachable: unit tests must test contracted error conditions (specified under `PRECONDITIONS:` using `- WHEN ..., MUST raise <Error>.`) with malformed or invalid inputs to verify contracted error reporting using `with self.assertRaises(ContractedError):` (catching exceptions via try/except in test methods is prohibited)
- [ ] Contract violations without contracted errors (preconditions without an error under `PRECONDITIONS:` or internal checks) cannot be tested; authoring tests that violate uncontracted caller preconditions is strictly prohibited
- [ ] Exceptions ending in `Exception` (`*Exception`) designate non-contract operational failures that are tested via seeding (such as collaborator mocking or simulated external faults)
- [ ] Tests accept caller preconditions without errors under `PRECONDITIONS:` axiomatically; testing violation or negative branch handling for uncontracted caller invariants is prohibited
- [ ] Tests respect static type contracts: passing `None` or invalid data types into parameters typed as non-optional is prohibited unless `Optional` or explicit runtime type validation is contracted
- [ ] Tests treat uncontracted failure conditions as undefined behavior: authoring tests for uncontracted non-concerns or asserting uncontracted defensive fallback outcomes is prohibited
- [ ] Assertions on error attributes verify only public domain entities contracted in the specification and never couple to internal graph placeholders or private implementation identifiers
- [ ] Test verification enforces a strict 10-second per-test timeout limit; tests verifying timeouts, delays, or cancellation never use multi-second sleeps or duration parameters approaching 10 seconds
- [ ] Operations with configurable timeout parameters are tested using fast sub-second intervals (e.g. 0.01 to 0.05 seconds) with minimal action delays
- [ ] Time progression across long durations is simulated without consuming wall-clock time by patching imported time functions (via `unittest.mock.patch`) in the target module
- [ ] Tests verifying mid-execution cancellation or interruption trigger the interrupt deterministically through collaborator action callbacks or synchronization events rather than sleeps

## Lifecycle scoping and mock registration

- [ ] Only singletons and data types are tested; an `_impl` component with no singletons has nothing to test; poly types are instantiated in tests only to supply collaborator instances needed to test singletons
- [ ] For lifecycle-managed components, each test execution creates an isolated `LifecycleRegistry` in `setUp`, calls target module `__initialize__(registry)`, and registers mock collaborators via `registry.register_instance(mock, keys=[...], tier=...)`
- [ ] For lifecycle-managed components, test assertions and collaborator resolutions execute within an active phase scope (opened in `setUp` and closed in `tearDown`, or wrapping the test method body in `with enter_phase(tier, registry=registry) as scope:`)
- [ ] For lifecycle-managed components, each test method executes setup, operations, and assertions within a single phase scope rather than across multiple sequential phase scopes where previous singleton mutations do not persist
- [ ] Helper methods that construct, register, or operate on target singletons receive the active `LifecycleScope` as an argument or execute within the test's active phase scope, and never open independent phase contexts that close upon helper return
- [ ] Test helper methods never return singletons from an exited `with enter_phase(...)` context, as singletons cannot resolve dependencies outside an open phase scope
- [ ] For lifecycle-managed components, target singletons are resolved from the active scope via `scope.get_singleton(TargetClass)`
- [ ] Tests interact with target instances strictly through their public contracts declared in `low/<name>.pyi`; invoking uncontracted configuration methods (`configure()`, `setup()`) is prohibited
- [ ] For standalone components, target classes are instantiated directly without lifecycle registry setup or scoping blocks
- [ ] Lifecycle phase scopes entered via `enter_phase` are thread-local; background helper threads avoid resolving singletons across threads without an active phase scope
