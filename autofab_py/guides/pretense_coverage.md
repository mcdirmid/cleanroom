# Guide: Pretense Coverage Arbiter

## Summary

The pretense coverage arbiter evaluates statement coverage and contract postcondition completeness for `lib/<name>.py` (or `lib/<name>_impl.py`) against companion Pretense test suites (`pretense/<name>_pretense.py` or `pretense/<name>_impl_pretense.py`) without modifying code files directly. Pure interface modules are excluded. Fuzz testing never explores contract violations. In fixed scenario tests establishing statement coverage, checked preconditions with a contracted Error (`PRECONDITIONS: - WHEN ... MUST raise ...Error`) must be exercised via transitions ending in a contract violation (`self.checked.violating(ExpectedError).<method>(...)`). Preconditions without errors define undefined behavior and are assumed unreachable in library code, handled via `with unreachable:`, `unreachable()`, or code restructuring. Under `--no-fuzz --cov`, coverage is measured strictly across deterministic scenario test methods in the implementation Pretense test file; attributing deficits to upstream interface state machines is prohibited. Running verification via `bin/check_files <target_file>` produces fresh diagnostics. While `lib/<name>.py` is the check target, the arbiter never assumes the library is the culprit. When 100% statement coverage is achieved and all explicit contract postconditions are exercised, clean targets passing verification are automatically submitted by `bin/get_work`, stamping `PRETENSE_COVERAGE_AUDIT: <timestamp>`. When deficits exist, blame is staged via `blame(target="<culprit_file>", critique="<critique>")` and committed via `submit(target="<target_file>")`.

Defect attribution is delivered exclusively via `blame`. Blame delivered to pretense is non-prescriptive, identifying only missing contracted postconditions, checked preconditions, or invariants without prescribing test code or citing library symbols or line numbers. Blame delivered to library code is strictly restricted to reporting code that is unreachable under the contract closure; diagnosing functional bugs belongs to Pretense QA. When an uncovered span persists after tests were updated, repeating identical unrefined blame is prohibited. The arbiter traces control flow through library code: operational algorithm branches and contracted postconditions are structurally reachable by definition and must be blamed on the pretense module with the missing scenario facet. Only when a branch is provably unreachable under the contract closure may blame be delivered to library code to wrap dead code in `with unreachable:` (or `unreachable()`); deleting operational algorithm logic or safety guards is prohibited. If 100% coverage cannot be achieved without violating contracts, use `fail`.

> META: "The pretense coverage arbiter attributes uncovered lines to missing specification requirements or caller assumptions without modifying code files directly."

## Deficit diagnosis and blame feedback

- [ ] All code files (`lib/*.py`, `pretense/*.py`) are strictly read-only; defect attribution is delivered exclusively via `blame`
- [ ] Uncovered statements are inspected by reading the library implementation file with line numbers enabled
- [ ] Fuzz testing never explores contract violations; checked preconditions with a contracted Error must be reachable in fixed scenario tests: blaming pretense modules to cover unexercised contracted error branches via scenario test execution using `self.checked.violating(ExpectedError)` is required; blame describes deficits as unexercised scenarios or error branches (e.g. `Violation: unexercised precondition error`), never as `unchecked precondition`
- [ ] Preconditions without errors are assumed unreachable when uncovered in lib, handled with `with unreachable:`, `unreachable()`, or code restructuring; blaming pretense modules to assert uncontracted caller precondition violations is strictly prohibited
- [ ] Blame feedback requiring `with unreachable:` or `unreachable()` must justify why the code is unreachable under `low/<name>.pyi` specification contracts or caller assumptions; instructing library code to mark contracted operational branches as unreachable is prohibited
- [ ] Contract postcondition audit: before submission, every explicit postcondition and grammar construct contracted in `low/<name>.pyi` is verified against the pretense scenario suite; if an explicit contract postcondition is unexercised, blame `pretense/<name>_impl_pretense.py` to add coverage even when statement coverage is 100%
- [ ] Non-prescriptive pretense blame: blame feedback delivered to the pretense module identifies only contracted postconditions, invariants, or positive-path branches lacking coverage, framed in terms of the low-level specification (`low/*.pyi`)
- [ ] Test scenario attribution: blame delivered to a pretense module is strictly an instruction to add scenario test execution in `Test<Target>ImplReal`, never an instruction to add `require()` or `requires()` precondition guards to the state machine or adapter
- [ ] Anti-contamination: blame feedback delivered to pretense never mentions library file names, line numbers, internal variables, private helper methods, or implementation artifacts
- [ ] Public boundary: blaming tests for failing to cover internal helper functions, private methods, or uncontracted defensive branches is strictly prohibited
- [ ] Implementation coverage attribution: under `--no-fuzz --cov`, coverage is measured strictly across deterministic scenario test methods in the implementation Pretense test file; attributing implementation coverage deficits to upstream interface state machines (`pretense/<iface>_pretense.py`) is prohibited
- [ ] Target disparity rule: while `lib/<name>.py` is the verification target presented to `check_files`, verification executes the companion pretense test suite under coverage; defaulting to blaming `lib/<name>.py` for deficits without analyzing reachability is strictly prohibited
- [ ] Unyielding deficit reachability audit: when an uncovered span persists after a prior blame round or test update, repeating identical unrefined blame against tests is prohibited
- [ ] The arbiter traces control flow through library code around the uncovered span to determine whether a conforming public API sequence can reach it
- [ ] Operational algorithm branches (traversal deduplication, loop termination guards, index lookups) and contracted postconditions are structurally reachable and must be blamed on the pretense module with the missing structural or scenario facet (e.g. `Facet: diamond graph reconvergence`)
- [ ] Attributing reachable algorithm logic or contracted requirements to the library module as unreachable code is prohibited
- [ ] Blame is attributed to the library module only when a branch is provably unreachable under the specification closure, instructing the author to wrap dead code in `with unreachable:` (or use `unreachable()`) rather than deleting operational algorithm code
- [ ] Blame feedback delivered to the library module is strictly restricted to reporting that specific code is unreachable under the specification closure; diagnosing functional bugs or logic errors belongs exclusively to Pretense QA
- [ ] Defensive deadlock guards, loop stall breakers, and assertions protecting against infinite execution loops are safety guards rather than redundant dead code: blaming library code to delete defensive deadlock or stall guards is prohibited; such guards are covered by testing edge/failure conditions or wrapped in `with unreachable:`
- [ ] Test pass fidelity: when verification runs with zero test failures and only the coverage threshold is not met, blame feedback never claims existing tests are failing, broken, or throwing unexpected exceptions; feedback strictly identifies uncovered contracts, branches, and missing scenario cases

<!-- if experiment:structured_blame -->

- [ ] Structured blame tuple format (mandatory under structured_blame): blame critique MUST use the structured tuple format:
  `bin/blame <culprit_file> "[slug:<spec.slug>] Violation: <noun phrase> Facet: <noun phrase> Lines: <range> Witness: <key_value_pairs>"`
  or via taxonomy tag format:
  `bin/blame <culprit_file> "[slug:<spec.slug>] [viol:<prefix>.<name>] Facet: <noun phrase> Lines: <range> Witness: <key_value_pairs>"`
  or via CLI flags: `bin/blame <culprit_file> --slug <slug> --viol <viol> --facet "<noun phrase>" [--lines "<range>"] [--witness "<values>"]`
  - Specification slug: Must match a slug declared in `low/*.pyi`.
  - Violation section: Either a generalized non-prescriptive noun phrase (`Violation: <noun phrase>`, max 8 words, max 60 chars, no action verbs) or a taxonomy tag (`[viol:<prefix>.<name>]`). Canonical violation phrases include `Violation: unexercised precondition error`, `Violation: unexercised postcondition`, `Violation: state transition starvation`, `Violation: collaborator seeding deficit`, and `Violation: unreachable logic`.
  - Facet: Descriptive noun phrase of domain state/entity without verbs or commands (max 8 words, max 60 chars, e.g. `Facet: transitive constraint rollback on backtrack`). Action tokens and modal verbs (including `check`, `fix`, `change`, `update`, `delete`, `remove`, `add`, `assert`, `set`, `use`, `make`, `ensure`, `replace`, `modify`, `block`, `should`, `must`, `cannot`, `need`) are strictly forbidden; use domain nouns instead (e.g. `validation`, `inspection`, `ordering`, `boundary`, `presence`, `condition`, `purge`, `handling`).
  - Lines (optional): Line number or range in culprit file (e.g. `Lines: 42` or `Lines: 42-50`, also accepts bracketed `[Lines: 42]`). Cannot reference foreign files or paths.
  - Witness: Literal key-value pairs (max 200 chars, e.g. `Witness: unreached_rule='rule_undo_candidate_assignment'`, also accepts bracketed `[Witness: ...]`). Conversational prose and prescriptive instructions are prohibited. Line numbers belong in `Lines:`, not Witness.

<!-- else -->

- [ ] Blame feedback format: the blame explanation string is strictly a single paragraph containing no newline characters or list formatting

<!-- endif -->

- [ ] Single-culprit attribution: each uncovered deficit has exactly one culprit; delivering simultaneous blame to both the pretense module and library module for the same code span is strictly prohibited
- [ ] Multi-span staging: when distinct spans in the same session have distinct culprits, blame is staged for each culprit file (pretense module for missing test scenarios, library module for provably unreachable invariant guards)
- [ ] Delivering courtesy blame to the library when it contains no unreachable code is prohibited
- [ ] Auditor escape valve: if 100% coverage appears unreachable without either testing a precondition violation or deleting contracted behavior, use `fail`
- [ ] When 100% statement coverage is achieved, targets are auto-submitted by `bin/get_work`; upon deficit, blame is staged one item at a time via `blame` and committed via `submit`

## Lint checks

- [ ] Applies to implementation modules with a corresponding pretense test suite (excluding pure interface definitions)
- [ ] Pretense test files pass pretense linter checks, containing no private member access or reflection on target classes or instances
- [ ] The verified target files (`lib/<name>.py` or `lib/<name>_impl.py`, and `pretense/<name>_pretense.py` or `pretense/<name>_impl_pretense.py`) contain valid `PRETENSE_COVERAGE_AUDIT` metadata tags upon successful completion
