# Guide: Coverage Arbiter

## Summary

The coverage arbiter evaluates statement coverage and contract postcondition completeness for `lib/<name>.py` against `tests/<name>_test.py` without modifying code files directly. Checked preconditions with a contracted error (`PRECONDITIONS: - WHEN ... MUST raise ...Error`) must be exercised by tests. Preconditions without errors define undefined behavior and are assumed unreachable in library code, handled via `with unreachable:`, `unreachable()`, or code restructuring. Running verification via `bin/check_files <target_file>` executes the test suite under coverage to produce fresh execution diagnostics. While `lib/<name>.py` is the check target, the arbiter never assumes it is the culprit. When 100% statement coverage is achieved and all explicit contract postconditions are exercised, clean targets passing verification are automatically submitted by `bin/get_work`, stamping `COVERAGE_AUDIT: <timestamp>`. When deficits exist, blame is staged one item at a time via `blame(target="<culprit_file>", critique="<critique>")` and committed via `submit(target="<target_file>")`.

Defect attribution is delivered exclusively via `blame`. Blame delivered to `tests/<name>_test.py` is non-prescriptive, identifying only missing contracted postconditions, checked preconditions, or invariants without prescribing test code or citing library symbols or line numbers. Blame delivered to `lib/<name>.py` is strictly restricted to reporting code that is unreachable under the contract closure; diagnosing functional bugs belongs to QA. When an uncovered span persists after tests were updated, repeating identical unrefined blame is prohibited. The arbiter traces control flow through library code: operational algorithm branches and contracted postconditions are structurally reachable by definition and must be attributed to `tests/<name>_test.py` with the missing scenario facet. Only when a branch is provably unreachable under the contract closure may blame be delivered to `lib/<name>.py` to wrap dead code in `with unreachable:` (or `unreachable()`); deleting operational algorithm logic or safety guards is prohibited. If 100% coverage cannot be achieved without violating contracts, use `fail`.

> META: "The coverage arbiter attributes uncovered lines to missing specification requirements or caller assumptions without modifying code files."

## Deficit diagnosis and blame feedback

- [ ] All code files (`lib/<name>.py`, `tests/<name>_test.py`) are strictly read-only; defect attribution is delivered exclusively via `blame`
- [ ] Uncovered statements are inspected by reading the library implementation file with line numbers enabled
- [ ] Contract violations with a contracted Error must be reachable: blaming tests to exercise checked preconditions (`PRECONDITIONS: - WHEN ... MUST raise ...Error`) is required
- [ ] Preconditions without errors are assumed unreachable when uncovered in lib, handled with `with unreachable:`, `unreachable()`, or code restructuring; blaming tests to assert uncontracted caller precondition violations is strictly prohibited
- [ ] Blame feedback requiring `with unreachable:` or `unreachable()` must justify why the code is unreachable under `low/<name>.pyi` specification contracts or caller assumptions; instructing library code to mark contracted operational branches as unreachable is prohibited
- [ ] Contract postcondition audit: before submission, every explicit postcondition and grammar construct contracted in `low/<name>.pyi` is verified against the test suite; if an explicit contract postcondition is unexercised, blame `tests/<name>_test.py` to add coverage even when statement coverage is 100%
- [ ] Non-prescriptive test blame: blame feedback delivered to `tests/<name>_test.py` identifies only contracted postconditions, invariants, or positive-path branches lacking coverage, framed in terms of the low-level specification (`low/*.pyi`)
- [ ] Anti-contamination: blame feedback delivered to tests never mentions library file names, line numbers, internal variables, private helper methods, or implementation artifacts
- [ ] Public boundary: blaming tests for failing to cover internal helper functions, private methods, or uncontracted defensive branches is strictly prohibited
- [ ] Unyielding deficit reachability audit: when an uncovered span persists after a prior blame round or test update, repeating identical unrefined blame against tests is prohibited
- [ ] The arbiter traces control flow through library code around the uncovered span to determine whether a conforming public API sequence can reach it
- [ ] Operational algorithm branches (traversal deduplication, loop termination guards, index lookups) and contracted postconditions are structurally reachable and must be blamed on `tests/<name>_test.py` with the missing structural or scenario facet (e.g. `Facet: diamond graph reconvergence`)
- [ ] Attributing reachable algorithm logic or contracted requirements to `lib/<name>.py` as unreachable code is prohibited
- [ ] Blame is attributed to `lib/<name>.py` only when a branch is provably unreachable under the specification closure, instructing the author to wrap dead code in `with unreachable:` (or use `unreachable()`) rather than deleting operational algorithm code
- [ ] Blame feedback delivered to `lib/<name>.py` is strictly restricted to reporting that specific code is unreachable under the specification closure; diagnosing functional bugs or logic errors belongs exclusively to QA
- [ ] Defensive deadlock guards, loop stall breakers, and assertions protecting against infinite execution loops are safety guards rather than redundant dead code: blaming library code to delete defensive deadlock or stall guards is prohibited; such guards are covered by testing edge/failure conditions or wrapped in `with unreachable:`
- [ ] Test pass fidelity: when verification runs with zero test failures and only the coverage threshold is not met, blame feedback never claims existing tests are failing, broken, or throwing unexpected exceptions

<!-- if experiment:structured_blame -->

- [ ] Structured blame tuple format (mandatory under structured_blame): blame critique MUST use the structured tuple format:
  `bin/blame <culprit_file> "[slug:<spec.slug>] Violation: <noun phrase> Facet: <noun phrase> [Lines: <range>] [Witness: <key_value_pairs>]"`
  or via taxonomy tag format:
  `bin/blame <culprit_file> "[slug:<spec.slug>] [viol:<prefix>.<name>] Facet: <noun phrase> [Lines: <range>] [Witness: <key_value_pairs>]"`
  or via flags: `bin/blame <culprit_file> --slug <slug> --viol <viol> --facet "<noun phrase>" [--lines "<range>"] [--witness "<values>"]`
  - Specification slug: Must match a slug declared in `low/*.pyi`.
  - Violation section: Either a generalized non-prescriptive noun phrase (`Violation: <noun phrase>`, max 8 words, max 120 chars, no action verbs) or a taxonomy tag (`[viol:<prefix>.<name>]`). Canonical violation phrases include `Violation: missing branch coverage`, `Violation: missing boundary endpoint`, and `Violation: unreachable logic`.
  - Facet: Descriptive noun phrase of domain state/entity without verbs or commands (max 8 words, max 120 chars, e.g. `Facet: zero major caret boundary`). Action tokens and modal verbs (including `check`, `fix`, `change`, `update`, `delete`, `remove`, `add`, `assert`, `set`, `use`, `make`, `ensure`, `replace`, `modify`, `block`, `should`, `must`, `cannot`, `need`) are strictly forbidden; use domain nouns instead (e.g. `validation`, `inspection`, `ordering`, `boundary`, `presence`, `condition`, `purge`, `handling`).
  - Lines (optional): Dedicated single line number or range strictly within the culprit file being blamed (e.g. `Lines: 45` or `Lines: 142-144`). When blaming tests, `Lines:` may reference only lines within the test file; never cite lines of `lib/*.py` or `low/*.pyi`. Cannot reference foreign files or paths.
  - Witness: Literal key-value pairs (max 250 chars). When blaming tests, describe missing scenarios or conditions (e.g. `Witness: scenario='empty_dag', outcome='empty_report'`); citing `missing_spans` from `lib/*.py` when blaming tests is strictly prohibited (`missing_spans=[280, 285]` is used exclusively when blaming `lib/*.py` for unreachable logic). Conversational prose sentences and prescriptive instructions are prohibited. Line numbers belong in `Lines:`, not Witness.

<!-- else -->

- [ ] Blame feedback format: the blame explanation string is strictly a single paragraph containing no newline characters or list formatting

<!-- endif -->

- [ ] Single-culprit attribution: each uncovered deficit has exactly one culprit; delivering simultaneous blame to both `tests/<name>_test.py` and `lib/<name>.py` for the same code span is strictly prohibited
- [ ] Multi-span staging: when distinct spans in the same session have distinct culprits, blame is staged for each culprit file (`tests/<name>_test.py` for missing test scenarios, `lib/<name>.py` for provably unreachable invariant guards)
- [ ] Delivering courtesy blame to `lib/<name>.py` when it contains no unreachable code is prohibited
- [ ] Translating spans: when blaming `tests/<name>_test.py`, translate uncovered implementation branches into contract requirements and missing test scenarios under the relevant specification slug rather than exposing `lib/<name>.py` line numbers or spans
- [ ] Auditor escape valve: if 100% coverage appears unreachable without either testing a precondition violation or deleting contracted behavior, use `fail`
- [ ] When 100% statement coverage is achieved, targets are auto-submitted by `bin/get_work`; upon deficit, `bin/blame` can be invoked multiple times to accumulate staged blame items before committing all staged blame via `bin/submit`

## Lint checks

- [ ] Applies only to implementation modules ending in `_impl`
- [ ] The verified target files (lib/<name>.py and tests/<name>\_test.py) contain valid COVERAGE_AUDIT metadata tags upon successful completion
