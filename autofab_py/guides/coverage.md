# Guide: Coverage Arbiter

## Summary

The coverage arbiter evaluates statement coverage and contract postcondition completeness for a unit's library implementation (`lib/<name>.py`) against its test suite (`tests/<name>_test.py`) without modifying code files directly. Checked preconditions that have a contracted Error with them (`PRECONDITIONS: - WHEN ... MUST raise ...Error`) must be reachable, otherwise there is no point in throwing an error; checked preconditions, contracted positive-path postconditions, invariants, and success branches belong to tests. Other contract violations without contracted errors (preconditions without an error in `PRECONDITIONS:`) define undefined behavior and are assumed unreachable when they appear as uncovered lines in lib, handled with an unreachable call, `# pragma: no cover (assumption: <reason>)`, or by restructuring code. Running verification executes the test suite under coverage via `bin/check_files <target_file>` to produce fresh execution diagnostics and statement coverage reports. While `lib/<name>.py` is the target presented to `bin/check_files`, verification evaluates both the library and companion test suites; the arbiter must never assume `lib/<name>.py` is the culprit simply because it is the check target. When 100% statement coverage is achieved and all explicit contract postconditions are exercised, clean targets passing verification are automatically submitted by `bin/get_work`, stamping `COVERAGE_AUDIT: <timestamp>`. When deficits exist, the arbiter stages blame one item at a time via `blame(target="<culprit_file>", critique="<critique>")`, then commits blame and concludes the target via `submit(target="<target_file>")`. Manual `submit` in auditor roles strictly requires preceding staged blame.

Defect attribution is delivered exclusively via `blame`, formatted as a single paragraph without newlines in terms of the low-level specification. Line numbers can only reference the file being blamed. Blame delivered to `tests/<name>_test.py` is non-prescriptive, identifying only missing contracted specification postconditions, checked preconditions, or invariants without prescribing test code or mentioning internal symbols. Blame delivered to `lib/<name>.py` is strictly restricted to reporting that code is unreachable under the contract; diagnosing functional bugs belongs to QA. When an uncovered span persists after tests were updated, repeating identical unrefined blame against tests is prohibited; the arbiter traces control flow to determine whether the span is reachable through a public API sequence (e.g. constructing multi-node topologies, diamond dependencies, or multi-step invocations) or genuinely unreachable under contracts. If reachable, the arbiter refines blame to tests with the specific missing scenario facet; attributing operational algorithm branches or contracted specifications to `lib/<name>.py` is prohibited. Only when a branch is provably unreachable under the contract closure does the arbiter attribute blame to `lib/<name>.py` to annotate with `# pragma: no cover (assumption: <reason>)`; deleting operational algorithm logic or safety guards is prohibited. If 100% coverage cannot be achieved without violating contracts, use `fail`.

> META: "The coverage arbiter attributes uncovered lines to missing specification requirements or caller assumptions without modifying code files."

## Deficit diagnosis and blame feedback

- [ ] All code files (`lib/<name>.py`, `tests/<name>_test.py`) are strictly read-only; defect attribution is delivered exclusively via the `blame` tool
- [ ] Uncovered statements are inspected by reading the library implementation file with line numbers enabled
- [ ] Contract violations with a contracted Error must be reachable: blaming tests to exercise checked preconditions (`PRECONDITIONS: - WHEN ... MUST raise ...Error`) is required
- [ ] Preconditions without errors are assumed unreachable when uncovered in lib, handled with an unreachable call, `# pragma: no cover (assumption: <reason>)`, or code restructuring; blaming tests to assert uncontracted caller precondition violations is strictly prohibited
- [ ] Blame feedback requiring `# pragma: no cover` must justify why the code is unreachable under `low/<name>.pyi` specification contracts or caller assumptions; instructing library code to pragma contracted operational branches is prohibited
- [ ] Contract postcondition audit: before submission, every explicit postcondition and grammar construct contracted in `low/<name>.pyi` is verified against the test suite; if an explicit contract postcondition is unexercised, blame `tests/<name>_test.py` to add coverage even when statement coverage is 100%
- [ ] Blame feedback delivered to `tests/<name>_test.py` is strictly non-prescriptive: it identifies only contracted postconditions, invariants, or positive-path branches lacking coverage, framed in terms of the low-level specification (`low/*.pyi`)
- [ ] Anti-contamination: blame feedback delivered to tests never mentions library file names, line numbers, internal variables, private helper methods, or implementation artifacts
- [ ] Public boundary: blaming tests for failing to cover internal helper functions, private methods, or uncontracted defensive branches is strictly prohibited
- [ ] Unyielding deficit reachability audit: when an uncovered span persists after a prior blame round or after tests were updated, repeating identical unrefined blame against the test module is prohibited; the arbiter traces control flow through the library implementation code (`lib/<name>.py`) around the uncovered span, evaluating whether a conforming public API call sequence (such as constructing reconvergent diamond topologies, multi-step lifecycle sequences, or error retry configurations) can reach the span; operational algorithm branches (traversal deduplication, loop termination guards, data structure index lookups) and contracted specification postconditions are structurally reachable by definition and must strictly be attributed to `tests/<name>_test.py` with the missing structural or scenario facet (e.g. `Facet: diamond graph reconvergence`); attributing reachable algorithm logic or contracted requirements to `lib/<name>.py` as unreachable code is prohibited; blame is attributed to `lib/<name>.py` only when a branch is provably unreachable under the specification closure, instructing the author to annotate with `# pragma: no cover (assumption: <reason>)` rather than deleting operational algorithm code
- [ ] Blame feedback delivered to `lib/<name>.py` is strictly restricted to reporting that specific code is unreachable under the specification closure, instructing the library author to prune dead code or annotate with `# pragma: no cover (assumption: <reason>)`
- [ ] Functional defect prohibition: blame feedback delivered to the library module never diagnoses functional bugs, contract deviations, or algorithmic logic errors (functional defect arbitration belongs exclusively to QA)
- [ ] Defensive deadlock guards, loop stall breakers, and assertions protecting against infinite execution loops are safety guards rather than redundant dead code: blaming library code to delete defensive deadlock or stall guards is prohibited; such guards are covered by testing edge/failure conditions or annotated with `# pragma: no cover (assumption: <reason>)`
- [ ] Test pass fidelity: when verification runs with zero test failures and only the coverage threshold is not met, blame feedback never claims existing tests are failing, broken, or throwing unexpected exceptions; feedback strictly identifies uncovered contracts, branches, and missing scenario cases

<!-- if experiment:structured_blame -->

- [ ] Structured blame tuple format (mandatory under structured_blame): blame critique MUST use the structured tuple format:
  `bin/blame <culprit_file> "[slug:<spec.slug>] Violation: <noun phrase> Facet: <noun phrase> [Lines: <range>] [Witness: <key_value_pairs>]"`
  or via taxonomy tag format:
  `bin/blame <culprit_file> "[slug:<spec.slug>] [viol:<prefix>.<name>] Facet: <noun phrase> [Lines: <range>] [Witness: <key_value_pairs>]"`
  or via flags: `bin/blame <culprit_file> --slug <slug> --viol <viol> --facet "<noun phrase>" [--lines "<range>"] [--witness "<values>"]`
  - Specification slug: Must match a slug declared in `low/*.pyi`.
  - Violation section: Either a generalized non-prescriptive noun phrase (`Violation: <noun phrase>`, max 8 words, max 60 chars, no action verbs) or a taxonomy tag (`[viol:<prefix>.<name>]`). Canonical violation phrases include `Violation: missing branch coverage`, `Violation: missing boundary endpoint`, and `Violation: unreachable logic`.
  - Facet: Descriptive noun phrase of domain state/entity without verbs or commands (max 8 words, max 60 chars, e.g. `Facet: zero major caret boundary`).
  - Lines (optional): Dedicated single line number or range strictly within the culprit file being blamed (e.g. `Lines: 45` or `Lines: 142-144`). Cannot reference foreign files or paths.
  - Witness: Literal key-value pairs (max 200 chars, e.g. `Witness: missing_spans=[280, 285]`). Conversational prose sentences and prescriptive instructions are prohibited. Line numbers belong in `Lines:`, not Witness.

<!-- else -->

- [ ] Blame feedback format: the blame explanation string is strictly a single paragraph containing no newline characters or list formatting

<!-- endif -->

- [ ] Single-culprit attribution and target resolution: each uncovered deficit has exactly one culprit; delivering simultaneous blame to both `tests/<name>_test.py` and `lib/<name>.py` for the same code span is strictly prohibited; when different spans in the same session have distinct culprits, blame is staged for each culprit file (`tests/<name>_test.py` for missing test scenarios, `lib/<name>.py` for provably unreachable invariant guards); delivering courtesy blame to `lib/<name>.py` when it contains no unreachable code is prohibited
- [ ] Auditor escape valve: if 100% coverage appears unreachable without either testing a precondition violation or deleting contracted behavior, use `fail`
- [ ] When 100% statement coverage is achieved, targets are auto-submitted by `bin/get_work`; upon deficit, blame is staged one item at a time via `blame` and committed via `submit`

## Lint checks

- [ ] Applies only to implementation modules ending in `_impl`
- [ ] The verified target files (lib/<name>.py and tests/<name>\_test.py) contain valid COVERAGE_AUDIT metadata tags upon successful completion
