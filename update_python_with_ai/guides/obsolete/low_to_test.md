# Guide: Converting an LLS to Tests (without reading the implementation)

## Summary

The artifact is the test module for an implementation: `<component-name>_test.py`, written from the implementation LLS and its dependency closure alone — the implementation Python file is never consulted. Tests written from the LLS catch implementation drift: when a test fails, the implementation is wrong, unless the test misread the LLS. A file that is a template is filled in.

The LLS is the only contract: tests cover its postconditions, invariants, and expected failure signals, extracting claims from Data Types, Config, Behavioral Description, Failure Handling, and Invariants. Test editing is incremental and targeted, updating or adding test methods one at a time via `update_lines` without regenerating the whole file.

## Module layout

- [ ] One test module per implementation LLS: `low/csv_inventory_impl.md` → `csv_inventory_impl_test.py`
- [ ] A test module (`<name>_impl_test.py`) imports only its target implementation module (`<name>_impl`) and interface protocols; it must never import from foreign `*_impl` modules or import foreign `*Impl` classes
- [ ] Imports of library modules use `from lib.<module> import ...` (never prefixing the workspace directory name)
- [ ] The module uses `unittest`, ending with `if __name__ == "__main__": unittest.main()`
- [ ] Tests are grouped into classes by concern (success routing, failure handling, invariants, config)

## What to test

- [ ] Dataclasses constructed with the LLS's fields; field values, types, and defaults asserted; `Literal` discriminators asserted where the LLS declares them
- [ ] Values exercised through the interface's Protocol type, never implementation-only attributes
- [ ] The implementation constructed with the LLS's Config; documented defaults asserted; dependency mocks wired through Config and asserted actually used
- [ ] Every Behavioral Description bullet has one or more outcome tests (return value; observable state through a fresh instance; a failure that leaves the previous state intact; atomicity)
- [ ] Stateful behavior asserted through the public operations or a fresh instance, never through internals
- [ ] Every expected failure signal named in the LLS has a test that triggers its condition and asserts the signal
- [ ] Error-message, warning, and reminder wording asserted only when the LLS pins the exact string; otherwise only the signal type or event occurrence is asserted
- [ ] Invariants tested across operation sequences (a fresh instance behaves freshly; state unchanged after a failing operation; resolved-path effects)
- [ ] Every test method documents its purpose in a docstring stating the tested edge case or CUJ, checked postconditions or invariants, and confirming no caller preconditions are violated as tests
- [ ] All edge cases are covered; for every covered edge case, tests exist exercising all sides of the boundary (e.g. exactly at threshold, one below, and one above; empty vs populated; matching vs non-matching)
- [ ] All stated behavioral requirements and failure signals are covered; unmandated implementation choices are never asserted

## Mocks

- [ ] Dependency interfaces are mocked from their LLSs (the closure) using protocol stubs or mock classes, never using foreign implementation classes (`*Impl`)
- [ ] Dependency interfaces are mocked from their LLSs (the closure), never the system under test
- [ ] Each mock records calls, returns scripted results, and enforces the interface's preconditions (raises when the component under test violates one)
- [ ] Preconditions are verified in caller tests via mock enforcement, never in callee tests (callees assume satisfied preconditions; violations are unexpected failures)
- [ ] Interaction is asserted through recorded calls: which dependency operations were called, in what order, with what arguments
- [ ] External boundaries are mocked with fixtures aligned to the interface types the LLS declares; boundary preconditions enforced the same way
- [ ] File fixtures exist on disk or are mocked: when a component takes a file path to read at initialization or during execution, tests must supply a real fixture file (e.g. created via `tempfile.NamedTemporaryFile` with test content) or mock the file-reading boundary, never passing a non-existent dummy path string
- [ ] Mock targets patch where looked up: when patching standard library functions or submodules used by a module, patch the attribute on the module under test (`patch('lib.<module>.<symbol>')`, e.g. `patch('lib.guide_delivery_impl.os.path.isfile', ...)`), never the global stdlib module (`os.path.isfile`). Global builtins target `builtins.<name>` (e.g. `builtins.open`)
- [ ] Synthetic fixtures conform strictly to spec delimiters: helper functions generating test files (guides, markdown, CSV, JSON) must produce the exact delimiters and heading structures the LLS defines (e.g. `## <heading>` for guide step sections, OpenAI tool call schema format), never bare unstructured strings
- [ ] Consistent patch scoping: when multiple patches are needed for construction/execution, nest `with patch(...):` blocks inside the test or use `setUp`/`tearDown`, ensuring every `@patch` decorator has a corresponding mock parameter on the test method

## The bias rule

- [ ] Tests verify that the implementation satisfies the LLS; they are never written to accommodate the implementation
- [ ] A failing test is re-read against the LLS first; when the LLS supports the assertion, the implementation is fixed, not the test
- [ ] Assertions are never weakened to match observed behavior; tests are never written by transcribing implementation behavior
- [ ] The only legitimate test-side fixes are LLS misreadings: wrong signal, wrong precondition, or testing something the LLS does not require

## What not to test

- [ ] No tests for unmandated choices (ordering, algorithm choice, representation, log/text format, message wording, chunk boundaries) unless explicitly pinned in the LLS
- [ ] No tests for unsatisfied preconditions (preconditions are tested in caller tests via mock enforcement, never in callee tests) or unexpected failures (every exception is an unexpected failure; unexpected failures do not need to be covered in tests unless the specification explicitly states otherwise)
- [ ] No tests for internal mechanisms the LLS does not state (cache internals, temporary-file steps)
- [ ] No exact error, warning, or reminder wording asserted unless the LLS explicitly pins the exact string
- [ ] No assertions on unmandated path representations, bare unextended identifier/target fragments, or formats outside the LLS contract
- [ ] No tests of the HLS; the LLS is the contract

## Lint checks

- [ ] Applies only to low-level implementation specs ending in `_impl.md` (does not apply to interface specs or assembly specs ending in `_asm.md`)
- [ ] The test module ends with `if __name__ == "__main__": unittest.main()`
- [ ] Imports of library modules use `from lib.<module> import ...` and are resolvable
- [ ] Global standard library patches (e.g. `@patch('os.path.isfile')`) are prohibited; patches target `lib.<module>.<symbol>` where looked up, or `builtins.<name>`
- [ ] Every `@patch` decorator has a corresponding mock parameter on the test method
- [ ] The test module only imports from its target implementation module (`<name>_impl`) and never imports from foreign `*_impl` modules or imports foreign `*Impl` classes
- [ ] The module under test is never mocked
- [ ] The test module defines at least one `unittest.TestCase` subclass with at least one test method starting with `test_`
- [ ] Dry-run test collection passes and discovers test methods
- [ ] The package BUILD file contains the `pyright_test` target with required dependencies

## Common pitfalls

- [ ] No tests that read the implementation and transcribe its behavior
- [ ] No weakened assertions to match observed behavior
- [ ] No mocks of the system under test
- [ ] No global stdlib patches (e.g. `@patch('os.path.isfile')` instead of `@patch('lib.<module>.os.path.isfile')`)
- [ ] No fixtures missing spec-defined structural delimiters (e.g. markdown heading syntax)
- [ ] No assertions on unmandated path fragments or unextended labels not specified by the LLS
- [ ] No precondition tests in callee suites (preconditions are tested in caller tests via mock enforcement, never in the callee itself)
- [ ] No tests for unmandated implementation choices (pin the aspect in the LLS first, or drop the assertion)
- [ ] No imports outside the LLS closure (the test imports only within its spec's dependency closure)
- [ ] No imports of foreign implementation modules or `*Impl` classes (mock dependency protocols instead)
