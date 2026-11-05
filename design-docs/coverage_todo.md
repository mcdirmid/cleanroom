# Coverage Architecture, Semantic Auditing & Error Handling Design Doc (`coverage_todo.md`)

> **Status: Active Proposal & Master Implementation Roadmap**  
> **Author:** Cleanroom Architecture Pair  
> **Scope:** Coverage Arbiters (`coverage`, `pretense_coverage`), Specification-Grounded Implementations (`lib`), Unit Tests (`test`), and Harness Verification Gates.

---

## Progress Checklist

- [x] **Phase 1: Guides Alignment (`autofab_py/guides/` & `autofab/guides/`)**
  - [x] Update `coverage.md` & `pretense_coverage.md` to mandate Contract Postcondition Audits and differentiate contracted operational errors from uncontracted caller preconditions.
  - [x] Update `low_to_lib.md` to require specification grounding comments and clarify error-throwing authority.
  - [x] Update `low_to_test.md` to clarify that contracted operational errors must be tested with malformed/invalid inputs.
- [x] **Phase 2: Harness Configuration Hardening**
  - [x] Remove blanket regex exclusions (`raise .*Error\(` and `raise .*Error$`) from `[tool.coverage.report] exclude_also` in `pyproject.toml`.
  - [x] Verify repo integrity with `bin/test` (0 errors, code 0).
- [x] **Phase 3: Empirical Benchmark Re-Evaluation (Flight v2)**
  - [x] Run `semver_solver` combined benchmark (`flight_20261104_225814_deepseek-flash_semver_solver_combined`).
  - [x] Evaluate differential cross-testing: soundness jumped from 45.3% to 97.5% (78/80 foreign tests passing), eliminating 27 wildcard operator defects.
  - [x] Update `docs/cross_test.md` with v2 telemetry and robustness matrices.
- [ ] **Phase 4: Tooling De-coercion & Mechanical Fixes**
  - [x] **HLS-First Alignment for `autofab/parts/workspace_cli`**:
    - [x] Update `high/coverage_impl.md`, `planning/coverage_impl.md`, `scenarios/coverage_impl.md`, `low/coverage_impl.pyi` to allow contracted operational error spans to be test-owned (`TEST-COVERAGE-DEFICIT`), and remove guidance commanding agents to treat all `*Error` raises as library pragmas.
    - [x] Update `high/commands_impl.md`, `planning/commands_impl.md`, `scenarios/commands_impl.md`, `low/commands_impl.pyi` to remove the prohibition on test-directed blame for contracted error postconditions.
  - [x] **Implementation Fixes in `workspace_cli/lib/`**:
    - [x] In `coverage_impl.py:classify_span`: Differentiate contracted errors (`Raises: ...Error` in `low/<name>.pyi`) from uncontracted caller preconditions (`ASSUMPTIONS:`). Mark contracted error spans as test-owned deficits rather than `LIB-PRAGMA-REQUIRED`.
    - [x] In `coverage_impl.py:format_coverage_report`: Remove misleading guidance that all `*Error` raises belong to library pragma annotations.
    - [x] In `commands_impl.py:run_blame`: Remove the mechanical check aborting `bin/blame` on test targets when error spans are present.
  - [ ] **Linter De-coercion in `build_lint_common.py` (UNRESOLVED DEFECT)**:
    - [ ] In `autofab/support/lib/build_lint_common.py` & `autofab_py/support/lib/build_lint_common.py`: Modify `check_no_error_testing` so it resolves `low/*.pyi` declarations and does NOT fail when the asserted exception is explicitly declared as a contracted error or under `Raises:` in the component's companion `low/*.pyi` specification. (Currently blanket-bans any `*Error` in `assertRaises`/`assert_raises`/`raises`, causing the Pretense coverage deadlock).
  - [ ] **Verification**: Run `bin/test` after linter fix.
- [ ] **Phase 5: Pretense Contract Violation & Error Architecture Alignment**
  - [ ] Add optional `error` parameter to `requires` and `require_arg` in Pretense framework (`pretense/`):
    - `require(condition, error=None)`
    - `require_arg(arg, condition, error=None)`
  - [ ] **Fixed Tests vs. Fuzz Tests Distinction**:
    - In **fuzz tests**: State preconditions (`require`) are statically extracted via AST parsing into boolean guarding expressions (`t.requirements`), and argument domains (`require_arg`) are extracted into generative strategies (`param_domains`). The fuzzer generates valid inputs and selects applicable transitions by construction, never exploring contract violations on chosen transitions. At runtime, if an operation violates a precondition (such as the SUT invoking a fake collaborator with an unsatisfied precondition), `require` raises a contract violation (`PretenseSpecificationError` or the contracted `error`), immediately failing the test. Precondition failures during execution are NEVER discarded or thrown out.
    - In **fixed tests** (deterministic scenario tests used to establish statement coverage under `--no-fuzz --cov`): Fixed tests can check contracted error outcomes by writing a sequence of transitions that end in a contract violation, throwing the specified `Error` rather than raising a generic framework contract violation.
  - [ ] **Coverage Arbiter Semantic Audit**:
    - Uncovered `raise ...Error` statements must be checked by the coverage arbiter to verify whether the condition is genuinely an error/precondition or a mistaken rejection of valid specification behavior (such as `> 1.x`).
    - If genuinely an error/precondition, it can be exercised by fixed tests via a contract-violation transition, or annotated by `lib` with `# pragma: no cover (assumption: <specification justification>)`.
- [ ] **Phase 6: Benchmark Verification Parity**
  - [ ] Re-run `semver_solver` combined and standard benchmarks to verify 100% soundness parity with Pretense.
  - [ ] Update `docs/cross_test.md` with final results.

---

## Table of Contents

1. [Executive Summary & Motivation](#1-executive-summary--motivation)
   - [The SemVer Solver Incident](#the-semver-solver-incident)
   - [The Pathology of False Mechanical Coverage](#the-pathology-of-false-mechanical-coverage)
2. [Division of Responsibilities: QA vs. Coverage Arbiters](#2-division-of-responsibilities-qa-vs-coverage-arbiters)
   - [The Non-Semantic QA Invariant](#the-non-semantic-qa-invariant)
   - [Coverage Arbiters as Primary Semantic Auditors](#coverage-arbiters-as-primary-semantic-auditors)
3. [Specification Grounding & Code Justification in `lib`](#3-specification-grounding--code-justification-in-lib)
   - [Mandatory Specification Comments in Library Code](#mandatory-specification-comments-in-library-code)
   - [Defining "No-Coverage Territory"](#defining-no-coverage-territory)
   - [Coverage Auditor Justification Requirement](#coverage-auditor-justification-requirement)
4. [Elimination of Blanket `*Error` Coverage Exclusions](#4-elimination-of-blanket-error-coverage-exclusions)
   - [The `pyproject.toml` Vulnerability](#the-pyprojecttoml-vulnerability)
   - [Dual Nature of `raise ...Error`: Preconditions vs. Contracted Errors](#dual-nature-of-raise-error-preconditions-vs-contracted-errors)
   - [Clarifying `lib`'s Authority to Throw Errors](#clarifying-libs-authority-to-throw-errors)
   - [Auditing Every `raise ...Error`](#auditing-every-raise-error)
5. [The Contract Postcondition Audit](#5-the-contract-postcondition-audit)
   - [Beyond Line/Statement Counting: Semantic Completeness](#beyond-linestatement-counting-semantic-completeness)
   - [Audit Checklist & Traceability Matrix](#audit-checklist--traceability-matrix)
   - [Grammar & Combinatorial Domain Coverage in Pretense](#grammar--combinatorial-domain-coverage-in-pretense)
6. [Actionable Implementation Roadmap](#6-actionable-implementation-roadmap)
   - [Phase 1: Guides Alignment (`autofab_py/guides/` & `autofab/guides/`)](#phase-1-guides-alignment-autofab_pyguides--autofabguides)
   - [Phase 2: Configuration & Harness Hardening (`pyproject.toml`)](#phase-2-configuration--harness-hardening-pyprojecttoml)
   - [Phase 3: Tooling & Static Linters (`test_lint.py` & `bin/check_files`)](#phase-3-tooling--static-linters-test_lintpy--bincheck_files)
   - [Phase 4: Empirical Benchmark Re-Evaluation](#phase-4-empirical-benchmark-re-evaluation)

---

## 1. Executive Summary & Motivation

### The SemVer Solver Incident
During cross-suite benchmarking of the `semver_solver` component, the Cleanroom `combined` workflow converged cleanly across all 7 roles with 100% statement coverage, zero linter defects, and passing test suites. However, differential cross-testing against external suites revealed that `combined` achieved only **45.3% soundness**, failing 24 out of 53 foreign cross-tests. In contrast, standalone `pretense` achieved **100.0% soundness** (29/29 passing).

Forensic analysis revealed the following root cause:
1. In [`benchmarks/results/semver_solver/deepseek-flash-combined/lib_1.py` lines 563–567](file:///Users/seanmcdirmid/projects/cleanroom/benchmarks/results/semver_solver/deepseek-flash-combined/lib_1.py#L563-L567), the library author hallucinated a defensive restriction:
   ```python
   if _expand_wildcard(target) is not None:
       raise InvalidRangeError(
           message=f"Operator {operator!r} cannot be applied to wildcard {target!r}",
           raw_range=raw_text,
       )
   ```
2. The low-level specification in [`benchmarks/parts/semver_solver/low/semver_solver.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/benchmarks/parts/semver_solver/low/semver_solver.pyi) explicitly contracted that relational and prefix operators can and must be applied to wildcards:
   > `- MUST accept optional whitespace between relational/prefix operators and target versions or wildcards (e.g. '>= 1.0.0' is equivalent to '>=1.0.0').`
3. Neither unit tests nor Pretense scenarios sampled operators on wildcards (both tested only bare wildcards like `1.x` and `1.2.x`).
4. When the `coverage` arbiter ran, it flagged lines 564–567 as uncovered. However, following Cleanroom dogma that `*Error` raises represent uncontracted caller precondition violations that tests are forbidden from asserting, the arbiter instructed `lib` to make the raise unqualified so that [`pyproject.toml` line 104](file:///Users/seanmcdirmid/projects/cleanroom/pyproject.toml#L104) would exclude it via regex:
   ```toml
   [tool.coverage.report]
   exclude_also = [
       'raise [A-Za-z0-9_]*Error\(',
       'raise [A-Za-z0-9_]*Error$',
   ]
   ```
5. Once excluded, mechanical statement coverage reached 100%, and the broken code converged cleanly without ever implementing the required interval algebra.

### The Pathology of False Mechanical Coverage
The incident exposes a fatal vulnerability in relying purely on syntactic statement coverage:
- **Syntactic Constraint Satisfaction**: When a language model is tasked with achieving 100% statement coverage under a rule that says "negative `*Error` branches are caller assumptions that must be pruned or pragmad out", the model naturally satisfies the constraint by marking or excluding uncovered branches—even when those branches are rejecting contracted valid inputs!
- **Invisible Blindspots**: Blanket regex exclusions in test runner configurations automatically swallow unexercised code, hiding specification non-compliance behind a facade of 100% coverage.

This design document establishes the architectural changes required to transform coverage arbitration from a mechanistic line-counting exercise into a rigorous **semantic contract postcondition audit**.

---

## 2. Division of Responsibilities: QA vs. Coverage Arbiters

A central finding of the post-mortem is that role confusion and hand-off assumptions between QA and Coverage created an audit vacuum where neither role performed semantic verification.

```
       [low/*.pyi Contract Specification]
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌──────────────────┐   ┌───────────────────────────────┐
│    QA Arbiter    │   │       Coverage Arbiter        │
│(qa/pretense_qa)  │   │ (coverage/pretense_coverage)  │
├──────────────────┤   ├───────────────────────────────┤
│ • Pure Execution │   │ • Semantic Contract Audit     │
│ • Diagnoses Active│  │ • Requirement Completeness   │
│   Test Failures  │   │ • Traces low/*.pyi Postconds  │
│ • ZERO Spec Audit│   │ • Audits Every raise ...Error │
│   when tests PASS│   │ • Challenges 'no cover' Spans │
└──────────────────┘   └───────────────────────────────┘
```

### The Non-Semantic QA Invariant
The QA arbiters ([`qa`](file:///Users/seanmcdirmid/projects/cleanroom/autofab_py/guides/qa.md) and [`pretense_qa`](file:///Users/seanmcdirmid/projects/cleanroom/autofab_py/guides/pretense_qa.md)) are strictly runtime execution auditors:
- **Scope**: Evaluate active test failures resulting from `bin/check_files` or `uv run pretense`.
- **Operational Rule**: When all tests pass under verification, QA is **strictly prohibited** from inspecting library implementation code, reading test assertions, or second-guessing specification coverage. QA stamps the target clean and submits.
- **Rationale**: If QA were allowed to perform unbounded semantic reviews of passing code, it would introduce infinite debate, speculative blaming, and circular thrashing on style or taste without concrete failing executions.

### Coverage Arbiters as Primary Semantic Auditors
Because QA does not audit passing tests, **the Coverage Arbiters ([`coverage`](file:///Users/seanmcdirmid/projects/cleanroom/autofab_py/guides/coverage.md) and [`pretense_coverage`](file:///Users/seanmcdirmid/projects/cleanroom/autofab_py/guides/pretense_coverage.md)) are exclusively responsible for semantic auditing**:
- Coverage arbiters cannot simply check whether line numbers in `lib/*.py` executed during the test run.
- Coverage arbiters must audit **why** code was executed, **which** specification contracts are exercised, and **whether** unexercised or pragmad lines represent legitimate caller assumptions or unfulfilled specification postconditions.

---

## 3. Specification Grounding & Code Justification in `lib`

To enable coverage arbiters to perform semantic audits without guessing the library author's intent, library code must be self-justifying in terms of the low-level specification.

### Mandatory Specification Comments in Library Code
Library implementations ([`lib/*.py`](file:///Users/seanmcdirmid/projects/cleanroom/autofab_py/guides/low_to_lib.md)) must explicitly ground control flow, input validation, branching, and edge cases in the specification:
1. **Contract Mapping Comments**: Each non-trivial method, parsing branch, and conditional branch must include a comment citing the corresponding postcondition, invariant, or grammar clause from `low/<name>.pyi`:
   ```python
   # CONTRACT: low/semver_solver.pyi:224 - accept optional whitespace between
   # relational/prefix operators and target versions or wildcards (e.g. '>= 1.0.0').
   operand = _parse_operand(raw_token)
   ```
2. **Defensive Invariant Comments**: If internal consistency checks or loop termination guards are added that do not map directly to a user-facing postcondition, the comment must justify its necessity:
   ```python
   # INVARIANT: Loop guaranteed to terminate because tokens are consumed strictly.
   if index == last_index:
       raise AssertionError("Parser loop made no forward progress")
   ```

### Defining "No-Coverage Territory"
Code in `lib/*.py` falls into one of two mutually exclusive territories:

| Territory | Description | Verification Requirement |
| :--- | :--- | :--- |
| **Covered Territory** | All valid inputs, operational transformations, grammar constructs, contracted error responses, and state mutations specified in `low/*.pyi`. | Must be exercised by positive-path unit tests (`tests/*_test.py`) or Pretense scenarios (`pretense/*_impl_pretense.py`). |
| **No-Coverage Territory** | Conditions that should **NOT** be handled under the specification (caller precondition violations, uncontracted impossible states, uncontracted defensive fallbacks). | Must be explicitly excluded via `# pragma: no cover (assumption: <reason>)` or `unreachable()`. |

### Coverage Auditor Justification Requirement
When an uncovered line or branch is discovered, the coverage arbiter is strictly prohibited from reflexively ordering a `# pragma: no cover`:
- The coverage arbiter must analyze the branch against `low/*.pyi`.
- **Burden of Proof**: The coverage arbiter must make a **rigorous case in terms of the specification** explaining why the code is in "no-coverage territory":
  - If the branch handles an input that the contract guarantees the caller will never supply (`ASSUMPTIONS:`), the arbiter attributes blame to `lib` with an explicit reason to annotate:
    `[BLAME] lib/<name>.py: Line 45 protects against caller null input which is uncontracted under low/<name>.pyi ASSUMPTIONS; annotate with '# pragma: no cover (assumption: caller guarantees non-null)'.`
  - If the branch handles an input or syntax that the contract actually mandates (e.g., wildcard operators), the arbiter **must NOT permit a pragma**. It must blame `lib` if the implementation is rejecting valid input, or blame `tests` / `pretense` if the test suite failed to exercise it.

---

## 4. Elimination of Blanket `*Error` Coverage Exclusions

### The `pyproject.toml` Vulnerability
The root cause of the silent bypass was the global configuration in [`pyproject.toml`](file:///Users/seanmcdirmid/projects/cleanroom/pyproject.toml):
```toml
# VULNERABLE CONFIGURATION (TO BE REMOVED)
[tool.coverage.report]
exclude_also = [
    'def unreachable\(',
    'unreachable\(',
    'assert_never\(',
    'raise AssertionError\(',
    'assert False',
    'raise [A-Za-z0-9_]*Error\(',  # <--- CRITICAL HOLE
    'raise [A-Za-z0-9_]*Error$',   # <--- CRITICAL HOLE
]
```
By globally excluding any line matching `raise .*Error\(`, `coverage.py` treated every exception raise as pre-covered. Any hallucinated defensive guard (like `if wildcard: raise InvalidRangeError`) became completely invisible to coverage metrics.

### Reachability of Contract Violations: Contracted Errors vs. Uncontracted Guards

1. **Contract Violations with Contracted Errors (Must Be Reachable)**:
   - A contract violation that has a contracted `*Error` associated with it in the specification **must be reachable** under fixed testing. Otherwise, there is no point in throwing an error.
   - Because it is reachable, a fixed test (deterministic unit test or Pretense scenario method) can and should reach it to verify the specified error behavior.

2. **Contract Violations Without Contracted Errors (Assumed Unreachable)**:
   - Other contract violations without contracted errors (e.g. defensive internal checks, caller precondition assertions, defensive fallbacks) may or may not be physically reachable.
   - When such branches appear as uncovered lines in `lib/*.py`, the coverage subagent **should assume they are unreachable**.
   - The library can handle these uncovered branches through one of three valid mechanisms:
     1. **`unreachable()` Call**: Replacing or guarding the branch with `from pretense import unreachable; unreachable()`, which crashes explicitly if ever actually reached during execution.
     2. **Pragma Annotation**: Marking the line with `# pragma: no cover (assumption: <specification justification>)`.
     3. **Code Restructuring**: Restructuring the implementation to eliminate the unreachable or redundant branch entirely.

### Contract Violations & Error Handling: Fuzz Tests vs. Fixed Tests

Once a contract violation occurs, the system is in an unknown bad state and assumed unusable. Under Cleanroom principles, error handling and contract violations interact fundamentally differently between generative fuzzing and deterministic scenario testing:

1. **Fuzz Testing Generates Valid Inputs by Construction**:
   - Fuzz testing explores the valid operational state space of transitions and invariant preservation.
   - **Fuzz testing will never explore contract violations on chosen transitions**:
     - Preconditions (`require`) are statically extracted via AST parsing into boolean guarding expressions (`t.requirements`), ensuring that transitions with unmet state preconditions are never selected.
     - Argument requirements (`require_arg`) are extracted into domain strategies (`param_domains`), ensuring that arguments are drawn valid by construction.
   - **Precondition Violations at Runtime are Test Failures**: If code executed during fuzz testing violates a precondition (for example, the SUT invokes a fake collaborator with an unsatisfied precondition or out-of-domain argument), `require` and `require_arg` raise `PretenseSpecificationError` (or the contracted `error`). This fails the test immediately—it is NEVER discarded or thrown out by Hypothesis.

2. **Fixed Tests Can Check Errors to Establish Coverage**:
   - In deterministic fixed tests (scenario test methods run under `--no-fuzz --cov` to establish statement coverage), errors can be checked.
   - Pretense's `require` and `require_arg` support an optional `error` parameter:
     ```python
     require(condition, error=InvalidVersionError)
     require_arg(text, len(text) > 0, error=InvalidRangeError)
     ```
   - In a fixed test, this error can be verified by writing a sequence of transitions that end in a contract violation.
   - In fixed execution mode, when the contract is violated, the harness throws the specified `Error` rather than raising a generic framework contract violation.

### Clarifying `lib`'s Authority to Throw Errors
Library authors are fully authorized to throw errors:
- `lib` **MUST** throw errors when an operation encounters an invalid or unhandled condition under the specification.
- `lib` **MAY** throw defensive errors when detecting caller invariant breaches (preconditions).

However, `lib` is strictly forbidden from throwing errors on **valid contracted inputs** under the mistaken assumption that they are malformed syntax (as occurred when `lib` rejected relational operators on wildcards like `>1.x`).

### Semantic Auditing of Every `raise ...Error` by Coverage Arbiters
Every single `raise ...Error` in `lib/*.py` must be accounted for by the coverage arbiter:
1. **Semantic Spec Check**: Is the condition being rejected actually required to be handled by the specification?
   - If the contract mandates support for this condition (e.g. relational wildcard operators), the library author has mistakenly treated valid specification behavior as an error.
   - **Blame `lib`**: The coverage arbiter refuses a pragma and blames `lib` to implement the required specification behavior.
2. **Genuine Error Conditions / Preconditions**:
   - If the condition is genuinely an error condition or caller precondition violation under the specification, it belongs in **no-coverage territory**.
   - It can be covered in fixed scenario tests via terminal contract-violation transitions with `require(..., error=...)`, OR
   - It can be annotated by `lib` with `# pragma: no cover (assumption: <specification justification>)`.
   - **Fuzz testing is NEVER blamed for failing to test an error.** Blanket or un-annotated exception raises remain uncovered lines, requiring explicit auditor review.

---

## 5. The Contract Postcondition Audit

### Beyond Line/Statement Counting: Semantic Completeness
Passing 100% statement coverage is a baseline prerequisite, but it does not prove that the specification has been implemented. An agent can achieve 100% statement coverage of a simplified, incorrect implementation that completely omits key clauses of the specification.

The **Contract Postcondition Audit** mandates that the coverage arbiter verify semantic completeness against `low/<name>.pyi` before stamping `COVERAGE_AUDIT` or `PRETENSE_COVERAGE_AUDIT`.

```
┌────────────────────────────────────────────────────────────────────────┐
│                     Coverage Arbiter Decision Tree                     │
└────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
                       Is statement coverage == 100%?
                                     │
                      ┌──────────────┴──────────────┐
                      │ NO                          │ YES
                      ▼                             ▼
           Is uncovered span a           Does test/scenario suite
           contracted Error postcondition? exercise ALL postcondition
                      │                  bullets from low/*.pyi?
              ┌───────┴───────┐                     │
              │ YES           │ NO          ┌───────┴───────┐
              ▼               ▼             │ YES           │ NO
       Must be reachable!   Assume          │               ▼
       Blame test/pretense  unreachable!    ▼           Blame test/pretense
       fixed test to add    Instruct lib  SUBMIT        with missing
       covering error test  to unreachable()  (Stamp Audit) contract requirements
                            or pragma
```

### Audit Checklist & Traceability Matrix
During each coverage round, the coverage arbiter must construct a mental or log-verified traceability matrix against `low/<name>.pyi`:

1. **POSTCONDITIONS: Enumeration**:
   - Inspect every bullet under `POSTCONDITIONS:` for all methods in `low/<name>.pyi`.
   - Verify that at least one test method in `tests/*_test.py` or scenario in `pretense/*_impl_pretense.py` asserts the specified outcome.
2. **Grammar & Operator Closure**:
   - When a component parses an expression language or grammar (e.g., version ranges, query strings, configuration formats), verify that **every** operator, operand kind, and allowed syntactic variant contracted in `low/*.pyi` is tested.
   - Check all permitted combinations: basic comparators (`==`, `!=`, `<`, `<=`, `>`, `>=`), prefix operators (`^`, `~`), wildcards (`*`, `x`, `X`, `M.x`), hyphen ranges, and whitespace variations.
3. **Boundary Values & Invariants**:
   - Verify zero-boundaries (e.g. `^0.x.x`, `^0.0.x`), negative values, empty sequences, and maximum boundaries.

If any explicit bullet from `low/<name>.pyi` is unexercised, the coverage arbiter **must blame the test role** to add a covering scenario—even if statement coverage is already 100%.

### Grammar & Combinatorial Domain Coverage in Pretense
In Pretense workflows, this vulnerability was amplified because the Pretense interface state machine (`pretense/<iface>_pretense.py`) only sampled bare wildcards in `VALID_RANGE_TEXTS`.

The Pretense Coverage Arbiter must enforce:
- **Domain Completeness**: `VALID_*` corpora and Hypothesis strategies in `pretense/<iface>_pretense.py` must span the full combinatorial closure of the contracted grammar.
- **No Unmandated Restrictions**: Interface state machines must not restrict drawn inputs below what the specification contracts as valid. If the grammar permits `>1.x`, the Pretense domain must generate `>1.x`.

### Pretense Contract Violations via `require` and `require_arg`
Pretense transitions enforce preconditions using `require` and `require_arg`:
```python
require(condition, error=None)
require_arg(arg, condition, error=None)
```
The behavior splits cleanly between execution modes:
1. **Fuzz Testing Mode**:
   - Fuzz testing is strictly generative and invariant-preserving.
   - Transition selection and argument generation are governed upfront:
     - `require` expressions are statically compiled into boolean guards that prevent ineligible transitions from being selected.
     - `require_arg` domains generate conforming argument values by construction.
   - If an invalid precondition is ever executed at runtime (e.g. SUT invokes a fake collaborator with an unsatisfied precondition), `require` raises `PretenseSpecificationError` (or the contracted error) and **fails the test immediately**; it is never discarded or swallowed.
2. **Fixed Scenario Testing Mode (`--no-fuzz --cov`)**:
   - Fixed tests (deterministic scenario methods written to establish statement coverage) can explicitly verify that contract violations throw the expected error.
   - When a fixed scenario test executes a sequence of transitions that intentionally ends in a contract violation, `require` throws the specified `error` (e.g. `InvalidVersionError`) rather than raising a generic framework contract violation.
   - Fixed tests can assert that this specific error was thrown, establishing coverage of the library's error-raising branches.

---

## 6. Actionable Implementation Roadmap

### Phase 1: Guides Alignment (`autofab_py/guides/` & `autofab/guides/`)

Guide edits must be concise, declarative, and adhere strictly to `autofab/guides/meta_guide.md`:
- Environmental communication is declarative and impersonal: second-person pronouns ("you", "your") and directive verbs ("ensure", "produce", "apply", "verify") are strictly prohibited.
- Constraints use declarative statements ("the module must", "X matches Y").
- The Summary is at most two concise paragraphs.
- Checklist items use `- [ ] <item>` lines stating objective invariants.

#### 1. Update `coverage.md` & `pretense_coverage.md`
- **Summary**: Frame coverage arbitration as a dual verification of 100% statement coverage and the semantic contract postcondition audit. State that fuzz testing never explores contract violations, while fixed scenario tests can check contracted error outcomes via terminal contract-violation transitions. Clarify that uncovered `raise ...Error` lines must be audited by the coverage arbiter: if the condition should be handled under the spec, blame `lib`; if genuinely an error condition, it can be tested via fixed scenario tests or annotated with `# pragma: no cover (assumption: <specification justification>)`.
- **Checklist Changes**:
  - Declaratively distinguish fuzz testing (never explores contract violations) from fixed tests (can check contracted errors via transitions ending in contract violations).
  - Add requirement: blame requiring `# pragma: no cover` must quote the specific `low/*.pyi` contract or assumption that renders the code unreachable under conforming execution.
  - Add requirement: contract postcondition audit verifies every explicit postcondition and grammar construct contracted in `low/*.pyi`; if an explicit contract postcondition is unexercised, blame tests/pretense to add coverage even when statement coverage is 100%.

#### 2. Update `low_to_lib.md`
- **Summary**: Clarify that implementation modules realize operational postconditions and contracted operational errors (`Raises: ...Error`), while caller assumptions (`ASSUMPTIONS:`) are accepted axiomatically with retained caller-precondition guards annotated with `# pragma: no cover (assumption: <reason>)`.
- **Checklist Changes**:
  - Strengthen specification comments: implementation methods, validation logic, and conditional branches include brief comments citing corresponding postconditions, invariants, or grammar clauses in `low/<name>.pyi`.
  - Clarify error authority: raising exceptions for contracted operational failure conditions (`Raises: ...Error`) is required and unannotated; defensive branches for uncontracted caller preconditions are annotated with `# pragma: no cover (assumption: <reason>)`.

#### 3. Update `low_to_test.md`
- **Summary & Checklist**: Clarify that while uncontracted caller precondition violations are untestable, contracted operational validation errors (`Raises: ...Error` specified in `low/<name>.pyi`) are tested to verify contracted failure reporting.

#### 4. Update `qa.md` & `pretense_qa.md`
- Reaffirm that QA remains strictly execution-driven and does not perform semantic auditing of passing test suites.

---

### Phase 2: Configuration & Harness Hardening (`pyproject.toml`)

#### Modify Coverage Exclusions in `pyproject.toml`
Update [`pyproject.toml` lines 97–107](file:///Users/seanmcdirmid/projects/cleanroom/pyproject.toml#L97-L107) to remove blanket regex exclusions on `*Error`:

```toml
# BEFORE (Vulnerable)
[tool.coverage.report]
exclude_also = [
    'def unreachable\(',
    'unreachable\(',
    'assert_never\(',
    'raise AssertionError\(',
    'assert False',
    'raise [A-Za-z0-9_]*Error\(',
    'raise [A-Za-z0-9_]*Error$',
]

# AFTER (Hardened)
[tool.coverage.report]
exclude_also = [
    'def unreachable\(',
    'unreachable\(',
    'assert_never\(',
    'raise AssertionError\(',
    'assert False',
]
```

With this change, any line in `lib/*.py` that executes a `raise ...Error` will be measured as an uncovered statement unless:
1. It is exercised by a test asserting that error postcondition, OR
2. It is explicitly annotated by the author with `# pragma: no cover (assumption: <reason>)` and audited by the coverage arbiter.

---

### Phase 3: Tooling & Static Linters (`test_lint.py` & `bin/check_files`)

To prevent models from inserting meaningless pragmas (e.g. `# pragma: no cover` without explanation), introduce automated linter rules:

1. **Rule `PRAGMA_ASSUMPTION_REQUIRED`**:
   - Any `# pragma: no cover` in `lib/*.py` must match the format:
     `# pragma: no cover (assumption: <non-empty justification>)`
   - Bare `# pragma: no cover` is rejected by `bin/check_files` as a linter violation.
2. **Rule `NO_UNANNOTATED_DEFENSIVE_RAISE`**:
   - If a line raises an exception and is not exercised, it must carry the required pragma assumption comment.

---

### Phase 4: Empirical Benchmark Re-Evaluation

Once Phases 1–3 are implemented:
1. Re-run the `semver_solver` benchmark under the updated harness:
   ```bash
   uv run autofab benchmark --suite semver_solver --method combined --model deepseek-flash
   ```
2. Verify that:
   - When the `lib` worker drafts the wildcard-operator check, `coverage` does not automatically exclude it.
   - The coverage arbiter refuses to stamp the audit because relational wildcards are contracted in `low/semver_solver.pyi`.
   - The test and scenario suites are forced to assert operators on wildcards.
   - The library worker implements the full interval algebra.
   - Differential cross-testing on `semver_solver` achieves **100% soundness**.

---

## 7. The Pretense `NO_ERROR_TESTING` Deadlock Incident & Resolution

### Incident Analysis: `benchmark_2` (SemVer Solver Combined)

During autonomous benchmarking of `semver_solver` under `deepseek-flash` with the `combined` methodology (`benchmark_2`), execution entered a multi-round impasse between `pretense_coverage` and `pretense`:

```
┌────────────────────────────────┐
│   semver_solver_impl.py (lib)  │
│  68.9% statement coverage      │
│  (99 missed lines: raises)     │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│ pretense_coverage (Turn 1)     │
│ Blames pretense for missing    │
│ InvalidVersionError, etc.      │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│   pretense worker              │
│ Adds assertRaises(...)         │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│   bin/check_files Linter       │
│ REJECTS with NO_ERROR_TESTING! │
│ "Preconditions cannot be       │
│ tested, even if checked"       │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│   pretense worker removes tests│
│ Coverage maxes out at 85.0%    │
│ Leaves # CHANGE: blocker note  │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│ pretense_coverage (Turn 2)     │
│ Froze on unyielding rule:      │
│ Can't blame pretense again,    │
│ but errors are spec-contracted!│
└────────────────────────────────┘
```

#### Detailed Breakdown
1. **The Lib Implementation**: `benchmark_2/parts/semver_solver/lib/semver_solver_impl.py` implements the parser and solver, raising `InvalidVersionError`, `InvalidRangeError`, `PackageNotFoundError`, and `ResolutionConflictError`.
2. **The Coverage Audit**: In Turn 1, `pretense_coverage` observed 68.9% statement coverage (99 missed lines). The arbiter correctly identified that these exception branches represented explicit requirements in `low/semver_solver.pyi` (which states: `Verification suites MUST assert on exception types and structured attributes`). The arbiter blamed `benchmark_2/parts/semver_solver/pretense/semver_solver_impl_pretense.py` to exercise these outcomes.
3. **The Static Linter Ambush**: The `pretense` worker attempted to implement tests exercising these errors. However, `bin/check_files` executed `check_no_error_testing` in `build_lint_common.py`, which failed the module with:
   ```
   error [NO_ERROR_TESTING]: Contract violation errors (*Error) designate checked preconditions that callers must satisfy and cannot be tested (found 'InvalidVersionError'). Preconditions cannot be tested, even if explicitly checked in code. Tests and transitions must never assert or expect *Error exceptions; preconditions must be satisfied by the caller (or gated via require(...) in Pretense).
   ```
4. **The Rollback & Plateau**: Because `bin/check_files` blocked submission, the `pretense` worker deleted the `assertRaises` tests, expanded coverage on valid grammar constructs to reach 85.0%, and documented the blocker in `# CHANGE:`.
5. **The Arbiter Freezes in Turn 2**: In Turn 2, `pretense_coverage` observed 47 missed lines (all error paths). Under the guide's "Unyielding deficit reachability audit" rule, repeating blame against `pretense` is strictly prohibited after tests have been updated. But the arbiter could not blame `lib` to prune or pragma the code either, because `low/semver_solver.pyi` explicitly contracts these exceptions as required public outcomes!

### Root Cause: Naive AST Linter Heuristic

The root cause is a severe semantic conflation in `check_no_error_testing` inside `autofab/support/lib/build_lint_common.py` and `autofab_py/support/lib/build_lint_common.py`:

```python
# DEFECTIVE CODE IN build_lint_common.py
def _extract_error_names(expr: ast.AST) -> list[str]:
    names: list[str] = []
    if isinstance(expr, ast.Name) and expr.id.endswith("Error"):
        names.append(expr.id)
    ...
```

The linter blindly treated **every identifier ending in `Error`** as an uncontracted caller precondition violation. It made zero distinction between:
- **Uncontracted Caller Preconditions**: (e.g. passing a negative length when positive is assumed, or testing internal defensive assertions). Callers must satisfy preconditions, and tests must not assert them.
- **Contracted Operational Errors**: (e.g. `InvalidVersionError`, `InvalidRangeError`, `PackageNotFoundError`, `ResolutionConflictError`). These are contracted interface postconditions. When arbitrary text or dependency sets are passed to public parsing or resolution entry points, raising these specific errors is the required contract postcondition.

Unit tests (`tests/*_test.py`) survived only because the `test` role worker bypassed the linter using generic exception capture (`try...except Exception as e: self.assertIsInstance(e, InvalidVersionError)`), avoiding the AST call check on `assertRaises`. The `pretense` role used `assertRaises` directly and was completely blocked.

### Architecture Solution

#### 1. Specification-Aware Exception Resolution in `build_lint_common.py`
`check_no_error_testing` must resolve the active component's `low/*.pyi` interface specification:
1. Parse the target's associated `low/*.pyi` specifications.
2. Collect all exception classes declared as data types, classes inheriting from `Exception`, or referenced under `Raises:` docstring blocks.
3. Treat declared exceptions as **Contracted Operational Errors**.
4. **Exemption**: If an asserted error in `assertRaises`, `assert_raises`, or `raises` is a declared Contracted Operational Error, `check_no_error_testing` **MUST NOT** emit `[NO_ERROR_TESTING]`.
5. Only reject assertion of uncontracted exception types (caller preconditions).

#### 2. Pretense Verification Modes for Contracted Errors
Clarify the two distinct operational modes in Pretense:
- **Generative Fuzz Testing Mode**: Preconditions on state machine transitions (`require`, `require_arg`) define the operational input domain. Fuzz testing generates valid inputs by construction and never explores precondition violations.
- **Deterministic Fixed Scenario Mode (`Test<Impl>Real`, `--no-fuzz --cov`)**:
  - Testing contracted operational errors to establish statement coverage is **fully supported and required**.
  - Can be asserted directly in `Test<Impl>Real` using standard `with self.assertRaises(ContractedError):` blocks (once de-coerced by the linter), OR
  - Via terminal transition execution ending in `require(condition, error=ContractedError)`.

#### 3. Arbiter Protocol for Uncontracted Defensive Guards
If an uncovered `raise` in `lib/*.py` is **NOT** declared in `low/*.pyi`:
- The coverage arbiter assumes it is an uncontracted caller precondition or unreachable defensive guard.
- The arbiter blames `lib` to prune the dead code, replace with `from pretense import unreachable; unreachable()`, or annotate with `# pragma: no cover (assumption: <reason>)`.
- Blaming tests or Pretense for failing to cover uncontracted defensive guards remains strictly prohibited.

#### 4. Prohibition of `try...except` in Test and Scenario Methods (`[NO_TRY_EXCEPT_IN_TESTS]`)
In `benchmark_1`, the test writer evaded `check_no_error_testing` by catching errors with `try...except` in a test method. This evasion exposes a critical reliability risk: if the implementation fails to raise the expected exception, a `try...except` block silently passes unless explicit boilerplate flags and assertions are meticulously maintained.

To enforce fail-closed assertion semantics and prevent linter evasion:
1. `test_lint.py` and `pretense_lint.py` enforce `[NO_TRY_EXCEPT_IN_TESTS]` across all unit tests and Pretense scenario tests.
2. Any test method or scenario using a `try...except` block is rejected.
3. Exception testing must use `with self.assertRaises(ContractedError):` (or `with pytest.raises(ContractedError):`).
4. `try...finally` (without except handlers) remains permitted for fixture teardown.
5. Non-test support code in test modules requiring `try...except` (such as mock stubs) must be explicitly annotated with `# pragma: allow-try-except`.

