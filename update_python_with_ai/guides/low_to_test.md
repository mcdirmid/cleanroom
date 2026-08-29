# Guide: Converting an LLS to Tests (without reading the implementation)

## Summary

The artifact is the test module for an implementation: `<component-name>_test.py` in `tests/`, written from the implementation LLS and its dependency closure alone — the implementation Python file is never consulted. Tests written from the LLS catch implementation drift: when a test fails, the implementation is wrong, unless the test misread the LLS. A file that is a template is filled in.

The LLS is the only contract: the tests cover its postconditions, invariants, and expected failure signals, and nothing else — no internal mechanisms, no exact message wording, no unspecified ordering, no behavior outside the contract. When in doubt, do not test it. The HLS is not part of the test contract; the LLS is self-contained.

Read the implementation LLS and the transitive closure of its dependency comment: every LLS in the comment, every LLS in their comments, until no new files remain — dependency mocks implement the dependency interfaces exactly from their own LLSs. Extract the testable claims: Data Types (construction, fields, defaults, `Literal` discriminators); Config (fields, defaults, mock wiring); Behavioral Description (each bullet → outcome tests); Failure Handling (each expected failure signal → a test); Invariants (sequence tests); Non-Concerns (pinned only).

This guide does not apply to assembly specs (`<name>_asm.md`): an assembly performs no functionality beyond configuration and assembly of other modules, so it has no test module (per high_level_spec.md, an assembly is never tested).

## Module layout

- [ ] One test module per implementation LLS: `specs/low/csv_inventory_impl.md` → `tests/csv_inventory_impl_test.py`
- [ ] Imports of library modules use `from lib.<module> import ...` (never prefixing the workspace directory name)
- [ ] The module uses `unittest`, ending with `if __name__ == "__main__": unittest.main()`
- [ ] Tests are grouped into classes by concern (success routing, failure handling, invariants, config)
- [ ] Write incrementally and make targeted edits: append one test class per edit (using `update_lines` to insert classes), and use `update_lines` to fix or update individual test methods; never rewrite or regenerate the whole file in one edit (which risks truncation and wastes tokens)
- [ ] The test node has write access only to its test file (`tests/<name>_test.py`); library implementation files (`lib/<name>.py`) are strictly read-only and never modified by the test node
- [ ] Each file change summary in `advance(changes=[...])` is at most 200 characters (one short sentence)

## What to test

- [ ] Dataclasses constructed with the LLS's fields; field values, types, and defaults asserted; `Literal` discriminators asserted where the LLS declares them
- [ ] Values exercised through the interface's Protocol type, never implementation-only attributes
- [ ] The implementation constructed with the LLS's Config; documented defaults asserted; dependency mocks wired through Config and asserted actually used
- [ ] Every Behavioral Description bullet has one or more outcome tests (return value; observable state through a fresh instance; a failure that leaves the previous state intact; atomicity)
- [ ] Stateful behavior asserted through the public operations or a fresh instance, never through internals
- [ ] Every expected failure signal named in the LLS has a test that triggers its condition and asserts the signal
- [ ] Error-message, warning, and reminder wording asserted only when the LLS pins the string in Non-Concerns; otherwise only the signal type or event occurrence is asserted
- [ ] Invariants tested across operation sequences (a fresh instance behaves freshly; state unchanged after a failing operation; resolved-path effects)
- [ ] Pinned non-concerns asserted; open non-concerns never tested

## Mocks

- [ ] Dependency interfaces are mocked from their LLSs (the closure), never the system under test
- [ ] Each mock records calls, returns scripted results, and enforces the interface's preconditions (raises when the component under test violates one)
- [ ] Preconditions are enforced by the mocks, never tested directly (precondition violations are unexpected failures)
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

- [ ] No tests for open non-concerns (ordering, algorithm choice, representation, log/text format, message wording, chunk boundaries)
- [ ] No tests for unexpected failures not listed as concerns (precondition violations, filesystem errors, state corruption)
- [ ] No tests for internal mechanisms the LLS does not state (cache internals, temporary-file steps) unless pinned in a Non-Concern
- [ ] No exact error, warning, or reminder wording asserted unless the LLS explicitly pins the string in Non-Concerns
- [ ] No assertions on unmandated path representations, bare unextended identifier/target fragments, or formats outside the LLS contract
- [ ] No tests of the HLS; the LLS is the contract

## Common pitfalls

- [ ] No tests that read the implementation and transcribe its behavior
- [ ] No weakened assertions to match observed behavior
- [ ] No mocks of the system under test
- [ ] No global stdlib patches (e.g. `@patch('os.path.isfile')` instead of `@patch('lib.<module>.os.path.isfile')`)
- [ ] No fixtures missing spec-defined structural delimiters (e.g. markdown heading syntax)
- [ ] No assertions on unmandated path fragments or unextended labels not specified by the LLS
- [ ] No precondition tests (preconditions are enforced by the mocks, not tested)
- [ ] No open-non-concern tests (pin the aspect in the LLS first, or drop the assertion)
- [ ] No imports outside the LLS closure (the test imports only within its spec's dependency closure)
