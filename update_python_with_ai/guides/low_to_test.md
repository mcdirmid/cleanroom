# Guide: Converting an LLS to Tests (without reading the implementation)

## Summary

The artifact is the test module for an implementation: `<component-name>_test.py` in `tests/`, written from the implementation LLS and its dependency closure alone — the implementation Python file is never consulted. Tests written from the LLS catch implementation drift: when a test fails, the implementation is wrong, unless the test misread the LLS. A file that is a template is filled in.

The LLS is the only contract: the tests cover its postconditions, invariants, and expected failure signals, and nothing else — no internal mechanisms, no exact message wording, no unspecified ordering, no behavior outside the contract. When in doubt, do not test it. The HLS is not part of the test contract; the LLS is self-contained.

Read the implementation LLS and the transitive closure of its dependency comment: every LLS in the comment, every LLS in their comments, until no new files remain — dependency mocks implement the dependency interfaces exactly from their own LLSs. Extract the testable claims: Data Types (construction, fields, defaults, `Literal` discriminators); Config (fields, defaults, mock wiring); Behavioral Description (each bullet → outcome tests); Failure Handling (each expected failure signal → a test); Invariants (sequence tests); Non-Concerns (pinned only).

## Module layout

- [ ] One test module per implementation LLS: `specs/low/csv_inventory_impl.md` → `tests/csv_inventory_impl_test.py`
- [ ] The module uses `unittest`, ending with `if __name__ == "__main__": unittest.main()`
- [ ] Tests are grouped into classes by concern (success routing, failure handling, invariants, config)
- [ ] Write incrementally: append one test class per edit (a `replace_lines` inserting a class), never the whole file in one edit — an edit that exceeds the response limit is lost, and the file must be re-read

## What to test

- [ ] Dataclasses constructed with the LLS's fields; field values, types, and defaults asserted; `Literal` discriminators asserted where the LLS declares them
- [ ] Values exercised through the interface's Protocol type, never implementation-only attributes
- [ ] The implementation constructed with the LLS's Config; documented defaults asserted; dependency mocks wired through Config and asserted actually used
- [ ] Every Behavioral Description bullet has one or more outcome tests (return value; observable state through a fresh instance; a failure that leaves the previous state intact; atomicity)
- [ ] Stateful behavior asserted through the public operations or a fresh instance, never through internals
- [ ] Every expected failure signal named in the LLS has a test that triggers its condition and asserts the signal
- [ ] Error-message wording asserted only when the LLS pins the string; otherwise only the signal type is asserted
- [ ] Invariants tested across operation sequences (a fresh instance behaves freshly; state unchanged after a failing operation; resolved-path effects)
- [ ] Pinned non-concerns asserted; open non-concerns never tested

## Mocks

- [ ] Dependency interfaces are mocked from their LLSs (the closure), never the system under test
- [ ] Each mock records calls, returns scripted results, and enforces the interface's preconditions (raises when the component under test violates one)
- [ ] Preconditions are enforced by the mocks, never tested directly (precondition violations are unexpected failures)
- [ ] Interaction is asserted through recorded calls: which dependency operations were called, in what order, with what arguments
- [ ] External boundaries are mocked with fixtures aligned to the interface types the LLS declares; boundary preconditions enforced the same way

## The bias rule

- [ ] Tests verify that the implementation satisfies the LLS; they are never written to accommodate the implementation
- [ ] A failing test is re-read against the LLS first; when the LLS supports the assertion, the implementation is fixed, not the test
- [ ] Assertions are never weakened to match observed behavior; tests are never written by transcribing implementation behavior
- [ ] The only legitimate test-side fixes are LLS misreadings: wrong signal, wrong precondition, or testing something the LLS does not require

## What not to test

- [ ] No tests for open non-concerns (ordering, algorithm choice, representation, log/text format, message wording, chunk boundaries)
- [ ] No tests for unexpected failures not listed as concerns (precondition violations, filesystem errors, state corruption)
- [ ] No tests for internal mechanisms the LLS does not state (cache internals, temporary-file steps) unless pinned in a Non-Concern
- [ ] No exact error-message wording unless the LLS pins the string for testing
- [ ] No tests of the HLS; the LLS is the contract

## Common pitfalls

- [ ] No tests that read the implementation and transcribe its behavior
- [ ] No weakened assertions to match observed behavior
- [ ] No mocks of the system under test
- [ ] No precondition tests (preconditions are enforced by the mocks, not tested)
- [ ] No open-non-concern tests (pin the aspect in the LLS first, or drop the assertion)
- [ ] No imports outside the LLS closure (the test imports only within its spec's dependency closure)
