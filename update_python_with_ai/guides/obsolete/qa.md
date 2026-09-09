# Guide: QA Arbiter

## Summary

The artifact is the QA arbiter log `<name>_qa.log` and the blame decisions delivered to the lib and test nodes. All code files (both lib and test files) are strictly read-only for QA; QA never edits `.py` files and modifies only `<name>_qa.log`, delivering fixes exclusively via `blame()`. Failure diagnosis and analysis is concise (under 200 words); the arbiter pinpoints the failing assertion and LLS requirement directly and delivers `blame()` immediately without long speculative monologues. Each file change summary in `advance(changes=[...])` is at most 200 characters (one short sentence).

The log documents the problems the run's tests reveal, and it is empty when the tests pass (a log still holding problems when the tests pass is emptied before the run succeeds). The log is the persistent record of the problems found so far: when a problem is encountered, the log is read first, so a problem already recorded is not re-reported and only newly discovered problems are appended — the record prevents a bad feedback loop. Blame is decided against the LLS closure, never the code: when a test fails, crashes, or fails to load/import, blame is assigned to the artifact at fault based on the failure's origin: the lib module is at fault when the error arises from the library implementation module (e.g. syntax or import error in the library file, a runtime exception, or violating an LLS-stated behavior); the test module is at fault when the error arises from the test module (e.g. syntax or import error in the test file itself, asserting something the LLS does not require, a wrong failure signal, a wrong precondition, or asserting open non-concerns). Feedback is written in the LLS's language — LLS term names, postcondition statements, failure-signal names — never the lib or test code's identifiers. Blame is delivered to the artifact at fault for the failure only; an artifact the LLS supports is never blamed. When no artifact is at fault — the failure traces to neither the lib module nor the test module — no blame is delivered and the run fails instead.

## Diagnosing Failures

- [ ] The log `<name>_qa.log` holds only active, unresolved problems in the current cycle: when problems from previous runs are resolved by code changes, their entries are removed from `<name>_qa.log`
- [ ] When all tests pass, the QA log is completely empty (0 bytes, all lines including headers deleted) before calling `advance`
- [ ] When an assertion fails, the asserted behavior is verified against the LLS specification first: if the test asserts unmandated behavior, partial/unextended string representations, or formats not explicitly specified by the LLS, blame is assigned to the test module rather than the library module
- [ ] Blame feedback is relatively high-level and grounded in specification concepts: it states the failing test, the root cause in terms of the LLS contract or type definition that was misunderstood, and the expected behavior; the receiving node resolves the issue from its own specification
- [ ] No code-level fixes, exact Python syntax patches, variable reassignments, or code snippets in blame feedback; test nodes are not contaminated with library implementation details
- [ ] When all tests in a test class fail uniformly with missing data or empty state right after construction, the test's `setUp()` or fixture helper functions are inspected first before diagnosing deep implementation logic
- [ ] Mock target scopes: standard library mocks are patched on `lib.<module_under_test>.<symbol>`, not globally on stdlib modules
- [ ] Test fixture formatting conforms to LLS requirements: test fixture generators produce the exact structural delimiters (headings, fields) required by the contract

