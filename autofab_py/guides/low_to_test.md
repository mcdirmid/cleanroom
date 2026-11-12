# Guide: Low-Level Specification to Unit Test Alignment

## Summary

The artifact is a Python unit test module (`tests/<name>_test.py` or `tests/<name>_impl_test.py`) that tests `lib/<name>.py`, submitted via `submit(target="<target_file>", change_summary="...")` when modified, or contested via `reject(target="<target_file>", reason="...")` strictly on unmodified files when asserting the existing test suite is already compliant with the specification. Metadata blocks under `# --- CLEANROOM METADATA ---` are managed automatically by Cleanroom tooling upon `submit` or `reject`; direct edits are prohibited. ONLY SINGLETONS AND DATA TYPES CAN BE TESTED. An `_impl` component with no singletons has nothing to test. Classes decorated with `@poly_type` are purely abstract and cannot be instantiated as standalone test targets; poly types are instantiated in tests only to supply collaborator instances needed to test singletons. Tests instantiate and exercise concrete target classes directly from the companion library implementation; creating mock doubles or test replacements of the target class under test is prohibited. Collaborator interface protocols are mocked using `@fake`; mutating or monkeypatching methods on live singleton instances is prohibited. Library modules imported from role dependencies serve as read-only compilation stubs; asserting stub error outcomes (`NotImplementedError`) is prohibited.

Tests systematically verify contractual invariants (`INVARIANTS:`), checked preconditions (`PRECONDITIONS: - WHEN ... MUST raise ...Error`), and operational postconditions (`POSTCONDITIONS:`) from `low/<name>.pyi` across the transitive inheritance hierarchy. Happy-path tests verify primary collaborator wiring and valid returns. Alternate and error tests cover every conditional postcondition (`WHEN/MUST`) and checked precondition error. Uncontracted caller precondition violations (preconditions without an error in `PRECONDITIONS:`) cannot be tested; authoring tests that assert uncontracted precondition violations is strictly prohibited. Operational postcondition exceptions (`*Exception`) designate external failures and are tested via seeding. Caller preconditions without errors and static type contracts are accepted axiomatically; testing negative branches for uncontracted invalid inputs or non-concerns is prohibited. For lifecycle-managed components, test cases inherit from `LifecycleTestCase` (from `support.lib.lifecycle`). `LifecycleTestCase` automatically discovers target implementations from imported library modules, registers them into an isolated registry, instantiates collaborator fakes decorated with `@fake`, enters the appropriate phase scope, populates `self.sut` with the target singleton under test, and guarantees scope cleanup via `addCleanup`. Test modules never define `setUp` with manual `LifecycleRegistry` or `enter_phase`, never import `__initialize__`, and never define `tearDown` with manual scope closing. Test execution enforces a strict 10-second timeout (`--timeout=10`); tests never consume wall-clock time with multi-second sleeps, testing time progression via fast sub-second intervals (`0.01`-`0.05`s), time patching, or deterministic synchronization events. Test modules conclude with `if __name__ == "__main__": unittest.main()`.

> META: "Unit tests systematically verify library implementations against low-level contract specifications, covering happy-path flows and every conditional postcondition branch."

## Lint checks

- [ ] Test modules define at least one `LifecycleTestCase` subclass (or `unittest.TestCase` for pure standalone data-type tests) containing test methods whose names start with `test_`
- [ ] Imports of library modules use package-qualified paths rooted at the Python package containing `lib/` (e.g. `from <unit>.lib.<module> import ...` for single-unit or benchmark packages, or `from <package_scope>.parts.<unit>.lib.<module> import ...` when a package namespace sits above `parts/`); bare partial 'parts' imports, unrooted 'lib' imports, and relative imports (`from .` or `from ..`) are prohibited
- [ ] The package scope for imports is the Python package name (e.g. `from dag_engine_lite.lib...`), never the outer repository root directory or flight runner folder name (`<unit>_<model>_<run>`)
- [ ] Local verification via `bin/check_files` enforces the full static verification suite (syntax, types, structural rules, import paths, slug references, try/except ban, and dry-run collection); downstream checks after `bin/submit` refer strictly to empirical test suite execution by QA auditors, not additional static linters
- [ ] Test modules only import from their companion target module and never import foreign implementation modules (`*_impl.py`) or class names ending with an `Impl` suffix
- [ ] Test modules never import or invoke `__initialize__`
- [ ] In `LifecycleTestCase` subclasses, collaborator fakes are declared using the `@fake` decorator
- [ ] All imported library modules and third-party packages are declared in role dependencies (or belong to standard library, lifecycle, framework, unittest, or pytest)
- [ ] Test modules never define or redefine the class under test, and never mock the target class or target module (neither as `Mock<Target>` classes nor via `@patch`)
- [ ] Calls and decorators using `patch()` never target standard library modules directly, and `@patch` decorators on test methods have matching injected parameters on the test method
- [ ] Dynamic reflection (`getattr()`, `setattr()`, `hasattr()`), attribute or method access on `cast(Any, ...)`, and accessing non-dunder private members (`obj._*`) on target or collaborator objects are prohibited
- [ ] Top-level probe statements (try/except, raise, while, for, assert, or \_PROBE symbols) are prohibited; executing the test suite or probing runtime behavior during authoring is prohibited (`TEST_LINT_NO_TOP_LEVEL_PROBE`)
- [ ] Testing expected exceptions uses `with self.assertRaises(ContractedError):` (or `with pytest.raises(ContractedError):`) for fail-closed assertion semantics; using try/except blocks in test methods is prohibited (`NO_TRY_EXCEPT_IN_TESTS`)
- [ ] Tests assert only contracted operational exceptions declared in companion specifications; asserting uncontracted caller preconditions is prohibited (`NO_ERROR_TESTING`)
- [ ] Test comments and docstrings never cite declared specification contract slugs or bracketed slug tags (`[slug:...]` or `<unit>.<contract>.<facet>`); citing specification slugs in code artifacts is strictly prohibited (`NO_SLUG_REFERENCES`)
- [ ] Test modules conclude with `if __name__ == "__main__": unittest.main()`
- [ ] Test modules contain valid Python syntax, load cleanly into unittest during dry-run discovery without runtime crashes, and pass Pyright type checking with zero errors; executing test suites or running ad-hoc probes is prohibited; submit work via `bin/submit` so a downstream QA auditor can execute the test suite

## Document layout and imports

- [ ] Test modules import `unittest`, standard typing tools, and collection primitives
- [ ] For lifecycle-managed components, test modules import `LifecycleTestCase` and `fake` from `support.lib.lifecycle`; standalone component tests omit lifecycle imports
- [ ] Test modules import target classes directly from the companion library implementation module without importing `__initialize__`
- [ ] Test modules import collaborator interfaces from their respective interface packages
- [ ] When protocols in `<unit>` and concrete classes in `<unit>_impl` share names, tests import the companion implementation module (`from <package>.lib import <unit>_impl`) and reference `<unit>_impl.<Class>`, or alias the concrete class on import (`from <package>.lib.<unit>_impl import <Class> as <Class>Target`)
- [ ] Module-level factory helpers wrap primitive inputs into domain `NewType` instances
- [ ] Invariant collections of polymorphic base types (e.g. `Set[BaseType]`) use explicit collection type annotations or element casts to prevent type invariance errors
- [ ] Collaborator types omitted from read-only role dependencies use type-erased casts (`cast(Any, ...)`)
- [ ] Mock classes and helper definitions are placed above the test case class
- [ ] Test cases are separated by two blank lines, and test methods are separated by one blank line
- [ ] Test modules terminate with `if __name__ == "__main__": unittest.main()`

## Happy-path test derivation

- [ ] Happy-path tests exercise the primary collaborator interaction sequence established in `low/<name>.pyi`
- [ ] Tests instantiate and exercise the concrete target class from the companion library implementation; creating mock doubles, dummy subclasses, or test replacements of the class under test is prohibited
- [ ] Collaborator interfaces are mocked using lightweight protocol implementations or test doubles matching property return types and method signatures exactly without phantom types
- [ ] Mock collaborators record incoming arguments and return scripted domain responses
- [ ] Input parameter bindings supply valid wire values for all required and optional parameters with domain `NewType`s explicitly wrapped
- [ ] Assertions verify that collaborator methods are invoked with properly converted actual values and return contracted successful records or values
- [ ] Assertions verify that mutator operations preserve type-level consistency invariants (`INVARIANTS:`)
- [ ] Every test method asserts explicit postconditions contracted in `low/<name>.pyi` or inherited from supertype protocols
- [ ] Happy-path test methods include brief docstrings describing the primary flow and postconditions in plain English prose (e.g. 'Verify successful task execution dispatches notifications'); citing raw contract slug IDs or slug tags is prohibited

## Alternate and error branch test derivation

- [ ] Tests explicitly target each conditional postcondition (`WHEN <condition>, MUST <outcome>.`) contracted in `low/<name>.pyi`
- [ ] Alternate and error test methods include brief docstrings describing the specific conditional postconditions or failure modes in plain English prose (e.g. 'Verify duplicate node registration raises DuplicateNodeError'); citing raw contract slug IDs or slug tags is prohibited
- [ ] Tests verify inherited supertype postconditions across the full inheritance hierarchy, accounting for stubs that omit redundant copy-down
- [ ] Tests target unknown entity lookups, omitted required parameters, missing message callbacks, default value fallbacks, parameter conversion failures, and collaborator failure propagation
- [ ] Tests target operations specifying domain exceptions, verifying that exceptions are raised with exact quoted error messages
- [ ] Diagnostic assertions verify exact error content, status flags, and advisory reminders quoted in `low/<name>.pyi` postconditions
- [ ] Test input and mock wiring: when authoring tests for error handling, failure policies, or state transitions, wire the failing callable or mock directly into the node or method under test; passing a succeeding mock default when asserting failure behavior is strictly prohibited
- [ ] Assertion orientation: ordering and inequality assertions must strictly match contract ordering semantics (e.g. descending priority places higher priority elements first at lower indices, where index_high < index_low)
- [ ] Contract violations with a contracted Error must be reachable: unit tests must test contracted error conditions (specified under `PRECONDITIONS:` using `- WHEN ..., MUST raise <Error>.`) with malformed or invalid inputs to verify contracted error reporting using `with self.assertRaises(ContractedError):` (catching exceptions via try/except in test methods is prohibited)
- [ ] Contract violations without contracted errors (preconditions without an error under `PRECONDITIONS:`) and uncontracted failure conditions define undefined behavior; authoring tests that assert uncontracted precondition violations, non-concerns, or defensive fallbacks is strictly prohibited
- [ ] Resolving coverage and QA blame: blame feedback identifies specifications via `[slug:<spec.slug>]` from `low/<name>.pyi`; line numbers in `Lines:` (if present) reference lines strictly within `tests/*_test.py` (never lines of `low/*.pyi` or `lib/*.py`); author tests covering the semantic contract identified by blame feedback without writing slug IDs into test code
- [ ] Exceptions ending in `Exception` (`*Exception`) designate non-contract operational failures that are tested via seeding (such as collaborator mocking or simulated external faults)
- [ ] Tests respect static type contracts: passing `None` or invalid data types into parameters typed as non-optional is prohibited unless `Optional` or explicit runtime type validation is contracted
- [ ] Assertions on error attributes verify only public domain entities contracted in the specification and never couple to internal graph placeholders or private implementation identifiers
- [ ] Test verification enforces a strict 10-second per-test timeout limit; tests verifying timeouts, delays, or cancellation never use multi-second sleeps or duration parameters approaching 10 seconds
- [ ] Operations with configurable timeout parameters are tested using fast sub-second intervals (e.g. 0.01 to 0.05 seconds) with minimal action delays
- [ ] Time progression across long durations is simulated without consuming wall-clock time by patching imported time functions (via `unittest.mock.patch`) in the target module
- [ ] Tests verifying mid-execution cancellation or interruption trigger the interrupt deterministically through collaborator action callbacks or synchronization events rather than sleeps

## Lifecycle scoping and mock registration

- [ ] For lifecycle-managed components, test classes inherit from `LifecycleTestCase`, which automatically discovers targets and registers fakes
- [ ] Collaborator fakes are declared inside or alongside the test class using `@fake` from `support.lib.lifecycle`, implementing collaborator protocols and declaring tier matching the collaborator interface
- [ ] Test methods access the target singleton under test directly via `self.sut` (or `self.get_singleton(TargetClass)`)
- [ ] Collaborator fakes decorated with `@fake(Protocol)` are accessible via `self.get_fake(Protocol)` or `self.<snake_case_fake_name>`
- [ ] When testing multiple singletons from the same module, each test class sets `target = TargetClass` (or imports `target_impl` and sets `target = target_impl.TargetClass`), or resolves singletons explicitly via `self.get_singleton(TargetClass)`
- [ ] Test classes never define manual `LifecycleRegistry`, never import `__initialize__`, and never call `begin_phase`, `enter_phase`, or `scope.close()` in `setUp` or `tearDown`
- [ ] Tests interact with target instances strictly through their public contracts declared in `low/<name>.pyi`; invoking uncontracted configuration methods (`configure()`, `setup()`) is prohibited
- [ ] Mutating or monkeypatching methods or attributes on live singleton instances (such as replacing methods on instances resolved from `self.sut` or `self.get_singleton(...)`) is prohibited; tests configure execution scenarios by setting up domain inputs or by declaring collaborator fakes decorated with `@fake(Protocol)`
- [ ] For standalone components without singletons, target classes are instantiated directly without lifecycle helpers
- [ ] Helper methods that operate on target singletons execute within the test's active phase scope without opening separate ephemeral scopes

## Examples

- [ ] Unit test with LifecycleTestCase and @fake collaborator:
```python
from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleTestCase, fake
from task_worker.lib.storage import StorageService
from task_worker.lib.task_worker import TaskNotifier, TaskWorkerService
from task_worker.lib.task_worker_impl import TaskWorkerServiceImpl


class TaskWorkerServiceImplTest(LifecycleTestCase):
    """Unit test for task worker service."""

    @fake(StorageService)
    class FakeStorage:
        def __init__(self) -> None:
            self.saved_tasks: list[str] = []

        def save(self, task_id: str) -> None:
            self.saved_tasks.append(task_id)

    @fake(TaskNotifier)
    class FakeNotifier:
        def __init__(self) -> None:
            self.completed: list[str] = []

        def notify_completion(self, task_id: str) -> None:
            self.completed.append(task_id)

    def test_execute_task_saves_and_notifies(self) -> None:
        """Verify task execution saves task state and notifies completion."""
        self.sut.execute_task("task-123")
        fake_storage = self.get_fake(StorageService)
        fake_notifier = self.get_fake(TaskNotifier)
        self.assertEqual(fake_storage.saved_tasks, ["task-123"])
        self.assertEqual(fake_notifier.completed, ["task-123"])


if __name__ == "__main__":
    unittest.main()

# PROHIBITED ANTI-PATTERN: Manual LifecycleRegistry, manual __initialize__, manual enter_phase
# class BadTest(unittest.TestCase):
#     def setUp(self) -> None:
#         self.registry = LifecycleRegistry()      # PROHIBITED: Inherit from LifecycleTestCase instead
#         __initialize__(self.registry)            # PROHIBITED: Never import or call __initialize__
#         self.scope = begin_phase(...)            # PROHIBITED: LifecycleTestCase handles scoping
```
