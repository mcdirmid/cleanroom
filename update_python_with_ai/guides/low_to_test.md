<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T05:04:27Z
LAST_CHANGED: 2026-10-04T02:03:40Z
CHANGE: new file
CODE_HASH: 262cc56a6a86
-->

# Guide: Low-Level Specification to Unit Test Alignment

## Summary

The artifact is a Python unit test module (`tests/<name>_test.py` or `tests/<name>_impl_test.py`) that tests `lib/<name>.py`, submitted via `submit(target="<target_file>", change_summary="...")`. In multi-node sessions, multiple test modules are processed together by package-relative alias path. Tests are derived directly by cross-referencing contractual invariants (`INVARIANTS:`) and operational postconditions (`POSTCONDITIONS:`) in `low/<name>.pyi` (and `low/<name>_impl.pyi`) across the full transitive inheritance hierarchy. Target classes share the exact specification class name (`from <target_impl> import <TargetClass>` or `from lib.<target_impl> import <TargetClass>`); mocking target classes or concrete data types is prohibited, while collaborator interface protocols are mocked.

The test suite systematically covers the primary execution pathway and all alternate or error paths contracted in `low/<name>.pyi`. Happy-path test cases execute primary collaborator wiring, verifying valid inputs produce contracted responses and state transitions. Alternate and error test cases target each postcondition condition (`WHEN <condition>, MUST <outcome>.`): unknown identifiers, missing required parameters (with and without diagnostic notes), default value substitution, wire conversion failures, domain exceptions, and collaborator failure propagation. Diagnostic assertions verify exact contracted status flags, return values, error messages, and advisory reminders specified in quotes. Caller assumptions (`ASSUMPTIONS:`) define caller obligations accepted axiomatically; testing assumption violations or expecting defensive checks for assumptions is strictly prohibited. Overriding operations in low-level specifications omit redundant copy-down of base docstrings; tests verify that implementation classes satisfy all inherited supertype contracts transitively. Tests construct mock collaborators using scripted return values matching contracted property types and method signatures exactly without phantom types, initialize target modules into isolated test lifecycle registries, and execute under scoped lifecycle phases via `enter_phase`. Domain contracts enforce strict nominal typing via `typing.NewType`; raw primitive literals (`str`, `int`) passed into dataclasses, messages, and collaborator arguments fail static type-checking unless explicitly wrapped in their domain `NewType` constructors or created via module-level factory helpers. Invariant collections (such as `Set[DagMessage]`) require explicit container type annotations or element casts when populated with subtype instances. When test setup requires types from external packages omitted from read-only `pyright_deps` in `tests/BUILD.bazel`, type-erased casts (`cast(Any, ...)`) construct values without importing undeclared dependencies.

> META: "Unit tests systematically verify library implementations against low-level contract specifications, covering happy-path flows and every conditional postcondition branch."

## Lint checks

- [ ] Test modules inherit from `unittest.TestCase` and organize test methods named `test_<scenario>`
- [ ] Target classes are imported from implementation modules (or defining modules for concrete data types extending polytypes) and instantiated directly; target classes are never mocked
- [ ] Collaborator interfaces are mocked using lightweight protocol implementations or test doubles matching property return types and method signatures exactly
- [ ] Mock classes and test doubles avoid phantom types or non-existent symbols not declared in interface specifications
- [ ] Every test method asserts explicit postconditions contracted in `low/<name>.pyi` or inherited from supertype protocols
- [ ] Tests run under an active lifecycle phase matching the component's declared tier using `enter_phase`
- [ ] All imported library modules are declared in the unit's `pyright_deps` in `tests/BUILD.bazel`
- [ ] All tests execute and pass cleanly under Bazel test runners

## Document layout and imports

- [ ] Test modules import `unittest`, standard typing tools, and collection primitives
- [ ] Test modules import lifecycle test helpers (`LifecycleRegistry`, `enter_phase`, `system`) from `support.lib.lifecycle`
- [ ] Test modules import target classes and initialization functions directly from the library implementation module
- [ ] Test modules import collaborator interfaces from their respective interface packages
- [ ] Module-level factory helpers (e.g. `_make_dag_node`, `_make_response`) wrap primitive inputs into domain `NewType` instances
- [ ] Invariant collections of polymorphic base types (e.g. `Set[BaseType]`) use explicit collection type annotations or element casts to prevent type invariance errors
- [ ] Collaborator types omitted from read-only build dependencies use type-erased casts (`cast(Any, ...)`) rather than undeclared package imports
- [ ] Mock classes and helper definitions are placed above the test case class
- [ ] Test cases are separated by two blank lines, and test methods are separated by one blank line

## Happy-path test derivation

- [ ] Happy-path tests exercise the primary collaborator interaction sequence established in `low/<name>.pyi`
- [ ] Mock collaborators record incoming arguments and return scripted domain responses
- [ ] Mock properties return exact contracted types (e.g. `Mapping[ParameterName, ...]` rather than `Mapping[str, ...]`)
- [ ] Input parameter bindings supply valid wire values for all required and optional parameters with domain `NewType`s explicitly wrapped
- [ ] Assertions verify that collaborator methods are invoked with properly converted actual values
- [ ] Assertions verify that the operation returns the expected successful response record or value
- [ ] Assertions verify that mutator operations preserve type-level consistency invariants (`INVARIANTS:`)

## Alternate and error branch test derivation

- [ ] Tests explicitly target each conditional postcondition (`WHEN <condition>, MUST <outcome>.`) contracted in `low/<name>.pyi`
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

## Lifecycle scoping and mock registration

- [ ] Each test execution creates an isolated `LifecycleRegistry` in `setUp`
- [ ] Target module `__initialize__(registry)` is called to register the implementation
- [ ] Mock collaborator instances are registered using `registry.register_instance(mock, keys=[...], tier=...)`
- [ ] Test assertions execute within a `with enter_phase(tier, registry=registry) as scope:` context block
- [ ] Target singletons are resolved from the active scope via `scope.get_singleton(TargetClass)`
