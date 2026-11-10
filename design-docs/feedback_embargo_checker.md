# Auditor Feedback Filter Subagent & Information Embargo Firewall Design Document

> **Authoritative Technical Design Specification**  
> This document specifies the architectural requirements, formal verification invariants, and proposed implementation solutions for the **Feedback Embargo Checker & Auditor Feedback Filter Subagent**.  
> It operationalizes **Task 4 (Feedback Embargo Checker Sub-Agent & Anti-Pruning Verification Gate)** from [`design-docs/todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md#L651) and provides the technical enforcement mechanism for the Non-Contaminating Blame Operator ($\mathcal{I}(P; V \mid \text{Blame}) = 0$) formalized in [`design-docs/paper_submission_design_doc.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md#L607).

---

## Table of Contents

1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [Empirical Failure Modes in Auditor Feedback](#2-empirical-failure-modes-in-auditor-feedback)
   - [Failure Mode 1: Information Leakage & Boundary Contamination ($\mathcal{I} > 0$)](#failure-mode-1-information-leakage--boundary-contamination-mathcali--0)
   - [Failure Mode 2: Hallucination Echo Chamber & Spec Misunderstanding Propagation](#failure-mode-2-hallucination-echo-chamber--spec-misunderstanding-propagation)
   - [Failure Mode 3: Ungrounded Demands & Auditor Overreach](#failure-mode-3-ungrounded-demands--auditor-overreach)
   - [Failure Mode 4: Destructive Pruning & Defensive Code Bullying](#failure-mode-4-destructive-pruning--defensive-code-bullying)
   - [Failure Mode 5: Prescriptive Micromanagement & Token Bloat](#failure-mode-5-prescriptive-micromanagement--token-bloat)
3. [The Core Feedback Rules & Formal Invariants](#3-the-core-feedback-rules--formal-invariants)
   - [Invariant 1: Normative Specification Grounding ($S = \langle \Sigma, \mathcal{C} \rangle$)](#invariant-1-normative-specification-grounding-s--langle-sigma-mathcalc-rangle)
   - [Invariant 2: Cognitive Independence & Anti-Echoing Firewall](#invariant-2-cognitive-independence--anti-echoing-firewall)
   - [Invariant 3: Physical Information Embargo ($\mathcal{I}(P; V \mid \text{Blame}) = 0$)](#invariant-3-physical-information-embargo-mathcalip-v-mid-textblame--0)
   - [Invariant 4: Anti-Pruning & Defensive Code Preservation](#invariant-4-anti-pruning--defensive-code-preservation)
   - [Invariant 5: Non-Prescriptive Formatting & Context Budget Protection](#invariant-5-non-prescriptive-formatting--context-budget-protection)
4. [Subagent Requirements Specification](#4-subagent-requirements-specification)
   - [Functional Requirements](#functional-requirements)
   - [Input Boundary & Visibility Matrix](#input-boundary--visibility-matrix)
   - [Decision Protocol & Verdict Schema](#decision-protocol--verdict-schema)
   - [Performance, Latency & Economic Budgets](#performance-latency--economic-budgets)
5. [Comparative Analysis of Architectural Solutions](#5-comparative-analysis-of-architectural-solutions)
   - [Option A: Synchronous In-Line Interception in `bin/blame`](#option-a-synchronous-in-line-interception-in-binblame)
   - [Option B: Asynchronous Wave-Boundary Mediation in Coordinator](#option-b-asynchronous-wave-boundary-mediation-in-coordinator)
   - [Option C: Dedicated Intermediate Methodology Role (`feedback_qa`)](#option-c-dedicated-intermediate-methodology-role-feedback_qa)
   - [Evaluation Matrix & Selection](#evaluation-matrix--selection)
6. [Recommended Solution: Two-Tiered Hybrid "Feedback Firewall"](#6-recommended-solution-two-tiered-hybrid-feedback-firewall)
   - [Tier 1: Zero-Token Deterministic Static Pre-Filter](#tier-1-zero-token-deterministic-static-pre-filter)
   - [Tier 2: Semantic Subagent Arbiter (`feedback_filter`)](#tier-2-semantic-subagent-arbiter-feedback_filter)
   - [Rejection, Re-Prompting & Remediation Flow](#rejection-re-prompting--remediation-flow)
   - [Subagent Prompt Engineering & Structured JSON Protocol](#subagent-prompt-engineering--structured-json-protocol)
7. [The Structured Blame Tuple & Violation Slug Grammar](#7-the-structured-blame-tuple--violation-slug-grammar)
   - [The Zero-Entropy Information Theory Principle](#the-zero-entropy-information-theory-principle)
   - [Taxonomy of Violation Class Slugs](#taxonomy-of-violation-class-slugs)
   - [Multifaceted Requirements: Sub-Slug Hierarchies, Equivalence Partitions & Witness Vectors](#multifaceted-requirements-sub-slug-hierarchies-equivalence-partitions--witness-vectors)
   - [Auditor Execution Lifecycle: Blame-Only Concluding & Auto-Submit](#auditor-execution-lifecycle-blame-only-concluding--auto-submit)
   - [The Auditor `bin/fail` Circuit Breaker: Kill-and-Restart $\to$ User Escalation](#the-auditor-binfail-circuit-breaker-kill-and-restart-to-user-escalation)
   - [Auditor Re-Evaluation Protocol (Failed Fixes & Contested Blame)](#auditor-re-evaluation-protocol-failed-fixes--contested-blame)
   - [Uncontracted Behavior (`[viol:test.uncontracted_behavior]`)](#uncontracted-behavior-violtestuncontracted_behavior)
   - [List-Based Ergonomics Over ASCII Tables](#list-based-ergonomics-over-ascii-tables)
   - [Receiver Feedback Rejection (`bin/reject`) & The Unchanged File Invariant](#receiver-feedback-rejection-binreject--the-unchanged-file-invariant)
   - [Strict Plane Separation: Disallowing Slugs in Code Artifacts (`check_no_slug_references`)](#strict-plane-separation-disallowing-slugs-in-code-artifacts-check_no_slug_references)
   - [Auditor Skepticism & Disallowing Mechanistic Slug Reliance](#auditor-skepticism--disallowing-mechanistic-slug-reliance)
   - [The Dual-Agent Impasse Circuit Breaker: Joint Context Reset](#the-dual-agent-impasse-circuit-breaker-joint-context-reset)
   - [Worker Rejection Reasoning & The Noun Phrase Recognizer](#worker-rejection-reasoning--the-noun-phrase-recognizer)
   - [Strict Separation: Downstream Auditors Do Not Spot Specification Errors](#strict-separation-downstream-auditors-do-not-spot-specification-errors)
   - [Standard DAG Propagation on Upstream Specification Changes](#standard-dag-propagation-on-upstream-specification-changes)
   - [Ephemeral Feedback Scrubbing & Header Hygiene](#ephemeral-feedback-scrubbing--header-hygiene)
   - [The Deterministic Slug Linter (`slug_lint.py`)](#the-deterministic-slug-linter-slug_lintpy)
8. [Implementation Blueprint](#8-implementation-blueprint)
   - [Component Decomposition & Touchpoints](#component-decomposition--touchpoints)
   - [AST Symbol Extraction Engine](#ast-symbol-extraction-engine)
   - [Integration with `AttributionCoordinator` & `bin/blame`](#integration-with-attributioncoordinator--binblame)
   - [Configuration Schema in `autofab_roles.toml`](#configuration-schema-in-autofab_rolestoml)
9. [Empirical Verification & Test Strategy](#9-empirical-verification--test-strategy)
   - [Defect Injection Test Matrix](#defect-injection-test-matrix)
   - [Soundness, Churn & Leakage Telemetry](#soundness-churn--leakage-telemetry)
10. [Experimental Gating & Empirical Comparative Testing Framework](#10-experimental-gating--empirical-comparative-testing-framework)
   - [Declarative & Runtime Toggle Mechanisms](#1-declarative--runtime-toggle-mechanisms)
   - [Dual-Mode Dispatch & Behavioral Matrix](#2-dual-mode-dispatch--behavioral-matrix)
   - [Comparative Benchmarking Protocol (`evaluate_model_efficiency.py`)](#3-comparative-benchmarking-protocol-evaluate_model_efficiency_py)

---

## 1. Executive Summary & Problem Statement

Autofab enforces a strict double-blind development methodology where code synthesis ($P$, `lib/*.py`) and verification testing ($V$, `tests/*_test.py` or `pretense/*_pretense.py`) are conducted in physically isolated, ephemeral operating system workspaces (`chmod 444` masks). Neither synthesis nor verification subagents can inspect each other's workspaces.

However, **auditor roles** (`qa`, `coverage`, `spec_qa`, `pretense_qa`, `pretense_coverage`) act as bridges: they run test suites and evaluate implementations against specifications. When an auditor discovers a defect or coverage deficit, it executes `bin/blame <culprit_file> "<critique>"`. The critique is embedded directly into in-band metadata headers (`FEEDBACK:`) of the culprit file, which is then read by the authoring worker in the subsequent round.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Auditor Role (QA / Coverage)                          │
│                     (Inspects Lib, Tests, and Specification)                    │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ bin/blame <culprit> "<critique>"
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │       UNFILTERED FEEDBACK CHANNEL (RISK)      │
                 │  - Leaks private symbols or test assertions   │
                 │  - Echoes misunderstandings between subagents │
                 │  - Demands pruning valid defensive code       │
                 │  - Prescribes line edits / ad-hoc hacks       │
                 └───────────────────────┬───────────────────────┘
                                         │ Injected into Metadata
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      Authoring Worker (Lib / Tests / High)                      │
│                  (Blinded by contamination or misled by echo)                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

Without an authoritative gatekeeper, **the feedback channel becomes an attack vector that shatters the double-blind isolation and induces non-convergence**. An unconstrained auditor leaks private symbols across the fence, echoes hallucinations from buggy tests into compliant libraries, bullies library authors into deleting defensive code, and prescribes brittle code snippets.

This design document establishes the architecture for a dedicated **Feedback Filter Subagent** (and its accompanying two-tier **Feedback Firewall**) that intercepts all auditor blame submissions, filters them against normative specifications, and guarantees that zero contaminated or hallucinated feedback enters downstream workspaces.

---

## 2. Empirical Failure Modes in Auditor Feedback

During empirical benchmark campaigns across `dag_engine_lite` and `semver_solver`, five distinct failure modes were observed when auditors operated without feedback filtering:

### Failure Mode 1: Information Leakage & Boundary Contamination ($\mathcal{I} > 0$)
- **Manifestation**: 
  - *Leaking Test Artifacts to Library Workers*: When a test fails, the QA auditor blames `lib/` stating: `"In test_range_limit line 45, assert r.max == 5 failed with 4"`. The library author immediately hardcodes an `if ... return 5` edge check, overfitting to the test name and assertion rather than synthesizing the general contract rule.
  - *Leaking Internal Library Details to Test Workers*: When testing fails, the auditor tells the test author: `"In lib/parser.py line 120, private helper _tokenize() returned None; update your test setup to pass an extra delimiter"`. The test author begins asserting private helper behavior (`_tokenize`), coupling tests to internal refactorings.
- **Root Cause**: The auditor has global read visibility in its sandbox and casually quotes whichever file is open in its context window without recognizing boundary boundaries.

### Failure Mode 2: Hallucination Echo Chamber & Spec Misunderstanding Propagation
- **Manifestation**:
  - The test author misreads `low/parser.pyi` and writes a test asserting that empty input strings must return an empty list (`[]`).
  - The low-level specification actually explicitly contracts: `PRECONDITIONS: - WHEN input is empty, MUST raise EmptyInputError`.
  - The compliant library correctly raises `EmptyInputError`.
  - The QA auditor runs the test, observes `EmptyInputError != []`, and naively assumes `lib` is broken. The auditor echoes the test author's misunderstanding to the library: `"In parse(), fix method to return [] on empty input instead of raising EmptyInputError"`.
  - The library author obeys the auditor, breaking specification compliance.
- **Root Cause**: The auditor treats test failure as synonymous with library fault, failing to arbitrate against the common specification. It acts as an uncritical parrot for the test author's cognitive errors.

### Failure Mode 3: Ungrounded Demands & Auditor Overreach
- **Manifestation**:
  - The auditor rejects a submission because it dislikes the formatting of an exception string, prefers a different dictionary sorting algorithm, or demands that the library validate types that the specification states are uncontracted preconditions (undefined behavior).
  - Example: Blaming `lib/` for not raising `TypeError` when `None` is passed to a non-optional parameter, even though `low/*.pyi` has no `MUST raise TypeError` clause.
- **Root Cause**: LLM models carry latent aesthetic biases from pre-training and attempt to enforce "clean code" rules not grounded in the repository's explicit contracts.

### Failure Mode 4: Destructive Pruning & Defensive Code Bullying
- **Manifestation**:
  - In `semver_solver` benchmark runs, the `pretense_coverage` auditor observed that internal helper branches handling empty clauses in `||` and wildcards (`*`, `x`) were uncovered by the test suite.
  - The auditor blamed `lib/` with: `"Lines 211 and 321 are uncovered; prune this dead code"`.
  - The library worker was forced to delete valid, specification-compliant edge handling. Consequently, the library failed foreign test suites during cross-evaluation.
- **Root Cause**: Coverage arbiters conflate "unexercised by current tests" with "logically dead code". Instead of directing the test author to expand coverage over valid specification domains, the auditor bullies the library into mutilating its code.

### Failure Mode 5: Prescriptive Micromanagement & Token Bloat
- **Manifestation**:
  - Auditors emit multi-paragraph essays with code diffs, markdown lists, and replacement implementations.
  - This bloats the metadata header, quickly exceeding `max_feedback_chars` (1000 characters), consuming prompt tokens, and encouraging workers to blindly copy-paste buggy snippets.
- **Root Cause**: Lack of strict syntactic token fencing and failure to enforce non-prescriptive diagnostic principles.

---

## 3. The Core Feedback Rules & Formal Invariants

To guarantee convergence and compositional soundness, every blame critique delivered through `bin/blame` must satisfy five formal invariants:

```
                                  FEEDBACK INVARIANTS
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │ 1. Specification Grounded: Anchored in contract slugs, preconditions, postconds. │
 │ 2. Cognitive Independence: Zero propagation of cross-agent misunderstandings.   │
 │ 3. Physical Embargo: Zero leakage of private symbols (_*), foreign line numbers. │
 │ 4. Anti-Pruning: Defensive code permitted by spec domain cannot be deleted.      │
 │ 5. Non-Prescriptive: Single paragraph, zero newlines, concise diagnostics only.   │
 └──────────────────────────────────────────────────────────────────────────────────┘
```

### Invariant 1: Normative Specification Grounding ($S = \langle \Sigma, \mathcal{C} \rangle$)
- All defect attribution must be formulated strictly in terms of the authoritative specification:
  - For `qa` and `coverage`: `low/*.pyi` (and imported boundary contracts).
  - For `spec_qa`: `high/*.md` and `planning/*.md`.
- Feedback must cite an explicit contract clause, invariant, or contract slug (e.g. `[slug:dag.add_node.duplicate]`).
- Uncontracted behavior is undefined behavior. Blaming a component for behavior outside the specification closure $\mathcal{C}$ is strictly prohibited.

### The Decisive Role of Contract Slugs (`[slug:...]`) in Low-Level Specifications

Integrating granular contract slugs into Low-Level Specifications (`low/*.pyi`) (as targeted in [Task 3 of `todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md#L626)) is not merely helpful—it is the **critical architectural enabler** that elevates feedback filtering from a probabilistic, fuzzy LLM heuristic into a deterministic verification gate.

Slugs resolve the four hardest challenges in feedback mediation:

1. **Deterministic Specification Grounding (Mechanical Zero-Token Verification)**:
   - *Without Slugs*: The auditor writes prose descriptions (e.g. *"failed to handle empty delimiters in split"*). The filtering agent must parse unstructured docstrings with fuzzy semantic reasoning to guess whether this requirement actually exists in `low/*.pyi` or was hallucinated by the auditor.
   - *With Slugs*: Docstring postconditions carry explicit identifiers:
     ```python
     def split(self, text: str, delim: str) -> list[str]:
         """Split text by delimiter.
         
         POSTCONDITIONS:
         - [slug:string.split.empty_delimiter]: WHEN delim is empty, MUST raise ValueError.
         - [slug:string.split.consecutive_delimiters]: WHEN delim is repeated, MUST preserve empty tokens.
         """
     ```
     The Tier 1 deterministic filter uses simple regex scanning (`\[slug:([a-z0-9_.]+)\]`): if the cited slug does not exist in `low/*.pyi`, the blame is immediately rejected with zero token consumption: `UNGROUNDED_SPEC_SLUG_NOT_FOUND`.

2. **The Ideal Non-Contaminating Blame Currency ($\mathcal{I}(P; V \mid \text{Blame}) = 0$)**:
   - The information embargo strictly prohibits the auditor from leaking test details to the library worker (no `test_parse_delims`, no test line numbers, no assertion expressions).
   - If the auditor is stripped of test artifacts, what high-resolution identifier can it safely provide?
   - **Contract slugs are the exact shared, non-contaminating tokens.**
     - *Leaking Blame*: `"In test_split_empty_delim line 44, assert s.split('a', '') == [] failed with ValueError"` ($\mathcal{I} > 0$, severe test leakage).
     - *Slug-Grounded Blame*: `"In split(), violated [slug:string.split.empty_delimiter]: expected ValueError, but returned []"` ($\mathcal{I} = 0$, zero leakage, 100% diagnostic clarity).

3. **Defeating the Hallucination Echo Chamber (Anti-Echoing Firebreak)**:
   - When tests are tagged with matching comment slugs (`# [slug:string.split.empty_delimiter]`), cross-checking test assertions against specifications becomes trivial:
     - The filter agent compares the failing test assertion directly against the slug's postcondition in `low/*.pyi`.
     - If the test author asserted an outcome contradictory to the slug (e.g. test asserts `[]`, but slug mandates `ValueError`), the filter catches the test author's cognitive error instantly.
     - The filter refuses to echo the test author's misunderstanding to `lib/*.py`, automatically re-attributing blame to `tests/*_test.py`.

4. **The Anti-Pruning Shield**:
   - Coverage auditors frequently claim that defensive branches handling edge cases (e.g. empty intervals, wildcard tokens `*`, `x`) are "dead code" because existing tests do not hit them.
   - When low-level specifications declare slugs for these edge cases (e.g. `[slug:semver.range.wildcard_star]`), the filter verifies that the uncovered library branch directly corresponds to a declared specification slug.
   - The filter instantly rejects pruning:
     `"Rejected: Uncovered branch implements valid contract [slug:semver.range.wildcard_star]. Blame tests to add test coverage for this slug rather than deleting library code."`

### Invariant 2: Cognitive Independence & Anti-Echoing Firewall
- The auditor's claim must be evaluated independently against the ground-truth specification.
- If a test author asserts unmandated behavior, the defect belongs to the test author (`tests/`), **never** to the library (`lib/`).
- The feedback filter must verify the **Target Disparity Invariant**: while `check_files` runs against `lib/`, the defect is attributed to the test file whenever the test asserts uncontracted conditions or fails in mock setup (`LifecycleResolutionError`).

### Invariant 3: Physical Information Embargo ($\mathcal{I}(P; V \mid \text{Blame}) = 0$)
- **Mutual Information Zero**: The critique must convey zero bits of information regarding the companion workspace's internal realization.
- **Self-Targeted Line Number Purity Principle**:
  - Providing exact file and line number information for the **file owned by the subagent being blamed** is explicitly encouraged and completely non-contaminating. Because the subagent already owns and edits that file in its workspace, line numbers within its own file provide maximum diagnostic resolution without leaking foreign context.
  - Citing line numbers or file paths of the **companion file** (the file across the boundary fence) is strictly prohibited.
- **Asymmetric Symbol Fencing**:
  - **Blame directed to `lib/*.py`**: May cite line numbers and function names strictly in `lib/*.py`. Must NEVER contain test function names (`test_*`), test class names, test file paths, test line numbers, assertion expressions (`assert x == y`), or test-specific mock setup details.
  - **Blame directed to `tests/*_test.py` or `pretense/*_pretense.py`**: May cite line numbers and test names strictly in `tests/*_test.py`. Must NEVER contain private library identifiers (matching regex `\b_[a-zA-Z0-9_]+\b`), internal library fields, private helper names, library file paths, or library line numbers.
  - **Deterministic Line Boundary Enforcement**: Line numbers must refer exclusively to the file being blamed and must fall within valid bounds: $1 \le \text{start\_line} \le \text{end\_line} \le \text{len}(\text{blamed\_file})$. Any foreign file path or foreign `.py:\d+` pattern triggers immediate rejection.

### Invariant 4: Anti-Pruning & Defensive Code Preservation
- Uncovered statements in `lib/` representing input validation, defensive guards, or boundary handling that fall within the valid input domain defined by `low/*.pyi` must be blamed to **tests** to provide coverage.
- Blaming `lib/` to delete code as "dead/unreachable" is permitted **only** when the span is provably unreachable under any conforming public API sequence (e.g., unreachable following an unconditional exception or structurally mutually exclusive conditionals).

### Invariant 5: Non-Prescriptive Formatting & Context Budget Protection
- The critique must be strictly diagnostic: stating **what** contracted postcondition or invariant was violated, not **how** to write the code.
- Format is strictly a single unbroken paragraph with **zero newline characters** (`\n`, `\r`).
- Length must not exceed `max_feedback_chars` (default: 1000 characters; target: ~120 words).
- No code snippets, no markdown code blocks, no diffs, and no list items.

---

## 4. Subagent Requirements Specification

### Functional Requirements

1. **FR-1: Blame Interception**: Intercept all invocations of `bin/blame` before in-band metadata or blame buffers are modified.
2. **FR-2: Zero-Token Pre-Validation**: Deterministically evaluate syntactic, length, formatting, and regex constraints using AST and lexical scanning before invoking an LLM.
3. **FR-3: Semantic Grounding Audit**: Verify that the critique references contracted terms in `low/*.pyi` and does not demand uncontracted behavior.
4. **FR-4: Cross-Artifact Leakage Detection**: Cross-reference the critique text against an extracted symbol table of private identifiers from the companion file.
5. **FR-5: Dynamic Sanitization (Rephrasing)**: When a critique contains valid defect insight but accidentally includes leaking line numbers or minor formatting defects, automatically rephrase the critique into a clean, compliant single paragraph.
6. **FR-6: Authoritative Rejection & Culprit Re-Attribution**: When a critique is fundamentally flawed (e.g., blaming `lib` for a test flaw, or demanding deletion of defensive code), reject the blame submission with an actionable error message back to the auditor, instructing it to blame the correct culprit.

### Input Boundary & Visibility Matrix

The Feedback Filter Subagent requires a strictly controlled visibility window:

| Artifact | Filter Subagent Visibility | Purpose |
| :--- | :--- | :--- |
| **Culprit File** (Blamed Target) | Full Read | Validate referenced lines and functions exist in the blamed target. |
| **Specification** (`low/*.pyi` or `high/*.md`) | Full Read | Single source of truth for contracted postconditions and slugs. |
| **Companion File** (Opposite side) | **AST Symbol Table Only** | Extract private symbols (`_*`), test names (`test_*`), and public API names to detect leakage, without passing whole file text. |
| **Auditor Diagnostic Output** (pytest/pyright) | Read | Contextual evidence of what error triggered the auditor's round. |
| **Raw Critique String** | Full Read | Candidate feedback to inspect and filter. |

### Decision Protocol & Verdict Schema

The subagent produces a structured JSON verdict conforming to `FeedbackVerdict`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "FeedbackVerdict",
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["ACCEPTED", "REPHRASED", "REATTRIBUTED", "REJECTED"]
    },
    "culprit_file": {
      "type": "string",
      "description": "The validated target file receiving blame."
    },
    "sanitized_critique": {
      "type": "string",
      "description": "The approved, non-contaminating, spec-grounded single-paragraph critique."
    },
    "rejection_reason": {
      "type": "string",
      "description": "Diagnostic error delivered to the auditor if rejected."
    },
    "violations": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of specific invariant codes violated (e.g. LEAK_PRIVATE_SYMBOL, UNGROUNDED_SPEC)."
    }
  },
  "required": ["status", "culprit_file", "sanitized_critique"]
}
```

### Performance, Latency & Economic Budgets

- **Execution Latency**:
  - Deterministic rejection (Tier 1): $< 50\text{ ms}$.
  - Subagent semantic filtering (Tier 2): $\le 2.0\text{ s}$.
- **Token Budget**:
  - Input context: $\le 2,500$ tokens (concise system prompt + specification stub + AST symbol list + critique).
  - Output completion: $\le 250$ tokens (structured JSON verdict).
- **Cost Allocation**: Evaluated using Tier 2 Budget Cloud (Gemini 3.8 Flash / DeepSeek V4.1 Flash) at $<\$0.001$ per invocation.

---

## 5. Comparative Analysis of Architectural Solutions

We evaluate three potential architectural placements for the feedback filtering subagent:

```
Option A: In-Line Synchronous Gate (bin/blame)
  Auditor ──► bin/blame ──► [Feedback Firewall] ──► Metadata (Approved)
                                  │ (Rejected)
                                  └──► Error to Auditor

Option B: Wave-Boundary Coordinator Mediation
  Auditor ──► Buffer ──► Coordinator Wave ──► [Filter Subagent] ──► Inject to Worker

Option C: Dedicated Methodology Role in DAG
  Auditor (QA) ──► Feedback_QA Node ──► Lib / Test
```

### Option A: Synchronous In-Line Interception in `bin/blame`
- **Mechanism**: `bin/blame` executes the Two-Tier Firewall directly in-process before updating metadata or the workspace blame buffer.
- **Pros**:
  - Immediate, synchronous feedback to the auditor: if the auditor violates rules, `bin/blame` returns non-zero with an actionable diagnostic.
  - Prevents bad state from ever reaching git history or shared workspace buffers.
  - Seamlessly integrates with both subagent-driven (Option 4) and subagentless (Option 3) workflows.
- **Cons**:
  - Requires subagent spawning capability or fast API invocation inside the role workspace CLI environment.

### Option B: Asynchronous Wave-Boundary Mediation in Coordinator
- **Mechanism**: The auditor records raw blame to `.autofab_blame_buffer.json` and concludes its round. When the top-level Coordinator calculates the next wave, it audits all pending blame buffers using a filter subagent before provisioning workspaces.
- **Pros**:
  - Completely decouples workspace execution from subagent invocation; coordinator runs the filter in its own context.
  - Enables cross-target holistic analysis if multiple nodes were blamed simultaneously.
- **Cons**:
  - When blame is rejected, the auditor has already concluded its round! The coordinator must re-commission the auditor in a subsequent round, doubling wave churn and latency.

### Option C: Dedicated Intermediate Methodology Role (`feedback_qa`)
- **Mechanism**: Add a first-class node in `autofab_roles.toml` (`lib` $\to$ `qa` $\to$ `feedback_qa`).
- **Pros**:
  - Follows standard DAG scheduling.
- **Cons**:
  - Severe orchestration overhead: introduces a mandatory extra round to every cleaning pipeline even when blame is trivial or absent, exploding token usage.

### Evaluation Matrix & Selection

| Criterion | Option A (In-Line Gate) | Option B (Wave Boundary) | Option C (DAG Role) |
| :--- | :---: | :---: | :---: |
| **Immediate Error Correction** | **Optimal** (instant in-round) | Poor (requires extra wave) | Poor (extra DAG node) |
| **Token Economy** | **Optimal** (only runs on blame) | Good (runs on blame) | Catastrophic (runs always) |
| **Convergence Speed** | **Fastest** (0 wave delay) | Slow (1 wave delay on error) | Slowest (+1 wave per turn) |
| **Isolation Preservation** | **100% Hermetic** | 100% Hermetic | 100% Hermetic |
| **Implementation Complexity** | Moderate | Moderate | High |

**Selection**: **Option A (Synchronous In-Line Interception with Two-Tiered Firewall)** is selected as the primary architecture, with graceful fallback to Option B if a role workspace lacks direct LLM endpoint credentials.

---

## 6. Recommended Solution: Two-Tiered Hybrid "Feedback Firewall"

```
                       bin/blame <culprit> "<critique>"
                                      │
                                      ▼
             ┌─────────────────────────────────────────────────┐
             │       TIER 1: Zero-Token Static Pre-Filter      │
             │ - Check single paragraph (no \n, \r)            │
             │ - Check max length (<= max_feedback_chars)      │
             │ - Regex scan for private symbols (_*)           │
             │ - Regex scan for test names in lib blame        │
             │ - Verify file paths & target existence          │
             └────────┬───────────────────────────────┬────────┘
                      │ (Violations detected)         │ (Passed mechanical checks)
                      ▼                               ▼
             ┌─────────────────┐             ┌───────────────────────────────────┐
             │ Rejection /     │             │ TIER 2: Semantic Subagent Arbiter │
             │ Auto-Normalize  │             │ (Gemini 3.8 Flash / DeepSeek)     │
             └─────────────────┘             │ - Grounding against low/*.pyi     │
                                             │ - Anti-Echoing check              │
                                             │ - Anti-Pruning verification       │
                                             │ - Target Disparity validation     │
                                             └─────────────────┬─────────────────┘
                                                               │
                         ┌─────────────────────────────────────┴─────────────────────────────────────┐
                         ▼                                     ▼                                     ▼
                ┌─────────────────┐                  ┌────────────────────┐                ┌──────────────────┐
                │ Status: ACCEPT  │                  │ Status: REPHRASED  │                │ Status: REJECT   │
                │ Write Metadata  │                  │ Write Sanitized    │                │ Exit 1 with      │
                │ & Blame Buffer  │                  │ Text to Metadata   │                │ Diagnostic Error │
                └─────────────────┘                  └────────────────────┘                └──────────────────┘
```

### Tier 1: Zero-Token Deterministic Static Pre-Filter

Before invoking any LLM API, `bin/blame` passes the critique through a deterministic Python verification pipeline:

1. **Newline Normalization & Rejection**:
   - Detects `\r` and `\n`. If present, automatically joins single lines or rejects multi-paragraph structures.
2. **Length Guard**:
   - Asserts $\text{len}(\text{critique}) \le \text{max\_feedback\_chars}$.
3. **Target Disparity Static Check**:
   - If caller is `coverage` or `pretense_coverage` and all uncovered lines are marked `[LIB-PRAGMA-REQUIRED]` (e.g. `raise *Error`), asserting blame against `tests/` is rejected immediately with:
     `"Error: misattribution: no test-owned spans in this deficit. Blame the library module."`
4. **Repetitive Blame Buffer Check**:
   - Compares candidate critique and missing spans against `.autofab_blame_buffer.json`. If the exact same span was already blamed without changes, rejects immediately to prevent infinite ping-pong.
5. **Static Symbol Embargo Scan**:
   - Scans the critique for private identifiers of the companion file.
   - For blame targeting `lib/*.py`: Checks regex `\btest_[a-zA-Z0-9_]+\b`, `\bTestCase\b`, `\bassert\b`, and `.py:\d+` referencing test files.
   - For blame targeting `tests/*_test.py`: Extracts all private symbols (`_foo`, `__bar`) from the companion `lib/*.py` AST and flags any direct mentions.

### Tier 2: Semantic Subagent Arbiter (`feedback_filter`)

When Tier 1 passes, the critique is submitted to the lightweight `feedback_filter` subagent. The subagent evaluates three semantic gates:

#### Gate 1: Specification Grounding Gate
- **Prompt Verification**: Does the critique reference an actual method, postcondition, invariant, or contract slug declared in `low/*.pyi`?
- If the auditor demands behavior explicitly contradictory to the specification (or absent from the spec closure), the critique is rejected as `UNGROUNDED_SPEC_DEMAND`.

#### Gate 2: Anti-Echoing & Target Disparity Gate
- **Analysis**: Did the test fail because the library violated `low/*.pyi`, or because the test asserted an uncontracted condition or failed in mock collaborator registration (`LifecycleResolutionError`)?
- If the test author asserted uncontracted behavior and the auditor blamed `lib`, the subagent issues verdict `REATTRIBUTED`, switching the culprit to `tests/*_test.py` and updating the feedback to explain the test author's overreach.

#### Gate 3: Anti-Pruning & Defensive Integrity Gate
- If the auditor claims library code is "dead" or "unreachable", the subagent inspects the method signature and preconditions in `low/*.pyi`.
- If the input domain permits the data leading to that branch, the subagent rejects pruning:
  `"Rejected: Input space is valid under low/*.pyi. Blame the test author to add test coverage instead of deleting library defensive logic."`

### Rejection, Re-Prompting & Remediation Flow

When the Feedback Firewall rejects a blame submission:
1. `bin/blame` exits with code `1` and prints a structured error banner:
   ```
   [FEEDBACK REJECTED BY EMBARGO FIREWALL]
   Culprit: lib/version_parser.py
   Violation: LEAK_TEST_ASSERTION, UNGROUNDED_SPEC
   Diagnostic: Your critique references 'assert v.major == 1' and demands returning None for empty strings, which contradicts low/version_parser.pyi Section 2.1 (EmptyInputError required).
   Action Required: Re-read low/version_parser.pyi and re-attribute blame to tests/version_parser_test.py for asserting uncontracted behavior.
   ```
2. The auditor's active tool call fails cleanly, allowing the LLM in its current round to adjust its reasoning, formulate a compliant blame critique, or switch culprits without tripping the unhandled exception circuit breaker.

---

### Subagent Prompt Engineering & Structured JSON Protocol

The `feedback_filter` subagent runs with the following system prompt and user template:

#### System Prompt (`autofab_feedback_filter_prompt`)
```markdown
You are the Autofab Feedback Embargo & Grounding Arbiter.
Your sole responsibility is to evaluate blame critiques submitted by auditor subagents (QA, Coverage, Spec QA) before they are injected into repository metadata.

You must strictly enforce five core invariants:
1. SPECIFICATION GROUNDING: The critique must be rooted in the low-level specification (contracts, invariants, preconditions, postconditions, or contract slugs). Demands for uncontracted behavior, stylistic preferences, or arbitrary error wording must be REJECTED.
2. ANTI-ECHOING (TARGET DISPARITY): If a test failed because the test author asserted uncontracted behavior, failed to register mocks (LifecycleResolutionError), or misread the specification, blaming the library is FORBIDDEN. You must REATTRIBUTE blame to the test file.
3. INFORMATION EMBARGO:
   - When blaming lib/*.py: Must NEVER mention test names (test_*), test line numbers, test assertions, or mock mechanics.
   - When blaming tests/*_test.py: Must NEVER mention private library symbols (_*), internal variables, helper methods, or library line numbers.
   - Line numbers are permitted ONLY for the file being blamed.
4. ANTI-PRUNING: Demanding that library code be deleted as "dead code" is FORBIDDEN if the branch handles valid inputs permitted by the specification. Deficits on valid inputs must be blamed to tests for missing coverage.
5. NON-PRESCRIPTIVE FORMAT: The output critique must be a single unbroken paragraph with ZERO newlines and under 1000 characters, describing WHAT contract requirement is unfulfilled, never prescribing code diffs.

You must output strictly a JSON object conforming to the FeedbackVerdict schema.
```

#### User Prompt Template
```json
{
  "caller_role": "{caller_role}",
  "blamed_file": "{blamed_file}",
  "companion_file": "{companion_file}",
  "companion_private_symbols": {companion_private_symbols},
  "specification_stub": "{specification_stub}",
  "auditor_diagnostic_summary": "{auditor_diagnostic_summary}",
  "raw_critique": "{raw_critique}"
}
```

---

## 7. The Structured Blame Tuple & Violation Slug Grammar

### The Zero-Entropy Information Theory Principle

The root cause of boundary contamination, prescriptive code leaks, and hallucination echoing is **unconstrained natural language**. Natural language has high semantic entropy; models prompted to give diagnostic feedback reflexively emit conversational filler, quote private variables from open buffers, or invent uncontracted advice.

By replacing free-form natural language with a **Structured Blame Tuple** parameterized by **Contract Slugs**, **Violation Class Slugs (`[viol:...]`)**, **Constrained Noun Phrase Facets**, **Bare Witness Literals**, and **Self-Targeted Line Numbers**, the communication channel bandwidth is strictly bounded:

$$\text{Blame Tuple} = \langle \text{TargetFile}, \text{SpecSlug}, \text{ViolationSlug}, \text{NounPhraseFacet}, \text{BareWitness}, \text{SelfTargetLineRange} \rangle$$

$$\mathcal{I}(P; V \mid \text{Blame Tuple}) = 0$$

Because the vocabulary is restricted to declared slugs, short noun phrases, bare input/output literals, and file line numbers of the **file owned by the subagent being blamed**, **it is mathematically impossible for an auditor to leak private symbols, test function names, or mock structures across the fence.**

---

### Taxonomy of Violation Class Slugs

Violation classes are strictly partitioned by target responsibility and auditor authority across the five auditor roles:

```
                                  VIOLATION SLUG TAXONOMY ACROSS AUDITOR TYPES
  ┌─────────────────────────┬─────────────────────────┬─────────────────────────┬─────────────────────────┬─────────────────────────┐
  │ QA Auditor              │ Coverage Auditor        │ Spec QA Arbiter         │ Pretense QA Auditor     │ Pretense Coverage       │
  │ (qa -> lib / tests)     │ (coverage -> tests/lib) │ (spec_qa -> low/plan)   │ (pretense_qa -> pret/lib│ (pretense_cov -> pret/lib│
  ├─────────────────────────┼─────────────────────────┼─────────────────────────┼─────────────────────────┼─────────────────────────┤
  │ [viol:post.wrong_return]│ [viol:cov.missing_test] │ [viol:spec.ambiguous]   │ [viol:pret_qa.falsified]│ [viol:pret_cov.gap]     │
  │ [viol:post.wrong_type]  │ [viol:cov.missing_part] │ [viol:spec.untyped_arg] │ [viol:pret_qa.uncontract│ [viol:pret_cov.fuzz]    │
  │ [viol:pre.missing_error]│ [viol:cov.missing_bound]│ [viol:spec.missing_err] │ [viol:pret_qa.inv_miss] │ [viol:pret_cov.seed]    │
  │ [viol:pre.unexp_error]  │ [viol:cov.unreachable]  │ [viol:spec.conjunction] │ [viol:pret_qa.mock_miss]│ [viol:pret_cov.no_rule] │
  │ [viol:inv.state_corrupt]│ [viol:cov.pragma_miss]  │ [viol:spec.drift_plan]  │ [viol:post.wrong_return]│ [viol:cov.unreachable]  │
  │ [viol:test.unmandated]  │                         │                         │ [viol:inv.state_corrupt]│ [viol:cov.pragma_miss]  │
  │ [viol:test.uncontracted]│                         │                         │                         │                         │
  │ [viol:test.wording_chk] │                         │                         │                         │                         │
  │ [viol:test.mock_missing]│                         │                         │                         │                         │
  └─────────────────────────┴─────────────────────────┴─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

#### 1. QA Auditor Violations (`qa`)

The QA Auditor evaluates unit test executions against the Low-Level Specification (`low/*.pyi`). Its authority is bidirectional:

##### Targeting Implementation (`qa -> lib/*.py`):
- `[viol:post.wrong_return]`: Operation returned a value contradicting the contracted postcondition (e.g. inverted boolean, off-by-one sort, incorrect collection element).
- `[viol:post.wrong_type]`: Return value type violates the declared type annotation in `low/*.pyi` (e.g. returning `list` instead of `tuple`, `int` instead of `float`).
- `[viol:post.contract_omitted]`: A mandated postcondition side effect was not applied (e.g. cache recency not updated, state flag left unchanged).
- `[viol:pre.missing_error]`: Method failed to raise the mandated exception class when given input that violates a contracted precondition (`WHEN ... MUST raise ...Error`).
- `[viol:pre.unexpected_error]`: Method raised an uncontracted exception (`AttributeError`, `IndexError`, `KeyError`, or internal crash) on valid, specification-conforming inputs.
- `[viol:inv.state_corrupted]`: Object invariant declared under `INVARIANTS:` in `low/*.pyi` was violated following method completion.
- `[viol:perf.deadlock_timeout]`: Method entered an infinite loop, livelock, or exceeded execution timeout limit (`--timeout=45`).

##### Targeting Test Suite (`qa -> tests/*_test.py`):
- `[viol:test.unmandated_behavior]`: Test asserts an arbitrary requirement or restriction not present in `low/*.pyi` (e.g. asserting internal variable presence, demanding specific ordering where spec specifies unordered set).
- `[viol:test.uncontracted_precondition]`: Test asserts specific behavior on uncontracted inputs (undefined behavior) rather than testing contracted domains.
- `[viol:test.exact_wording_asserted]`: Test asserts exact exception message string instead of verifying exception type and structured attributes (violates `MESSAGE_INVARIANCE` rule).
- `[viol:test.mock_unregistered]`: Test crashed with `LifecycleResolutionError` because it failed to register a mock instance in `setUp` via `self.registry.register_instance`.
- `[viol:test.precondition_violated]`: Test passed illegal inputs into a library function without using `assertRaises(...)`, causing an expected `*Error` to escape and fail the test run.
- `[viol:test.unstable_ordering]`: Test asserts equality on dictionaries or sets whose iteration order is not guaranteed by specification.

---

#### 2. Coverage Auditor Violations (`coverage`)

The Coverage Auditor analyzes statement and branch deficits reported by `coverage.py`. It enforces full postcondition exercising without allowing pruning of defensive code:

##### Targeting Test Suite (`coverage -> tests/*_test.py`):
- `[viol:cov.missing_test_branch]`: A valid public contract branch or conditional path in `lib/*.py` has zero test executions exercising it.
- `[viol:cov.missing_equivalence_partition]`: A distinct input equivalence partition (e.g. numeric prereleases, empty string, boundary zero) is unexercised.
- `[viol:cov.missing_boundary_endpoint]`: Boundary edge cases (e.g. empty collections, minimum/maximum capacity limits, 0-major version ranges) are not asserted.
- `[viol:cov.missing_contract_slug]`: A specification slug declared in `low/*.pyi` has zero corresponding `# [slug:...]` assertions in the test suite.

##### Targeting Implementation (`coverage -> lib/*.py`):
- `[viol:cov.unreachable_under_spec]`: Uncovered library code represents dead logic or defensive code that is structurally unreachable through public APIs; library author must restructure or annotate with `# pragma: no cover (assumption: <reason>)`.
- `[viol:cov.defensive_pragma_missing]`: Precondition verification guards (`if not valid: raise *Error`) lack the required `# pragma: no cover (assumption: precondition enforced by caller)`.

---

#### 3. Spec QA Arbiter Violations (`spec_qa`)

The Spec QA Arbiter reviews Low-Level Specifications (`low/*.pyi`) and Planning documents (`planning/*.md`) against upstream High-Level Specifications (`high/*.md`):

##### Targeting Low-Level Specification (`spec_qa -> low/*.pyi`):
- `[viol:spec.ambiguous_contract]`: Postcondition or precondition uses vague prose lacking concrete, falsifiable mathematical conditions.
- `[viol:spec.untyped_parameter]`: Method signature lacks strict type hints, return annotations, or dataclass attributes.
- `[viol:spec.missing_error_type]`: Docstring mandates exception raising without defining the corresponding `@dataclass` exception class in the file.
- `[viol:spec.compound_conjunction]`: Postcondition combines multiple orthogonal requirements into a single clause using conjunctions (`and`, `also`, `as well as`), violating the Zero-Conjunction Rule.
- `[viol:spec.drift_from_planning]`: Low-level interface omits, alters, or invents methods not contracted in `planning/*.md`.

##### Targeting Planning Document (`spec_qa -> planning/*.md`):
- `[viol:plan.unaligned_with_high]`: Planning step drops or contradicts requirements established in `high/*.md`.
- `[viol:plan.epistemic_drift]`: Planning step prescribes low-level implementation details (internal variables, private functions) instead of architectural component responsibilities.

---

#### 4. Pretense QA Auditor Violations (`pretense_qa`)

The **Pretense QA Auditor** evaluates property-based testing and state machine simulations against library implementations using the Pretense framework.

##### Verification Engine & Execution Oracle
- **Primary Tool**: `uv run pretense <target_file>`
- **Core Mission**: **Dynamic falsification, counterexample extraction, and contract invariant preservation** across randomized and stateful execution sequences generated by Hypothesis `RuleBasedStateMachine`.
- **Verification Plane**: Pretense QA operates on dynamic property verification, hunting for assertion failures, state divergence, and unhandled exceptions. It does **not** evaluate code coverage, line counts, or branch metrics.

##### Target Disparity & Root-Cause Attribution
The verification target presented to `bin/check_files` is typically `lib/<name>.py`, but verification actually executes companion state machines (`pretense/<name>_pretense.py`). When an execution fails:
1. **Library Culprit (`lib/*.py`)**: If the state machine executed a valid, specification-compliant sequence of operations and parameter inputs, but the library returned an invalid value or left object state corrupted:
   - Blame is attributed to `lib/*.py`.
2. **Pretense Culprit (`pretense/*_pretense.py`)**: If the test failure was caused by the state machine defining an uncontracted state rule, violating an uncontracted precondition, asserting an uncontracted invariant, or failing in mock collaborator setup:
   - Blame is attributed to `pretense/*_pretense.py`.

##### Pretense QA Violation Slugs:
###### Targeting Implementation (`pretense_qa -> lib/*.py`):
- `[viol:pret_qa.falsified_property]`: State machine step sequence discovered a concrete counterexample disproving a contracted postcondition or interface property.
- `[viol:post.wrong_return]`: Library method returned an incorrect value or data type during a valid state machine step.
- `[viol:inv.state_corrupted]`: Object invariant declared under `INVARIANTS:` in `low/*.pyi` failed following a randomized sequence of operations.
- `[viol:pre.missing_error]`: Method failed to raise the mandated exception class when a state machine rule supplied invalid input violating a contracted precondition.
- `[viol:pre.unexpected_error]`: Method crashed with an uncontracted exception on valid randomized inputs generated within the specification domain.

###### Targeting Pretense State Machine (`pretense_qa -> pretense/*_pretense.py`):
- `[viol:pret_qa.uncontracted_state_rule]`: State machine rule asserts outputs or transitions not mandated by `low/*.pyi`.
- `[viol:pret_qa.invalid_rule_precondition]`: Rule `precondition(...)` guard permits states or inputs that violate interface preconditions, causing an expected `*Error` to crash the test.
- `[viol:pret_qa.mock_unregistered]`: State machine rule or `initialize()` hook crashed with `LifecycleResolutionError` due to missing mock instance registration.
- `[viol:pret_qa.invariant_omitted]`: A crucial specification invariant declared in `low/*.pyi` is omitted from `@invariant()` assertions.
- `[viol:pret_qa.flaky_state_machine]`: State machine produces non-deterministic failures due to unseeded pseudo-random state, external environment dependencies, or mutable global state leakage.

---

#### 5. Pretense Coverage Arbiter Violations (`pretense_coverage`)

The **Pretense Coverage Arbiter** evaluates state-space exploration completeness, rule-matrix reachability, and code coverage achieved by property-based state machines.

##### Verification Engine & Execution Oracle
- **Primary Tool**: `coverage run -m pretense <target_file>` followed by statement and branch analysis.
- **Core Mission**: **State-space exploration completeness, transition graph connectivity, Hypothesis strategy generation boundaries, and collaborator seeding completeness**.

##### Strict Separation from Pretense QA
- **Pretense QA** asks: *"Did the executed state transitions discover a bug in the code or in the property definition?"* (Correctness & Falsification).
- **Pretense Coverage** asks: *"Did the state machines thoroughly exercise all specification-contracted states, operations, and branch boundaries?"* (Completeness & State-Space Exploration).

##### Anti-Pruning & Defensive Integrity Invariant
- Pretense Coverage is **strictly prohibited from directing library authors to delete defensive branches** as "unreachable" if those branches handle valid input states permitted by `low/*.pyi`.
- If a valid specification condition in `lib/*.py` is unexercised, Pretense Coverage **must blame `pretense/*_pretense.py`** to add the missing rule, expand its Hypothesis strategy, or provide collaborator seeding.

##### Pretense Coverage Violation Slugs:
###### Targeting Pretense State Machine (`pretense_coverage -> pretense/*_pretense.py`):
- `[viol:pret_cov.unexplored_state_transition]`: A public method or operation declared in `low/*.pyi` has zero corresponding `@rule` methods in the state machine.
- `[viol:pret_cov.shallow_hypothesis_strategy]`: Hypothesis parameter strategies (`st.integers()`, `st.text()`) fail to generate boundary extrema (e.g. empty strings, zero endpoints, maximum capacity).
- `[viol:pret_cov.collaborator_seeding_deficit]`: Composite state machine fails to register mock collaborators across multiple interface implementations, leaving cross-component boundary branches unexercised.
- `[viol:pret_cov.rule_graph_disconnect]`: A state machine target state cannot be reached from the initial state due to overly restrictive `precondition()` filters or dead-end transition rules.
- `[viol:pret_cov.missing_contract_slug]`: A specification slug declared in `low/*.pyi` is completely unexercised by the pretense state machine.

###### Targeting Implementation (`pretense_coverage -> lib/*.py`):
- `[viol:cov.unreachable_under_spec]`: Uncovered library code represents dead logic or defensive code that is structurally unreachable under any public API call sequence; library author must restructure or annotate with `# pragma: no cover (assumption: <reason>)`.
- `[viol:cov.defensive_pragma_missing]`: Precondition verification guards (`if not valid: raise *Error`) lack the required `# pragma: no cover (assumption: precondition enforced by caller)`.

---

### The Facet Architecture: Equivalence Partitions, Boundaries, and Constrained Noun Phrases

#### What Are Facets?

A **Facet** is an atomic attribute, input subdomain, operational branch, state trigger, or boundary condition that refines a contracted requirement without introducing natural language verbs, prescriptive advice, or boundary-crossing information leaks.

Formally, given a specification contract $\mathcal{C}$ associated with a slug $S$, the requirement partitions the input/state space $\Omega$ into equivalence classes:

$$\Omega = \bigcup_{k=1}^m \Phi_k \quad \text{where each } \Phi_k \text{ is an equivalence facet.}$$

When an auditor cites $S$, the authoring subagent needs to know **which facet $\Phi_k$** failed or lacks coverage. The facet provides this refinement cleanly:

$$\text{Blame Descriptor} = \langle \text{Target}, \text{Slug } S, \text{Violation } V, \text{Facet } \Phi_k \rangle$$

#### The 6 Canonical Facet Archetypes

Facets across all Autofab specifications fall into 6 strictly defined grammatical archetypes:

```
                                  CANONICAL FACET ARCHETYPES
  ┌──────────────────────────────┬──────────────────────────────────────────────────────────────┐
  │ Facet Archetype              │ Definition & Structural Role                                 │
  ├──────────────────────────────┼──────────────────────────────────────────────────────────────┤
  │ 1. Equivalence Partition     │ Input data class sharing identical operational behavior      │
  │ 2. Boundary / Extreme Value  │ Endpoint limits, zero values, or collection extrema          │
  │ 3. Syntax / Lexical Variant  │ Delimiter, whitespace, operator, or tokenization variation   │
  │ 4. Precondition / Error      │ Trigger condition mandating an explicit exception class      │
  │ 5. State Machine Transition  │ Operation sequencing, lifecycle stage, or temporal condition │
  │ 6. Structural Relationship   │ Dependency topology, hierarchy depth, or conflict structure  │
  └──────────────────────────────┴──────────────────────────────────────────────────────────────┘
```

##### Archetype 1: Equivalence Partition Facets
Designate a coherent subclass of inputs that must be handled uniformly:
- Examples: `numeric prerelease identifiers`, `alphanumeric prerelease identifiers`, `multilevel transitive packages`, `case-insensitive headers`.

##### Archetype 2: Boundary & Extreme Value Facets
Designate edge conditions, zero endpoints, or capacity extrema:
- Examples: `zero major version (^0.x.y)`, `zero major and minor (^0.0.z)`, `maximum buffer capacity`, `empty string input`.

##### Archetype 3: Syntax & Lexical Variant Facets
Designate tokenization variants, optional whitespace, or formatting alternatives permitted by grammar:
- Examples: `embedded operator whitespace (>= 1.0.0)`, `tilde on partial version (~1.2.x)`, `inclusive hyphen range endpoints`, `comma-separated comparator rejection`.

##### Archetype 4: Precondition & Error Trigger Facets
Designate invalid states or illegal inputs that mandate explicit error raising:
- Examples: `leading zeros in numeric segment`, `bare partial version without wildcard`, `unregistered package reference`, `circular dependency cycle`.

##### Archetype 5: State Machine Transition Facets
Designate object lifecycle phases, mutation recency, or order preservation:
- Examples: `buffer wrap-around on full capacity`, `eviction of oldest unreferenced key`, `re-insertion of existing key updates recency`, `fifo dequeue order`.

##### Archetype 6: Structural & Relational Facets
Designate topological or compositional arrangements:
- Examples: `unresolvable conflicting constraints`, `forward-checking candidate rejection`, `transitive constraint rollback on backtrack`, `diamond dependency resolution`.

---

#### Noun Phrase Grammatical Constraints

Facets are **strictly constrained to pure noun phrases**:
1. **Zero Verbs or Imperatives**: Words such as `change`, `fix`, `add`, `assert`, `check`, `modify`, `use`, `return`, `delete`, `replace` are **strictly forbidden**.
2. **Length Caps**: Maximum $\le 8$ words and $\le 60$ characters.
3. **Domain Vocabulary Only**: Must describe entities and states from the specification domain, never mentioning file names, test names (`test_*`), line numbers, or private symbols (`_*`).

```
  CORRECT (Pure Noun Phrase Facets):
  ✔ "numeric prerelease identifiers"
  ✔ "embedded operator whitespace"
  ✔ "zero major version boundary"
  ✔ "unregistered package reference"
  ✔ "consecutive empty delimiters"

  INCORRECT (Violates Noun Phrase Constraints):
  ✘ "fix the parser to accept whitespace" (Contains verb 'fix')
  ✘ "assert that ^0.2.3 handles zero" (Contains imperative 'assert')
  ✘ "change line 42 to use _helper" (Contains verb 'change' and private symbol '_helper')
  ✘ "tests should check for empty string" (Prescriptive sentence structure)
```

---

### Concrete Benchmark Slugs & Canonical Facet Dictionaries

To anchor experimental validation across existing benchmark suites, the following tables define the canonical **Specification Slugs** and their corresponding **Approved Facet Dictionaries**:

#### 1. `semver_solver` Specification Slugs & Facets

*Specification Source*: [`benchmarks/parts/semver_solver/low/semver_solver.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/benchmarks/parts/semver_solver/low/semver_solver.pyi)

| Contract Slug | Method / Target | Contract Requirement Summary | Canonical Facet Vocabulary |
| :--- | :--- | :--- | :--- |
| `[slug:semver.parse.grammar]` | `parse_version` | Valid SemVer 2.0.0 major.minor.patch-pre+build parsing | `numeric prerelease identifiers`, `alphanumeric prerelease identifiers`, `dot-separated prerelease segments`, `build metadata segments` |
| `[slug:semver.parse.leading_zero]` | `parse_version` | Rejection of leading zeros in numeric identifiers | `leading zero in major component`, `leading zero in minor component`, `leading zero in patch component`, `leading zero in numeric prerelease` |
| `[slug:semver.precedence.numeric_vs_alpha]` | `compare_precedence` | Numeric prereleases ranked below alphanumeric segments | `numeric prerelease segment`, `alphanumeric prerelease segment`, `numeric below string ranking`, `lexicographical ascii ranking` |
| `[slug:semver.precedence.normal_vs_prerelease]` | `compare_precedence` | Normal version ranks higher than matching prerelease | `normal version precedence advantage`, `identical major minor patch components` |
| `[slug:semver.precedence.build_metadata_ignored]` | `compare_precedence` | Build metadata ignored in precedence calculation | `identical version differing build metadata`, `build metadata ordering neutrality` |
| `[slug:semver.range.basic_comparator]` | `parse_range` | Relational operators (==, =, !=, <, <=, >, >=) | `equality comparator`, `inequality comparator`, `strict less than`, `inclusive less than`, `strict greater than`, `inclusive greater than` |
| `[slug:semver.range.caret_range]` | `parse_range` | Caret range expansion across zero/nonzero components | `nonzero major caret boundary`, `zero major caret boundary (^0.x.y)`, `zero major minor caret boundary (^0.0.z)`, `prerelease caret matching` |
| `[slug:semver.range.tilde_range]` | `parse_range` | Tilde range expansion allowing patch-level shifts | `full version tilde range`, `partial version tilde range (~1.2.x)`, `major only tilde range (~1.x)` |
| `[slug:semver.range.hyphen_range]` | `parse_range` | Hyphen ranges connecting lower and upper bounds | `inclusive full version hyphen endpoints`, `wildcard upper bound hyphen range`, `partial version hyphen range` |
| `[slug:semver.range.wildcard_expansion]` | `parse_range` | Wildcard characters (x, X, *) in major, minor, patch | `bare wildcard expression (*, 1.x)`, `double trailing wildcard (1.x.x)`, `comparator with wildcard target (<1.x)`, `unbounded comparator wildcard (<*, >=*)` |
| `[slug:semver.range.whitespace_tolerance]` | `parse_range` | Optional whitespace between operator and operand | `embedded operator whitespace (>= 1.0.0)`, `embedded prefix whitespace (~ 1.2)`, `whitespace-delimited comparators` |
| `[slug:semver.range.bare_partial_rejected]` | `parse_range` | Rejection of partial versions lacking wildcards | `bare partial major ('1')`, `bare partial major minor ('1.2')`, `comparator on bare partial ('>1.2')`, `bare partial hyphen range ('1.2 - 2.3')` |
| `[slug:semver.range.union_or]` | `parse_range` | Alternatives combined via '\|\|' delimiter | `disjoint range union clauses`, `overlapping range union clauses`, `whitespace trimmed around union clauses` |
| `[slug:semver.satisfies.prerelease_filtering]` | `satisfies` | Pre-release satisfaction with include_prerelease | `prerelease exclusion by default`, `explicit prerelease inclusion flag`, `prerelease matching exact prerelease constraint` |
| `[slug:semver.repo.precedence_sorted]` | `PackageRepository` | Package releases retrieved in descending precedence | `descending precedence ordering`, `latest version retrieval`, `empty repository lookup` |
| `[slug:semver.repo.package_not_found]` | `PackageRepository` | PackageNotFoundError raised on nonexistent package | `unregistered package name lookup`, `case-sensitive package name mismatch` |
| `[slug:semver.solver.mrv_ordering]` | `DependencySolver` | Minimum Remaining Values variable ordering | `mrv variable heuristic`, `descending value heuristic`, `deterministic tie breaking` |
| `[slug:semver.solver.forward_checking]` | `DependencySolver` | Incompatible candidate pruned during forward check | `forward checking constraint contradiction`, `candidate rejection before subtree exploration`, `single candidate domain` |
| `[slug:semver.solver.backtracking_undo]` | `DependencySolver` | Constraint state restoration on candidate backtrack | `undoing newly introduced constraints`, `restoring previous package constraint trail`, `alternative lower release selection` |
| `[slug:semver.solver.conflict_resolution_error]` | `DependencySolver` | ResolutionConflictError on mutually unsatisfiable trees | `exhausted candidate domain`, `unregistered transitive package error containment`, `conflicting packages reporting in exception` |

---

#### 2. `ring_buffer` Specification Slugs & Facets

*Specification Source*: [`benchmarks/parts/ring_buffer/low/ring_buffer.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/benchmarks/parts/ring_buffer/low/ring_buffer.pyi)

| Contract Slug | Method / Target | Contract Requirement Summary | Canonical Facet Vocabulary |
| :--- | :--- | :--- | :--- |
| `[slug:ring_buffer.init.capacity]` | `__init__` | Non-negative integer capacity allocation | `positive integer capacity allocation`, `zero capacity allocation`, `invalid negative capacity error` |
| `[slug:ring_buffer.push.overwrite]` | `push` | Ring buffer overwrite on full capacity | `push on non-full buffer`, `overwrite oldest element on full capacity`, `head pointer advance on overwrite` |
| `[slug:ring_buffer.pop.fifo_order]` | `pop` | FIFO element extraction from buffer | `fifo element extraction order`, `length decrement on pop`, `tail pointer advance` |
| `[slug:ring_buffer.pop.empty_error]` | `pop` | BufferEmptyError raised when popping empty buffer | `pop on initially empty buffer`, `pop on fully drained buffer` |
| `[slug:ring_buffer.peek.non_mutating]` | `peek` | Inspect oldest element without mutation | `oldest element inspection`, `unmodified buffer length after peek`, `empty buffer peek error` |
| `[slug:ring_buffer.iter.oldest_to_newest]` | `__iter__` | Iterator yield from oldest to newest element | `iteration sequence oldest to newest`, `iterator isolation from concurrent mutations`, `empty buffer iteration` |
| `[slug:ring_buffer.invariants.len_le_capacity]` | Invariants | Element count strictly bounded by capacity | `element count bounded by capacity`, `empty buffer zero length invariant`, `full buffer maximum length invariant` |

---

#### 3. `lru_cache` Specification Slugs & Facets

*Specification Source*: [`benchmarks/parts/lru_cache/low/lru_cache.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/benchmarks/parts/lru_cache/low/lru_cache.pyi)

| Contract Slug | Method / Target | Contract Requirement Summary | Canonical Facet Vocabulary |
| :--- | :--- | :--- | :--- |
| `[slug:lru_cache.init.capacity]` | `__init__` | Positive integer capacity configuration | `positive integer capacity`, `zero or negative capacity error` |
| `[slug:lru_cache.get.hit_updates_recency]` | `get` | Cache hit returns value and marks entry MRU | `cache hit value retrieval`, `cache hit recency promotion to mru`, `double hit recency stability` |
| `[slug:lru_cache.get.miss_returns_default]` | `get` | Cache miss returns specified default value | `cache miss none default`, `cache miss custom default value`, `unmodified cache state on miss` |
| `[slug:lru_cache.put.capacity_evicts_lru]` | `put` | Insertion at full capacity evicts least recently used | `eviction of oldest unaccessed key`, `mru insertion of newly added key`, `length preserved at capacity limit` |
| `[slug:lru_cache.put.update_existing_key]` | `put` | Overwriting existing key updates value & recency | `existing key value replacement`, `existing key recency promotion without eviction`, `unchanged collection size on update` |
| `[slug:lru_cache.invariants.len_le_capacity]` | Invariants | Cache size never exceeds capacity limit | `cache size bounded by capacity`, `bijective key value mapping invariant` |

---

#### 4. `dag_engine` Specification Slugs & Facets

*Specification Source*: [`benchmarks/parts/dag_engine/low/dag_engine.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/benchmarks/parts/dag_engine/low/dag_engine.pyi)

| Contract Slug | Method / Target | Contract Requirement Summary | Canonical Facet Vocabulary |
| :--- | :--- | :--- | :--- |
| `[slug:dag.node.add_unique]` | `add_node` | Unique node registration in graph topology | `unique node registration`, `duplicate node idempotent registration`, `empty node identifier error` |
| `[slug:dag.edge.add_directed]` | `add_edge` | Directed dependency from dependency to dependent | `directed dependency edge insertion`, `implicit node creation on edge addition`, `self loop edge error` |
| `[slug:dag.edge.cycle_detection_error]` | `add_edge` | CycleDetectedError on edge inducing cyclic path | `direct cycle detection (2 nodes)`, `transitive cycle detection (3+ nodes)`, `graph state preservation on rejected cycle` |
| `[slug:dag.order.topological_sort]` | `topological_order` | Dependency-first total ordering evaluation | `dependency preceding dependent ordering`, `independent node tie breaking`, `disconnected component ordering` |
| `[slug:dag.dirty.ancestor_propagation]` | `mark_dirty` | Transitive downstream dirty mark propagation | `transitive downstream dirty propagation`, `unrelated branch clean preservation`, `already dirty node idempotency` |
| `[slug:dag.dirty.mark_clean]` | `mark_clean` | Clean status stamped only when prerequisites clean | `clean status stamping`, `uncleaned prerequisite error on mark clean`, `leaf node clean stamping` |

---

### The Structured Blame Tuple Grammar & Formatting Standards

Combining the taxonomy of violation slugs, specification contract slugs, and constrained noun phrase facets, the blame critique string follows a strict formal BNF grammar:

```bnf
<BlameCritique>    ::= <SlugSection> " " <ViolationSection> " " <FacetSection> [ " " <LinesSection> ] [ " " <WitnessSection> ]
<SlugSection>      ::= "[slug:" <Identifier> ("." <Identifier>)* [ "#" <Identifier> ] "]"
<ViolationSection> ::= "[viol:" <AuditorPrefix> "." <ViolationName> "]" | "Violation: " <NounPhrase>
<FacetSection>     ::= "Facet: " <NounPhrase>
<LinesSection>     ::= "Lines: " <LineRange> | "[lines:" <LineRange> "]"
<LineRange>        ::= <Digits> | <Digits> "-" <Digits>
<WitnessSection>   ::= "Witness: " <LiteralKeyValueList>

<AuditorPrefix>    ::= "post" | "pre" | "inv" | "test" | "cov" | "spec" | "plan" | "pret_qa" | "pret_cov"
<NounPhrase>       ::= 1..8 Words of domain state/entity without verbs or prescriptive commands (max 60 chars)
<LiteralKeyValueList> ::= One or more key-value pairs of literal values (max 200 chars, e.g. `input='>= 1.0.0', exp=InvalidRangeError, obs=None`)
```

#### Grammar Rules & Structural Constraints
1. **Generalized Violation Section**: `<ViolationSection>` accepts either a taxonomy tag (`[viol:<prefix>.<name>]`) or a generalized restricted noun phrase (`Violation: <NounPhrase>`). Like `<FacetSection>`, a noun phrase violation must be **1–8 words, max 60 characters**, and contain **zero imperative verbs, modals, or prescriptive commands** (checked against `FORBIDDEN_ACTION_TOKENS`). This eliminates the infinite-taxonomy dilemma while maintaining strict non-prescriptive boundaries.
2. **Constrained Facet Section**: `<FacetSection>` identifies the equivalence partition or domain state (1–8 words, max 60 characters, no action verbs).
3. **Dedicated Culprit Line Component**: `<LinesSection>` is an optional dedicated section specifying the single line number or line range (`Lines: <Digits>[-<Digits>]`) strictly within the **culprit file being blamed**. Because blame targets a specific file, line numbers are bound exclusively to that file. Mentioning foreign file paths, foreign file names, or inline path citations (`file.py:12`) is strictly prohibited and rejected by the embargo firewall. Line ranges are validated against the actual line count of the blamed file ($1 \le \text{start} \le \text{end} \le \text{len}(\text{target\_file})$).
4. **Structured Witness Validation**: `<WitnessSection>` is strictly restricted to literal key-value pairs representing observed vs expected program states (e.g. `input=..., exp=..., obs=...`). It must contain at least one `=` key-value assignment, cannot contain foreign file names or line numbers (which belong in the dedicated `<LinesSection>`), and cannot contain conversational prose or imperative action tokens. This ensures witnesses remain pure data representations.

#### Canonical Examples Across Auditor Roles

##### 1. QA Auditor Blaming Implementation (Tag & Generalized Noun Phrase Formats)
```
[slug:semver.range.whitespace_tolerance] [viol:post.wrong_return] Facet: embedded operator whitespace Lines: 84-88 Witness: input='>= 1.0.0', exp='>=1.0.0', obs=InvalidRangeError
```
Or with generalized violation:
```
[slug:semver.range.whitespace_tolerance] Violation: postcondition divergence Facet: embedded operator whitespace Lines: 84 Witness: input='>= 1.0.0', exp='>=1.0.0', obs=InvalidRangeError
```

##### 2. QA Auditor Blaming Test Suite
```
[slug:semver.range.whitespace_tolerance] [viol:test.unmandated_behavior] Facet: uncontracted whitespace rejection Lines: 120-125 Witness: asserted=InvalidRangeError, allowed_by_spec=True
```
Or with generalized violation:
```
[slug:semver.range.whitespace_tolerance] Violation: uncontracted negative assertion Facet: uncontracted whitespace rejection Lines: 120 Witness: asserted=InvalidRangeError, allowed_by_spec=True
```

##### 3. Coverage Auditor Blaming Test Suite for Missing Edge Cases
```
[slug:semver.range.caret_range] [viol:cov.missing_boundary_endpoint] Facet: zero major caret boundary (^0.x.y) Lines: 45 Witness: missing_spans=[280, 285]
```

##### 4. Coverage Auditor Blaming Library for Unreachable Code
```
[slug:semver.parse.grammar] [viol:cov.unreachable_under_spec] Facet: trailing zero return in precedence comparison Lines: 142-144 Witness: span=[142, 144], pragma_required=True
```

##### 5. Spec QA Arbiter Blaming Low-Level Specification
```
[slug:semver.range.basic_comparator] [viol:spec.compound_conjunction] Facet: relational comparator and hyphen parsing conjunction Witness: clause='POSTCONDITIONS: MUST parse basic comparators and hyphen ranges'
```

##### 6. Pretense QA Auditor Blaming Implementation
```
[slug:semver.precedence.numeric_vs_alpha] [viol:pret_qa.falsified_property] Facet: numeric below string ranking Witness: v1='1.0.0-1', v2='1.0.0-alpha', step='compare_precedence'
```

##### 7. Pretense QA Auditor Blaming Pretense State Machine (Precondition Error Handling)
```
[slug:dag_lite.dag.get_node.node_must_exist] Violation: precondition error omission Facet: unregistered node identifier Witness: op=get_node, node='ghost', exp=NodeNotFoundError, obs=PretenseSpecificationError
```

##### 8. Pretense Coverage Arbiter Blaming Pretense State Machine
```
[slug:semver.solver.backtracking_undo] [viol:pret_cov.collaborator_seeding_deficit] Facet: transitive constraint rollback on backtrack Witness: unreached_rule='rule_undo_candidate_assignment'
```

##### 9. Pretense Coverage Arbiter Blaming Library for Unreachable Logic
```
[slug:semver.parse.leading_zero] [viol:cov.unreachable_under_spec] Facet: duplicate wildcard position guard Witness: span=[211, 214], pragma_required=True
```

---

---

### Multifaceted Requirements: Sub-Slug Hierarchies, Equivalence Partitions & Witness Vectors

A critical challenge arises when a specification requirement is **multifaceted**—combining multiple boundary cases, input partitions, or variant rules under a single contract clause. If an auditor reports:

$$\text{Blame: } \langle \text{tests/parser\_test.py}, \text{[slug:parser.parse.prerelease]}, \text{[viol:cov.missing\_test]} \rangle$$

The test author is left with an ambiguous directive: *which facet* of pre-release parsing is missing coverage? Is it numeric identifiers, multi-dot segmentation, hyphenated tags, or leading-zero edge cases?

Allowing the auditor to write natural language explanations to clarify the facet re-opens the door to accidental boundary leaks and hallucination echoing. Instead, Autofab provides a three-tiered mechanism to handle multifaceted requirements cleanly:

#### 1. Specification-Level Prevention: Sub-Slug Hierarchies (`[slug:...#facet]`)
Under the **Zero-Conjunction Rule** ([`planning_format.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/planning_format.md#L126)), compound requirements must be factored into atomic clauses during the planning and spec phases. When a requirement naturally has multiple operational facets or branches, `low/*.pyi` formalizes **Hierarchical Sub-Slugs**:

```python
def parse_version(self, text: str) -> Version:
    """Parse a semantic version string.
    
    POSTCONDITIONS:
    - [slug:semver.parse.prerelease#numeric]: WHEN prerelease contains digits, MUST compare numerically.
    - [slug:semver.parse.prerelease#lexical]: WHEN prerelease contains letters, MUST compare ASCII lexically.
    - [slug:semver.parse.prerelease#dotted]: WHEN prerelease contains dots, MUST split into atomic identifiers.
    """
```
By citing `[slug:semver.parse.prerelease#numeric]`, the auditor pinpoints the exact missing facet with zero natural language ambiguity.

#### 2. The Constrained Noun Phrase Facet Descriptor (`--facet`)
When sub-slugs do not exist in the specification, the auditor may supply a **short natural language noun phrase** ($\le 8$ words, $\le 60$ characters).

**Why Noun Phrases Prevent Contamination**:
- By grammatical construction, a noun phrase designates a **domain state, entity, or condition** (e.g. *"consecutive empty delimiters"*, *"prerelease tag with leading zeros"*, *"circular dependency cycle"*).
- It is **grammatically barred from containing verbs, imperatives, or recommendations** (prohibiting phrases like *"change line 42"*, *"use helper _foo"*, or *"assert result is empty"*).
- It eliminates conversational fluff, pleasantries, and cross-agent advice while giving authoring workers immediate, concrete clarity on what specific phenomenon requires attention.

```bash
bin/blame tests/parser_test.py \
  --spec-slug="[slug:semver.parse.prerelease]" \
  --viol="[viol:cov.missing_test]" \
  --facet="prerelease tags containing leading zeros"
```

#### 3. Bare Witness Literal Values (Context-Free Input/Output Witnesses)
In formal verification and property-based testing, the most actionable way to demonstrate a missing facet or counterexample is to present **Bare Witness Values** (literal parameter inputs or expected/observed data pairs).

While `low/*.pyi` defines parameter types (e.g., `text: str`), it rarely enumerates the concrete test strings. Presenting concrete sample values—even if not explicitly written in `low/*.pyi`—is **completely non-contaminating as long as they are presented as bare literals without surrounding prose or test scaffolding**:

```bash
bin/blame tests/parser_test.py \
  --spec-slug="[slug:semver.parse.prerelease]" \
  --viol="[viol:cov.missing_test]" \
  --facet="prerelease tags with leading zeros" \
  --witness="text='1.0.0-01.alpha'"
```

And for functional library bugs:
```bash
bin/blame lib/parser.py \
  --spec-slug="[slug:parser.parse.empty_delimiter]" \
  --viol="[viol:post.wrong_return]" \
  --facet="consecutive commas" \
  --witness="input='a,,b', exp=['a', '', 'b'], obs=['a', 'b']"
```

**Why Bare Witness Values Are Safe**:
- **Zero Scaffolding**: Contains no `test_*` function names, no `self.assertEqual(...)`, and no test setup context.
- **Zero Private Leaks**: Passed strictly through the public parameter interface.
- **Zero Hallucination Echoing**: Represents an objective mathematical observation (input $\to$ expected output under spec vs. observed output) rather than an auditor's speculation about how the code should be structured.

#### 4. Domain Partition Qualifiers (`--partition`)
When a concrete input literal is unwieldy or the requirement spans an abstract equivalence class, the blame tuple accepts a bounded **Domain Partition Qualifier**:

```bash
bin/blame tests/parser_test.py \
  --spec-slug="[slug:semver.parse.prerelease]" \
  --viol="[viol:cov.missing_test]" \
  --partition="prerelease_has_mixed_numeric_and_alpha"
```

---

### Auditor Execution Lifecycle: Blame-Only Concluding & Auto-Submit

#### Auto-Certification & Ignoring Redundant `bin/submit`
In Autofab's auditor role workspaces (`qa`, `coverage`, `spec_qa`):
1. **Automatic Baseline Submission**: If verification passes with zero failures and no blame needs to be delivered, targets are **automatically certified** at the start of the round without requiring the model to hunt and manually submit each clean file.
2. **Ignoring Blame-Free `bin/submit`**: If an auditor calls `bin/submit <target>` on a file for which no blame has been staged, the harness safely **ignores it as a no-op** (*"No blame staged for `<target>`; ignoring submit as file is already clean"*).
3. **Turn Conclusion via Blame Alone**: The auditor's sole duty in failure rounds is to attribute blame to the culprit target(s) per failure incident (e.g., in a test failure, attributing blame to `tests/*_test.py`, `lib/*.py`, or both). Once the auditor has executed `bin/blame` for the incident, **it can conclude its round immediately** without calling `bin/submit` on files it has nothing to say about.

---

### The Auditor `bin/fail` Circuit Breaker: Kill-and-Restart $\to$ User Escalation

What happens when an auditor is trapped at an impasse and has no idea what to do?
- **Example Scenario**: The auditor blames `lib/`, the library author rejects with `bin/reject` (*"Lines 42–45 already handle this; test crashed in mock setup"*). The auditor re-enters, re-reads the code, but still genuinely believes its feedback is correct, yet cannot get the subagent to accept it. Or the auditor is paralyzed by conflicting test traces.

The auditor invokes the escape valve:
```bash
bin/fail lib/parser.py "Impasse: Author rejected blame citing mock setup, but low/parser.pyi explicitly requires EmptyInputError on empty string which line 42 fails to raise."
```

#### The Two-Strike Restart & Escalation Protocol:

```
                  AUDITOR CALLS BIN/FAIL  OR  COORDINATOR DETECTS N REJECTS
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼                                   ▼
             [STRIKE 1: FIRST FAIL]              [STRIKE 2: CONSECUTIVE FAIL]
           - Traps bin/fail or N rejects       - Traps 2nd fail / persistent loop
           - Kills active auditor session      - Impasse circuit breaker trips
           - Wipes context window clean        - HALTS autonomous execution
           - Restarts fresh auditor subagent   - Requests HUMAN INTERVENTION
```

1. **Self-Initiated `bin/fail` vs. Coordinator-Declared Impasse**:
   - **Auditor Self-Failure**: The auditor can invoke `bin/fail` on its own when it has no idea what to do or is stuck (e.g. it cannot get the subagent to accept its feedback and still genuinely believes its critique is correct).
   - **Coordinator-Declared Impasse**: Even if an auditor does not call `bin/fail`, the coordinator tracks round history. If an auditor and subagent enter an unyielding loop (Auditor blames $\to$ Subagent `bin/reject`s $\to$ Auditor re-blames $\to$ Subagent re-rejects), the **coordinator automatically declares failure after $N$ blame-reject rounds** (default $N=2$).
2. **Strike 1 (Kill & Restart Fresh)**:
   - When failure is triggered the first time, the coordinator **kills the active auditor process/session immediately**.
   - It provisions a brand-new auditor session with a completely clean context window, wiping away model perseveration, attention decay, and cognitive fixation.
   - The freshly spawned auditor inspects the workspace with unbiased eyes.
3. **Strike 2 (Hard Stop for User Intervention)**:
   - If the restarted auditor *also* invokes `bin/fail` (or the blame-reject loop persists across the restarted instance), autonomous recovery has reached its limit.
   - The coordinator trips the **User Intervention Circuit Breaker**:
     - Execution on that target scope is halted immediately.
     - A high-priority user prompt is surfaced, presenting both the auditor's blame critique and the author's rejection rationale.
     - The human specification custodian intervenes to resolve the dispute, clarify ambiguous contracts in `high/*.md`, or correct faulty mock setups.

---

### Auditor Re-Evaluation Protocol (Failed Fixes & Contested Blame)

When an auditor re-enters a target after a failed fix or when blame was contested:
1. **Focus on the `# CHANGE:` Header**: If the worker submitted a change that failed to resolve the test failure or coverage deficit, the auditor must inspect the worker's `# CHANGE:` comment and code diff. Rather than blindly repeating the identical blame, the auditor analyzes *why* the worker's attempt fell short (e.g., identifying that the worker patched one branch but missed an adjacent condition).
2. **Contested Feedback Scrutiny**: If the worker contested previous blame (`bin/contest`), the auditor is presented with the worker's contest rationale.
3. **Objective Scrutiny Without Caving**: The auditor must neither stubbornly repeat disproven assumptions nor complacently cave to the worker's opinion. The auditor re-reads the authoritative specification (`low/*.pyi`), independently traces the execution path, and either:
   - Formulates a more precise blame item with a concrete witness demonstrating why the worker is still non-compliant; or
   - Concedes that the worker's code is compliant with the contract and redirects blame to the test author.

---

### Uncontracted Behavior (`[viol:test.uncontracted_behavior]`)

In Cleanroom architecture, **the specification is the immutable source of truth** during the code/test implementation phase. Because downstream roles cannot mutate `low/*.pyi`, uncontracted behavior represents **undefined behavior**:
- **Implementation Liberty**: The library implementation is completely unconstrained on undefined behavior—it may return `None`, raise an exception, or ignore the condition.
- **The Test Violation**: If a test asserts a specific outcome for an uncontracted scenario, the auditor issues:
  ```bash
  bin/blame tests/parser_test.py \
    --viol="[viol:test.uncontracted_behavior]" \
    --facet="asserting specific return value on uncontracted negative port numbers" \
    --lines=88-92
  ```
  The test author is instructed to delete or generalize the assertion, as tests are forbidden from turning undefined behavior into mandated contracts.

---

### List-Based Ergonomics Over ASCII Tables

Empirical evaluations confirm that LLMs do **not** parse ASCII tables well. Padded column borders (`| ... |`), horizontal divider hyphens (`+---+`), and cell wrapping consume excessive tokens, disrupt line-by-line attention mechanisms, and cause token-slicing artifacts.

Instead, Autofab formats feedback using **clean, indented Markdown/YAML key-value lists**, which models parse with near-perfect structural recall:

```markdown
# AUTOFAB METADATA
# FEEDBACK: [from qa]
# - item: 1
#   target: lib/parser.py
#   lines: 42-45
#   spec_slug: [slug:semver.parse.prerelease#numeric]
#   violation: [viol:pre.missing_error]
#   facet: prerelease numeric tags with leading zeros
#   witness: input='1.0.0-01', exp=ValueError, obs=None
# - item: 2
#   target: lib/parser.py
#   lines: 78-80
#   spec_slug: [slug:semver.parse.build#alphanumeric]
#   violation: [viol:post.wrong_return]
#   facet: alphanumeric build tags with hyphens
#   witness: input='1.0.0+01-a', exp='01-a', obs='01'
```

---

### Receiver Feedback Rejection (`bin/reject`) & The Unchanged File Invariant

When an authoring worker (`lib` or `test`) enters a role workspace and discovers feedback in in-band metadata, it has two mutually exclusive paths:

```
                                  INCOMING FEEDBACK
                                          │
                        ┌─────────────────┴─────────────────┐
                        ▼                                   ▼
              [AGREE WITH FEEDBACK]               [DISAGREE WITH FEEDBACK]
            - Modify code in workspace          - DO NOT touch code!
            - Run bin/check_files               - Run bin/reject <file> "<reason>"
            - Run bin/submit <file>             - Strict Invariant: File MUST be UNCHANGED
            - Invariant: File MUST be CHANGED   - Routes reason back to auditor
```

#### The `bin/submit` vs. `bin/reject` Invariant Duality

| Dimension | `bin/submit <file> --change-summary="..."` | `bin/reject <file> "<reason>"` |
| :--- | :--- | :--- |
| **Worker Stance** | **Accepts Feedback**: Acknowledges code defect or missing test. | **Rejects Feedback**: Asserts existing code is already compliant; feedback is invalid. |
| **File Mutation Invariant** | **Strictly Requires File to be CHANGED** (when resolving active feedback, as already enforced in Autofab): `CODE_HASH != baseline_hash` or git diff exists. Submitting an unedited file when feedback exists fails. | **Strictly Requires File to be UNCHANGED**: `git diff --quiet <file>` must return 0. Rejecting a modified file fails. |
| **Metadata Effect** | Records `# CHANGE:`, **wipes `# FEEDBACK:` immediately**, advances state clean. | **Wipes `# FEEDBACK:` immediately** from file header, records rejection rationale in workspace buffer (`.autofab_blame_buffer.json`). **No `# REJECTED_FEEDBACK:` metadata field exists.** |
| **Workflow Action** | Moves target forward to auditor re-verification. | Hands target back to auditor with rejection rationale in buffer for re-scrutiny. |

#### Feedback Scrubbing & Dirtiness Lifecycle
In Autofab's storage and DAG engine (`storage_impl`, `dirtiness_impl`), **the presence of active `# FEEDBACK:` in a file's header marks that node DIRTY**:
- As soon as a subagent executes either `bin/submit` OR `bin/reject`, the `# FEEDBACK:` block is **immediately deleted and scrubbed from the file header**.
- If feedback were not deleted upon `bin/reject`, the file would remain perpetually dirty under DAG checks.
- Deleting the feedback block on `bin/reject` keeps canonical source files 100% clean of operational debate logs, while the rejection reason is stored purely out-of-band in the coordinator's workspace blame buffer.

#### Why `bin/reject` Requires the File to be Unchanged
If a worker believes an auditor's blame is invalid (e.g. the test crashed in mock collaborator registration, or lines 42–45 already implement the contracted behavior), **the worker must not make cosmetic, superficial, or stealth edits to appease the harness**.
- If a worker modifies the file, `bin/reject` aborts with an error:
  `"Error: Cannot reject feedback on a modified file. If you made code changes, use 'bin/submit'. Rejecting feedback asserts that your existing code is already compliant with the specification."`
- This prevents "fake work" loops where models tweak whitespace or comments just to satisfy submission tools.

---

### Strict Plane Separation: Anti-Mechanistic Auditor Protection (`check_no_slug_references`)

**What is the true purpose of prohibiting specification contract references in code artifacts (`lib/`, `tests/`, `pretense/`)?**

The sole purpose is **Anti-Mechanistic Auditor Protection**: to prevent downstream auditors (QA, Coverage, Pretense QA) from mechanistically taking a `lib`, `test`, or `pretense` file's word for what `<contract>` is implemented.

Contract slugs belong **exclusively to the Specification Plane** (`high/*.md`, `planning/*.md`, `low/*.pyi`) and the **Auditor Blame Channel** (`bin/blame --spec-slug="[slug:...]" ...`). Code artifacts must remain standard, unembellished Python implementations and tests, evaluated purely on their empirical runtime behavior and AST semantics, never on self-attested claims.

#### The Anti-Mechanistic Threat Model:
1. **The Dangerous Token: Real Declared `<contract>` IDs**:
   If an authoring worker inlines a real, existing `<contract>` identifier into a comment or docstring (e.g. `# implements semver.compare_precedence.tri_state` or `def test_tri_state(): """semver.compare_precedence.tri_state"""`), an auditor inspecting that file is cognitively tempted into a shallow, mechanistic confirmation bias: *"The contract ID is present in the file's comments, so this requirement must be satisfied."* This shortcuts deep semantic analysis and branch verification.
2. **The Irrelevance of Slug Boilerplate**:
   Syntactic wrapper boilerplate (such as `[slug:`, `[contract:`, or variable names like `slug = ...`) is completely irrelevant to auditor bias. Banning generic brackets or the word `slug` does nothing to prevent an auditor from taking a worker's word for what contract was satisfied.
3. **The Irrelevance of Hallucinated Contracts**:
   Invented or hallucinated contract identifiers that do not exist in `low/*.pyi` are completely harmless. Because they do not correspond to any normative clause in the specification, they cannot satisfy any contract, trick an auditor into certifying a real requirement, or evade verification gates.
4. **Conclusion**:
   **Only real `<contract>` IDs that actually exist in the unit's companion `low/*.pyi` specification are dangerous.**

#### The Grounded Anti-Mechanistic Contract Linter (`check_no_slug_references`)
Rather than naively searching for the string `"[slug:"` (which is useless against plain comments and creates false positives on legitimate programming code), the linter:
1. Dynamically resolves the unit's companion Low-Level Specification (`low/*.pyi`).
2. Extracts the exact set of real, declared `<contract>` IDs.
3. Scans comments and docstrings in `lib/*.py`, `tests/*_test.py`, and `pretense/*.py`.
4. Rejects any reference to those **real declared contract IDs**:

```python
def check_no_contract_references(file_path: str, declared_contract_ids: Set[str]) -> list[str]:
    """Ensures lib, test, and pretense files do not reference real specification contract IDs.
    
    Protects downstream auditors from mechanistically taking the file's word
    for what contract is implemented. Only real contract IDs declared in the companion
    low/*.pyi specification are prohibited; boilerplate and non-existent IDs are ignored.
    """
    errors: list[str] = []
    if not declared_contract_ids:
        return errors

    # Match any declared contract ID within comments or docstrings
    contract_patterns = [
        (cid, re.compile(rf"\b{re.escape(cid)}\b", re.IGNORECASE))
        for cid in declared_contract_ids
    ]

    for lineno, comment_or_docstring in extract_comments_and_docstrings(file_path):
        for cid, pattern in contract_patterns:
            if pattern.search(comment_or_docstring):
                errors.append(
                    f"{file_path}:{lineno}: error: reference to declared specification contract '{cid}' "
                    "in code comment/docstring is prohibited. Auditors must evaluate contracts through "
                    "empirical execution, not self-attested in-code contract claims."
                )
                break
    return errors
```

    with open(file_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            for slug_id, pattern in slug_patterns:
                if pattern.search(line):
                    errors.append(
                        f"{file_path}:{idx}: Reference to low-level specification slug ID '{slug_id}' is strictly prohibited. "
                        "Code and test artifacts must not cite specification slug identifiers (bracketed or unbracketed)."
                    )
                    break
    return errors
```

- **Targeted & False-Positive Free**: Legitimate programming uses of the word `slug` (e.g. `url_slug`) are completely unaffected.
- **Absolute Plane Separation**: If `low/*.pyi` contracts `[slug:parser.parse.empty_delimiter]` or `[slug:prerelease_numeric_precedence]`, any occurrence of that exact identifier in `lib/*.py`, `tests/*_test.py`, or `pretense/*.py` **fails `bin/check_files` immediately in Pass 1**.
- **Auditor Independence**: Prevents subagents from planting slug IDs in code to bias the auditor into mechanistic confirmation.

---

### Multi-Culprit Concurrent Blame (Coupled Defects)

When a test failure involves **coupled defects across both planes** (e.g., the library has an off-by-one return value *and* the unit test failed to register a mock collaborator), the auditor is not forced to make an artificial choice between them.

The auditor calls `bin/blame` for each culprit independently in the same round:
```bash
# Blame the library defect:
bin/blame lib/parser.py \
  --spec-slug="[slug:semver.parse.prerelease#numeric]" \
  --viol="[viol:post.wrong_return]" \
  --facet="numeric segment comparison" \
  --witness="input='1.0.0-2', exp=2, obs=1" \
  --lines=42-45

# Blame the companion test defect:
bin/blame tests/parser_test.py \
  --viol="[viol:test.mock_missing]" \
  --facet="unregistered VersionEngine singleton in setUp" \
  --lines=24-26
```

#### Parallel Convergence:
Because Autofab executes Option 4 (parallel sibling workspaces), both `lib` and `tests` are marked dirty simultaneously and scheduled in the next wave concurrently. Each subagent resolves its own blame in its isolated sandbox without cross-boundary interference.

---

### Auditor Skepticism & Disallowing Mechanistic Slug Reliance

#### Preventing Mechanistic Bias in Auditors
While subagents may include comments in their code explaining how specification contracts are realized, **auditors must never treat in-code slug comments as proof of correctness**:
- An authoring subagent might slap a slug comment (`# [slug:...]`) onto an incomplete, buggy, or stubbed conditional branch.
- If the auditor relied on in-code slug tags, it would be tempted into a shallow, mechanistic conclusion (*"The slug tag exists on line 42, so the requirement must be satisfied"*).
- **The Empirical Skepticism Rule**: Auditors evaluate code exclusively through empirical execution (running unit tests, inspecting concrete runtime failures, tracing logic against `low/*.pyi`). The presence or absence of a comment tag in code does not absolve the implementation from failing test scenarios or coverage gates.

---

### The Dual-Agent Impasse Circuit Breaker: Joint Context Reset

When an auditor and worker enter a rejection loop (Auditor blames $\to$ Worker `bin/reject`s $\to$ Auditor re-blames $\to$ Worker re-rejects):
- **Cognitive Fixation on Both Sides**: Impasses are rarely one-sided. The worker develops defensive tunnel vision justifying its existing code, while the auditor develops perseverative fixation on its initial diagnostic hypothesis.
- **Joint Context Clearing (Strike 1)**:
  - When the coordinator declares an impasse after $N$ reject rounds (or on `bin/fail`), it **kills and restarts BOTH the auditor AND the worker sessions**.
  - **Zero Filesystem Re-Provisioning**: Physical workspaces are **not** torn down or re-provisioned. The files and environment remain intact.
  - **Context-Only Wiping**: Only the model conversation contexts (message history, prompt trajectories) are cleared.
  - Both agents start with a fresh context window, re-reading instructions, guides, and the actual file state without the cognitive baggage of prior conversational friction.
- **Strike 2 (Human Intervention)**: If the freshly restarted pair encounters another impasse on the same target, execution halts and the coordinator prompts the human user.

---

### Worker Rejection Reasoning & The Noun Phrase Recognizer

#### 1. Worker Rejection Ergonomics (`bin/reject`)
- `bin/reject <file> "<reason>"` captures the worker's natural language reasoning explaining why it believes its code is already compliant or why the test setup is flawed.
- Because workers operate in blind workspaces without the ability to execute the full test suite, they are **not** expected to construct formal mathematical counterexamples or complex witness vectors.
- The rejection reason is recorded in the coordinator's workspace blame buffer (`.autofab_blame_buffer.json`).
- When the auditor re-enters, it reads the worker's claim with **deep skepticism**, independently verifying whether the worker's argument holds against `low/*.pyi` and the test suite.

#### 2. Noun Phrase Recognition Engine
How do we ensure that `--facet` remains a descriptive noun phrase rather than an imperative code-prescription channel?

**Tier 1: Zero-Token Lexical Imperative Blocklist**:
In standard Python, a high-speed lexical scanner inspects the facet string:
- **Length Constraint**: $\le 8$ words, $\le 60$ characters.
- **Imperative Verb Rejection**: Rejects any string starting with or prominently containing imperative verbs or prescriptive modals:
  ```python
  FORBIDDEN_ACTION_TOKENS = {
      "fix", "change", "update", "delete", "remove", "add", "assert",
      "set", "use", "make", "ensure", "replace", "modify", "check",
      "should", "must", "cannot", "need", "refactor"
  }
  ```
- **Structure**: Permits standard noun phrase patterns: `[Determiner] [Adjective*] [Noun+] [Prepositional Phrase?]` (e.g. *"prerelease tags with leading zeros"*, *"consecutive empty delimiters"*).

**Tier 2: Meta-Auditor Fallback**:
If empirical evaluation reveals that models find ways to smuggle prescriptions past the lexical filter, a lightweight **Meta-Auditor** (using a fast Tier 1/2 model) inspects ambiguous facet strings during the blame interception pass.

---

### Strict Separation: Downstream Auditors Do Not Spot Specification Errors
Auditors in implementation and testing roles (`qa`, `coverage`, `pretense_qa`, `pretense_coverage`) evaluate `lib` and `tests` strictly against `low/*.pyi`.
- They are **not** specification arbiters and must never attempt to audit or redesign upstream specifications.
- Specification soundness, completeness, and consistency are verified exclusively by upstream review gates (`spec_qa`, High-to-Planning, and Planning-to-Low) before code synthesis begins.

---

### Standard DAG Propagation on Upstream Specification Changes

If an upstream specification (`low/*.pyi` or `high/*.md`) is modified while a target has pending feedback:
- The existing DAG dirtiness engine handles this naturally without special flush hooks.
- On its next clean round, the worker receives both the upstream change and the active feedback.
- If the worker implements the new spec changes but neglects the feedback (or vice versa), the auditor simply evaluates the target on its next round and blames the remaining discrepancies.

---

### Ephemeral Feedback Scrubbing & Header Hygiene

In Autofab, `# FEEDBACK:` blocks exist strictly to drive active dirty resolution:
- As soon as a worker executes `bin/submit` (accepting and submitting fixes) or `bin/reject` (asserting compliance and providing a contest reason), the `# FEEDBACK:` block is **immediately scrubbed from the file header**.
- No `# REJECTED_FEEDBACK:` comment is ever added to source files. The rejection rationale is stored strictly in the out-of-band workspace buffer for the auditor to inspect.
- This guarantees that target files transition cleanly out of the dirty state and canonical source trees never accumulate stale debate logs.

---

### The Deterministic Specification Contract Linter (`slug_lint.py`)

The primary purpose of `slug_lint.py` is **Anti-Mechanistic Auditor Protection**: preventing downstream auditors (QA, Coverage, Pretense QA) from mechanistically taking the authoring files' word for what specification contracts are implemented.

1. **Specification Plane Validation (`low/*.pyi`)**:
   - **Syntax Grammar**: Asserts that every declared contract slug in `low/*.pyi` adheres strictly to:
     `^\[slug:[a-z0-9_.]+(#[a-z0-9_]+)?(:[a-z0-9_]+)?\]$`
   - **Local Uniqueness**: Asserts that no two contract clauses within the same `low/*.pyi` file share the same slug.
   - **Specification Completeness**: Asserts that every `POSTCONDITIONS:` bullet and checked `PRECONDITIONS:` bullet in `low/*.pyi` carries an explicit slug tag.
2. **Code Artifact Plane Enforcement (`lib/*.py`, `tests/*_test.py`, `pretense/*.py`)**:
   - **Dynamic Specification Grounding**: Resolves the unit's companion `low/*.pyi` and extracts the exact set of real, declared `<contract>` IDs.
   - **Prohibiting Real Contract IDs in Comments/Docstrings**: Strictly rejects any comment or docstring mentioning any of those real, declared `<contract>` IDs, preventing authors from self-attesting contract coverage.
   - **Irrelevance of Boilerplate & Hallucinated IDs**: The linter completely ignores generic syntactic boilerplate (such as `[slug:`) and hallucinated contract IDs that do not exist in `low/*.pyi`. Only real declared contract IDs are dangerous because only real IDs could trick an auditor into mechanistically certifying a requirement.

---

## 8. Implementation Blueprint

### Component Decomposition & Touchpoints

The Feedback Firewall modifies and adds the following repository components:

```
autofab/parts/
├── control/
│   ├── lib/
│   │   ├── attribution_impl.py      <-- Integrate FeedbackFirewall.validate_blame()
│   │   └── feedback_firewall.py     <-- NEW: Two-Tier Firewall orchestration
│   └── low/
│       └── feedback_firewall.pyi    <-- NEW: Formal contracts for firewall & verdict
├── tools/
│   ├── lib/
│   │   └── symbol_extractor.py      <-- NEW: AST extraction of private/test symbols
│   └── low/
│       └── symbol_extractor.pyi     <-- NEW: Stub for symbol extraction
└── workspace_cli/
    └── lib/
        └── commands_impl.py         <-- Catch rejection diagnostics and print banners
```

### AST Symbol Extraction Engine (`symbol_extractor.py`)

A high-performance zero-token utility built using Python's native `ast` module:
- Scans `tests/*_test.py`: Extracts all `FunctionDef` names matching `test_*`, test classes (`Test*`), and fixture names.
- Scans `lib/*.py`: Extracts all `FunctionDef`, `AsyncFunctionDef`, `Name`, and `Attribute` identifiers starting with a single underscore (`_[a-zA-Z0-9]`), excluding dunder methods (`__init__`).
- Returns a lightweight set of prohibited token strings used by Tier 1 regex scanners and passed to Tier 2 context.

### Integration with `AttributionCoordinator` & `bin/blame`

In `autofab/parts/control/lib/attribution_impl.py`, `blame_culprit_file` is updated to invoke the firewall before mutating source files:

```python
# In AttributionCoordinator.blame_culprit_file():
firewall = get_singleton(feedback_firewall.FeedbackFirewall)
verdict = firewall.verify_and_sanitize_blame(
    culprit_file=culprit_file,
    critique=critique,
    caller_role=caller,
    repo_root=main_root,
    workspace_root=ws_root,
)

if not verdict.accepted:
    return attribution.AttributionOutcome(
        accepted=False,
        message=f"[FEEDBACK REJECTED] {verdict.rejection_reason}",
        affected_nodes=[],
    )

# Use sanitized critique if rephrased:
final_critique = verdict.sanitized_critique
final_culprit = verdict.culprit_file
```

### Configuration Schema in `autofab_roles.toml`

New declarative options added to `[role.<auditor>]` sections:

```toml
[role.qa]
# ... existing role definition ...
feedback_embargo_enabled = true
enforce_spec_grounding = true
allow_auto_rephrase = true
filter_model = "tier2_budget_cloud"

[role.coverage]
# ... existing role definition ...
feedback_embargo_enabled = true
anti_pruning_gate = true
allow_auto_rephrase = true
filter_model = "tier2_budget_cloud"
```

---

## 9. Empirical Verification & Test Strategy

### Defect Injection Test Matrix

The Feedback Firewall must be verified against an adversarial suite of synthetic blame submissions:

| Test Case ID | Injected Defect Scenario | Expected Firewall Action |
| :--- | :--- | :--- |
| **TC-EMB-01** | Critique to `lib/` cites `test_invalid_port()` and line 42. | **REPHRASED** (removes test citation, keeps spec gap) or **REJECTED**. |
| **TC-EMB-02** | Critique to `tests/` cites private helper `_parse_octal()`. | **REJECTED** with `LEAK_PRIVATE_SYMBOL`. |
| **TC-EMB-03** | Auditor blames `lib/` for test assertion failure where test asserted uncontracted error string. | **REATTRIBUTED** to `tests/` for asserting unmandated wording. |
| **TC-EMB-04** | Coverage auditor blames `lib/` to delete defensive wildcard handler (`*`). | **REJECTED** with `ANTI_PRUNING_VIOLATION`; directs coverage to test author. |
| **TC-EMB-05** | Critique contains 3 paragraphs, markdown code block, and 2,500 characters. | **Tier 1 REJECTED** (newline & length violations) in $< 10\text{ ms}$. |
| **TC-EMB-06** | Perfectly compliant, non-prescriptive, spec-grounded single paragraph. | **ACCEPTED** with zero modification in $< 1.5\text{ s}$. |

### Soundness, Churn & Leakage Telemetry

During benchmark flights (`evaluate_model_efficiency.py`), the runner records:
1. **Mutual Information Leakage**: $\mathcal{I}(P; V \mid \text{Blame})$, measured by n-gram overlap between blamed feedback and companion workspace ASTs. Target: $0.0\text{ bits}$.
2. **Blame Churn & Ping-Pong Reduction**: Comparative iterations to convergence ($T_{\text{conv}}$) with vs. without the Feedback Firewall.
3. **Cross-Test Suite Soundness**: Retention of defensive edge handling when evaluated against adversarial foreign test suites, measuring the elimination of destructive pruning defects.

---

## 10. Experimental Gating & Empirical Comparative Testing Framework

To rigorously measure the empirical benefits of structured blame against the legacy baseline and prevent regression in active development workflows, the entire feedback embargo architecture is implemented behind an **experimental feature toggle**.

### 1. Declarative & Runtime Toggle Mechanisms

The framework can be activated or deactivated dynamically across three distinct control planes:

```
                                 CONTROL PLANES
  ┌───────────────────────────┬───────────────────────────┬───────────────────────────┐
  │ 1. CLI Execution Flags    │ 2. Environment Variables  │ 3. Configuration Files    │
  ├───────────────────────────┼───────────────────────────┼───────────────────────────┤
  │ --structured-blame        │ AUTOFAB_STRUCTURED_BLAME=1│ [experimental]            │
  │ --legacy-blame            │ (or AUTOFAB_STRUCTURED_   │ structured_blame = true   │
  │                           │  BLAME=0)                 │ (in autofab_roles.toml)   │
  └───────────────────────────┴───────────────────────────┴───────────────────────────┘
```

- **CLI Flag Priority**: Specifying `--structured-blame` on `autofab clean`, `autofab orchestrate`, or `bin/evaluate_model_efficiency.py` takes immediate precedence over config files.
- **Backward Compatibility**: When the flag is omitted and configuration is default (`structured_blame = false`), Autofab runs in **Legacy Baseline Mode** without disruption.

---

### 2. Dual-Mode Dispatch & Behavioral Matrix

| Subsystem Component | Legacy Baseline Mode (`structured_blame = false`) | Experimental Mode (`--structured-blame`) |
| :--- | :--- | :--- |
| **`bin/blame` CLI Interface** | Accepts free-form natural language paragraph string: `bin/blame <target> "<critique>"`. | Enforces structured blame tuple: `--spec-slug`, `--viol`, `--facet`, `--witness`, `--lines`. |
| **Information Channel** | High-entropy natural language prose. | Zero-entropy structured tuple ($\mathcal{I} = 0$). |
| **Facet Validation** | None (free-form prose permitted). | Vector Cosine Margin Classifier + Noun Phrase Token Blocklist. |
| **`bin/reject` Tool** | Disabled / not deployed to workspace. | Enabled; enforces the Strict Unchanged File Invariant (`git diff --quiet`). |
| **Impasse Handling** | Ad-hoc failure; unmediated ping-pong. | Joint Context Reset (Strike 1) $\to$ User Prompt (Strike 2) after $N=2$ rejects. |
| **`slug_lint.py` Linter** | Non-blocking warning (Pass 1 permissive). | Hard failure on Pass 1 if LLS slug IDs appear in `lib/`, `tests/`, or `pretense/`. |
| **Metadata Header Format** | Unstructured single-paragraph string. | Indented YAML/Markdown list with explicit items and fields. |

---

### 3. Comparative Benchmarking Protocol (`evaluate_model_efficiency.py`)

The empirical benchmarking suite will evaluate the structured blame architecture against the legacy baseline across the anchor benchmark targets (`dag_engine_lite` and `semver_solver`):

#### Experimental Conditions (A/B Test Design):
- **Condition A (Legacy Baseline)**: Autofab multi-role pipeline running with legacy free-form feedback (`bin/blame <target> "<critique>"`).
- **Condition B (Experimental Structured Blame)**: Autofab multi-role pipeline running with `--structured-blame` active.

#### Comparative Telemetry & Success Metrics:

1. **Information Leakage ($\mathcal{I}(P; V \mid \text{Blame})$)**:
   - Measured by n-gram and identifier mutual information between blame feedback and companion workspace source files.
   - *Target*: Drop from $\mathcal{I} > 0.35\text{ bits}$ in Condition A down to **$0.00\text{ bits}$ in Condition B**.
2. **Cross-Test Suite Soundness (Differential Soundness %)**:
   - Evaluates whether implementations retain defensive edge handling against foreign test suites without destructive dead-code pruning.
   - *Hypothesis*: Eliminating dead-code pruning will boost cross-soundness in `semver_solver` from ~85% to **$\ge 96\%$**.
3. **Turn Count to Convergence ($T_{\text{conv}}$) & Blame Churn**:
   - Number of wave iterations required to achieve 100% clean status.
   - *Hypothesis*: Clear, non-leaking, slug-grounded diagnostics will eliminate 1–3 rounds of conversational misunderstanding ping-pong.
4. **Token Economics & Total Cost ($USD)**:
   - Measures prompt cache hit rate, token expenditure per clean, and step latency.
   - *Hypothesis*: Indented lists and short noun phrases will reduce feedback token bloat by **$40\% - 60\%$** relative to conversational essays.
5. **Rejection & Impasse Precision**:
   - Measures how frequently `bin/reject` is invoked and whether Strike 1 resets successfully resolve cognitive deadlocks without human intervention.
