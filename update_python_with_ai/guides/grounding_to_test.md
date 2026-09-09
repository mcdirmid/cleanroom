# Guide: Writing Unit Tests from Grounding Specifications

## Summary

The artifact is the test module for an implementation: `<name>_impl_test.py`, written from `grounding/<name>_impl.pyi` and its dependency closure alone — the library implementation Python file is never consulted. Tests written from the grounding specification catch implementation drift: when a test fails, the implementation is wrong, unless the test misread the grounding contract. A file that is a template is filled in. The files and specifications provided in context at session start are the complete and only source of truth required to write the test module.

The grounding specification is the only contract: tests cover its postconditions (`FRESH_REQUIREMENTS:`, `INHERITED_REQUIREMENTS:`), invariants, and expected failure signals, while dependency mocks enforce caller preconditions (`FRESH_ASSUMPTIONS:`). Tests must always satisfy all declared assumptions (`FRESH_ASSUMPTIONS:`, `INHERITED_ASSUMPTIONS:`) and never test that an assumption violation produces anything other than unexpected behavior — undefined behavior is undefined behavior, and tests never assert defined behavior for violated assumptions. When tool execution fails, tests assert the failure signal (`is_failed=True`, `is_terminated=...`) but never assert string contents or wording of error and diagnostic messages; requirements specifying that tool failure responses include error messages, diagnostics, or recovery guidance are cataloged in the untested requirements block at the bottom of the test file. Every test method contains a docstring or comment block identifying the tested Customer User Journey (CUJ) or edge case, and comments identifying which specific requirements (`# Requirement: <text>`) and invariants are tested. A comment block at the bottom of each test file lists any untested requirements from the grounding specification, with the aim of making that list as short as possible by covering every testable requirement. Singletons under test are instantiated and tested via their lifecycle scope; collaborator singletons are registered as mocks or stubs in a fresh lifecycle registry, while polymorphic types are mocked or instantiated directly. Test editing is incremental and targeted, updating or adding test methods one at a time via `update_lines` without regenerating the whole file. When calling `advance(change_summary="...")`, the summary is at most 200 characters (one short sentence).

## Module layout

- [ ] One test module per implementation specification: `grounding/widget_impl.pyi` → `widget_impl_test.py`
- [ ] A test module (`<name>_impl_test.py`) imports only its target implementation module (`<name>_impl`) and interface protocols; it must never import from foreign `*_impl` modules or import foreign `*Impl` classes
- [ ] Imports of library modules use `from lib.<module> import ...` (never prefixing the workspace directory name)
- [ ] The module uses `unittest`, ending with `if __name__ == "__main__": unittest.main()`
- [ ] Tests are grouped into `unittest.TestCase` classes by concern (success routing, failure handling, invariants, configuration)
- [ ] Untested requirements from `FRESH_REQUIREMENTS:` and `INHERITED_REQUIREMENTS:` are cataloged in a comment block at the bottom of the test file following `if __name__ == "__main__": unittest.main()`, or marked `# Untested requirements: None` when all requirements are tested
- [ ] The list of untested requirements at the bottom of the test file is kept as short as possible by providing test coverage for every verifiable requirement

## What to test

- [ ] Dataclasses constructed using the grounding specification's `__init__` constructor signature; field values, types, and defaults asserted; `Literal` discriminators asserted where the specification declares them
- [ ] Values exercised through the interface's Protocol type, never implementation-only attributes
- [ ] The implementation under test is registered into a fresh lifecycle registry via its `__initialize__` method, with collaborator singletons supplied as protocol mocks or stubs in the same or parent phase
- [ ] Every requirement under `FRESH_REQUIREMENTS:` and `INHERITED_REQUIREMENTS:` has one or more outcome tests (return value; observable state through a fresh instance; a failure that leaves previous state intact; atomicity)
- [ ] Stateful behavior asserted through public operations or a fresh instance, never through internals
- [ ] Every expected failure signal named in the contract has a test that triggers its condition and asserts the signal
- [ ] Error-message, warning, and reminder wording asserted only when the contract pins the exact string; otherwise only the signal type or event occurrence is asserted
- [ ] Invariants tested across operation sequences (a fresh instance behaves freshly; state unchanged after a failing operation; idempotency)
- [ ] Every test method documents its purpose in a docstring or leading comment identifying the tested Customer User Journey (CUJ) or edge case, checked postconditions or invariants, and confirming no caller preconditions are violated
- [ ] Comments inside each test method identify which requirements or invariants from `FRESH_REQUIREMENTS:` and `INHERITED_REQUIREMENTS:` the test asserts, citing the requirement text using `# Requirement: <text>`, without explaining test execution mechanics
- [ ] All edge cases are covered; for every covered edge case, tests exist exercising all sides of the boundary (e.g. exactly at threshold, one below, and one above; empty vs populated; matching vs non-matching)
- [ ] All stated behavioral requirements and failure signals are covered; unmandated implementation choices are never asserted
- [ ] Every requirement in `FRESH_REQUIREMENTS:` and `INHERITED_REQUIREMENTS:` is either asserted in a test method with a `# Requirement:` comment or listed in the untested requirements comment block at the bottom of the test file

## Mocks and dependencies

- [ ] Dependency interfaces are mocked from their grounding specifications (the closure) using protocol stubs, mock classes, or mock instances, never using foreign implementation classes (`*Impl`)
- [ ] Dependency interfaces are mocked from their grounding specifications, never the system under test
- [ ] Foreign collaborator singletons are registered into a test `LifecycleRegistry` as mock classes or mock instances under their interface protocol keys in the appropriate lifecycle tier (`system` or `agent_session`)
- [ ] Polymorphic dependency types (records, variants, parameter converters, verification checks) are mocked or instantiated directly and passed as operation arguments
- [ ] Each mock records calls, returns scripted results, and enforces the interface's preconditions (raises when the component under test violates a `FRESH_ASSUMPTIONS:` precondition)
- [ ] Preconditions are verified in caller tests via mock enforcement, never in callee tests (callees assume satisfied preconditions; violations are unexpected failures)
- [ ] Interaction is asserted through recorded calls: which dependency operations were called, in what order, with what arguments
- [ ] External boundaries documented in `grounding/<name>_ext.pyi` are mocked with fixtures aligned to the interface types; boundary preconditions are enforced the same way
- [ ] File fixtures exist on disk or are mocked: when a component takes a file path to read at initialization or during execution, tests supply a real fixture file (e.g. created via `tempfile.NamedTemporaryFile` with test content) or mock the file-reading boundary, never passing a non-existent dummy path string
- [ ] Mock targets patch where looked up: when patching standard library functions or submodules used by a module, patch the attribute on the module under test (`patch('lib.<module>.<symbol>')`, e.g. `patch('lib.widget_impl.os.path.isfile', ...)`), never the global stdlib module (`os.path.isfile`); global builtins target `builtins.<name>` (e.g. `builtins.open`)
- [ ] Synthetic fixtures conform strictly to spec delimiters: helper functions generating test files (markdown, CSV, JSON, proto) produce the exact delimiters and structures defined in grounding specifications or external docstrings, never bare unstructured strings
- [ ] Consistent patch scoping: when multiple patches are needed for construction or execution, nest `with patch(...):` blocks inside the test or use `setUp`/`tearDown`, ensuring every `@patch` decorator has a corresponding mock parameter on the test method

## The bias rule

- [ ] Tests verify that the implementation satisfies the grounding contract; they are never written to accommodate the implementation
- [ ] A failing test is re-read against the grounding contract first; when the contract supports the assertion, the implementation is fixed, not the test
- [ ] Assertions are never weakened to match observed behavior; tests are never written by transcribing implementation behavior
- [ ] The only legitimate test-side fixes are contract misreadings: wrong signal, wrong precondition, or testing something the contract does not require

## What not to test

- [ ] No tests for unmandated choices (ordering, algorithm choice, internal representation, log text format, message wording) unless explicitly pinned in the grounding specification
- [ ] No tests for unsatisfied preconditions (preconditions are tested in caller tests via mock enforcement, never in callee tests) or unexpected failures (unexpected failures do not need test coverage unless the specification explicitly states otherwise)
- [ ] No tests for assumption violations: tests must never test that violating a `FRESH_ASSUMPTIONS:` or `INHERITED_ASSUMPTIONS:` precondition produces anything other than unexpected behavior; undefined behavior is undefined behavior and is never tested
- [ ] When reviewing requirements, any requirement or test scenario that accidentally exercises or asserts behavior under a violated assumption is excluded from tests
- [ ] No tests asserting defined outcomes, graceful recovery, error codes, or specific exceptions for violated caller assumptions
- [ ] No tests for internal mechanisms the grounding specification does not state (private helper methods, cache internals, temporary-file steps)
- [ ] No exact error, warning, or reminder wording asserted unless the contract explicitly pins the exact string
- [ ] Tool failure response string contents: when tool execution fails, tests assert the failure signal (`is_failed=True`, `is_terminated=...`) but never assert specific string contents or English wording of error or diagnostic messages
- [ ] Requirements specifying that failed tool responses include error messages, diagnostic messages, or agent guidance are not assertable in unit tests and are cataloged as untested requirements
- [ ] No tests of high-level specs; the grounding specification is the contract

## Lint checks

- [ ] Applies only to implementation grounding specs ending in `_impl.pyi` (does not apply to interface specs, external specs ending in `_ext.pyi`, or assembly specs ending in `_asm.pyi`)
- [ ] The test module contains `if __name__ == "__main__": unittest.main()`
- [ ] The test module contains an `# Untested requirements:` comment block following `if __name__ == "__main__": unittest.main()`
- [ ] Test assertion blocks contain `# Requirement:` comments citing requirements from `FRESH_REQUIREMENTS:` or `INHERITED_REQUIREMENTS:`
- [ ] Imports of library modules use `from lib.<module> import ...` and are resolvable
- [ ] Global standard library patches (e.g. `@patch('os.path.isfile')`) are prohibited; patches target `lib.<module>.<symbol>` where looked up, or `builtins.<name>`
- [ ] Every `@patch` decorator has a corresponding mock parameter on the test method
- [ ] The test module only imports from its target implementation module (`<name>_impl`) and never imports from foreign `*_impl` modules or imports foreign `*Impl` classes
- [ ] The module under test is never mocked
- [ ] The test module defines at least one `unittest.TestCase` subclass with at least one test method starting with `test_`
- [ ] Dry-run test collection passes and discovers test methods
- [ ] The package BUILD file contains the `pyright_test` target with required dependencies

## Common pitfalls

- [ ] Tests that read the library implementation and transcribe its behavior instead of reading the grounding contract
- [ ] Weakening assertions to match observed implementation behavior
- [ ] Mocking the system under test
- [ ] Global stdlib patches (`@patch('os.path.isfile')` instead of `@patch('lib.<module>.os.path.isfile')`)
- [ ] Fixtures missing specification-defined structural delimiters (e.g. markdown heading syntax or JSON fields)
- [ ] Precondition tests in callee test suites (preconditions are tested in caller tests via mock enforcement, never in the callee itself)
- [ ] Testing behavior when an assumption is violated instead of treating assumption violation as undefined behavior
- [ ] Asserting defined error handling, graceful returns, or specific exceptions for inputs that violate contract assumptions
- [ ] Asserting string contents or wording of tool failure responses instead of treating diagnostic guidance requirements as untested requirements
- [ ] Tests for unmandated implementation choices
- [ ] Imports of foreign implementation modules or foreign `*Impl` classes (mock dependency protocols instead)
- [ ] Omitting docstrings or leading comments describing the CUJ or edge case being covered
- [ ] Omitting `# Requirement: <text>` comments on test assertion blocks
- [ ] Omitting the `# Untested requirements:` comment block at the bottom of the test file
- [ ] Leaving requirements in the untested requirements block that can be verified with unit tests
- [ ] Explaining test mechanics in comments rather than identifying what requirement or invariant is tested
- [ ] Importing foreign implementation modules to wire collaborator singletons instead of registering protocol mocks in the lifecycle registry
