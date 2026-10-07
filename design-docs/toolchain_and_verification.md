# Cleanroom Toolchain & Verification Architecture

## 1. Executive Summary & Philosophy

Cleanroom software engineering eliminates hallucinations, ambiguity, and implementation drift through a rigorous, closed-world verification pipeline. Rather than relying on non-deterministic LLMs to perform validation, synchronization, and coverage auditing, Cleanroom enforces an uncompromising principle:

> **The Anti-Drift Principle**: Structural validation, requirements inheritance, symbol linking, and coverage auditing must be executed by **100% deterministic, zero-token Python tooling** running in milliseconds. LLMs are reserved for generative synthesis; deterministic tools enforce the guardrails.

This document describes the complete toolchain architecture implemented in Cleanroom:
1. **The Specification Linters (`update_python_with_ai/support/lib/`)**: AST-based prose validation (`high_lint.py`), planning canvas structure validation (`spec_lint.py`), and pure interface stub verification (`low_lint.py`).
2. **The Code & Test Linters (`update_python_with_ai/support/lib/`)**: Concrete implementation compliance (`lib_lint.py`), requirement comment citation validation (`test_lint.py`), and derived build synchronization (`check_build_derived.py`).
3. **The Coverage Evaluation Engine (`update_with_ai/parts/tools/`)**: Modular single-target test tracing, AST statement extraction, and contiguous span deficit reporting (`tool_coverage.py`, `tool_coverage_impl.py`), executed via `bin/check_files` in the `coverage` role workspace.
4. **Planned Linter Modernization (TODO)**: Migrating procedural linters from `support/lib/` into canonical `parts/` components with full 4-stage specifications.

```
+---------------------------------------------------------------------------------------+
|                                CLEANROOM SPECIFICATION & VERIFICATION PIPELINE        |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|  [High-Level Spec: high/*.md]                                                         |
|           |                                                                           |
|           v (high_lint.py)                                                            |
|  [Planning Canvas: planning/*.md]                                                     |
|           |                                                                           |
|           v (spec_lint.py: Gate 1 SPEC_QA)                                            |
|  [Low-Level Stubs: low/*.pyi]                                                         |
|           |                                                                           |
|           v (low_lint.py: Gate 2 LOW_QA)                                              |
|           +---------------------------------------+                                   |
|           |                                       |                                   |
|           v (lib_lint.py)                         v (test_lint.py)                    |
|  [Implementation: lib/*.py]               [Unit Tests: tests/*_test.py]               |
|           |                                       |                                   |
|           +-------------------+-------------------+                                   |
|                               |                                                       |
|                               v (tool_coverage via bin/check_files)                   |
|              [Single-Target 100% Statement Coverage: Gate 3]                          |
|                               |                                                       |
|                               v (bazel test //... && pyright)                         |
|                 [Verified Cleanroom Subsystem]                                        |
+---------------------------------------------------------------------------------------+
```

---

## 2. The Specification Toolchain: `grounding_tool.py`

### 2.1 Overview & Architecture

The specification toolchain lives in [`update_with_ai/support/lib/grounding_tool.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/support/lib/grounding_tool.py) and is exposed via Bazel as:
- Binary: `//update_with_ai/support/lib:grounding_tool`
- Library: `//update_with_ai/support/lib:grounding_tool_lib`
- Unit Test Suite: `//update_with_ai/support/tests:test_spec_toolchain` ([`update_with_ai/support/tests/test_spec_toolchain.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/support/tests/test_spec_toolchain.py))

`grounding_tool.py` unifies six core capabilities into a single multi-pass compilation and verification pipeline:

```
Input: *.pyi Stubs & *.gt Specifications
   |
   +--> Pass 1: AST Linter (SpecLintVisitor)
   |       - Pure ellipsis body verification (`...`)
   |       - Structural decorator classification (@singleton_type, @poly_type, etc.)
   |       - "By-hand" typo and symbol resolution
   |       - Docstring contract headers (INVARIANTS, PRECONDITIONS, POSTCONDITIONS)
   |
   +--> Pass 2: Closed-World Linker (ClosedWorldLinker)
   |       - Cross-module import resolution
   |       - Supertype inheritance resolution
   |       - Lifecycle tier isolation (system vs. agent_session)
   |
   +--> Pass 3: Requirements & Stub Synchronizer (SpecRegistry & compile_module_inheritance)
   |       - Zero-token MRO requirements inheritance
   |       - Automatic `@override` member stub synthesis and stale member pruning
   |       - In-place file update (`--sync`) or compilation output (`--out-dir`)
   |
   +--> Pass 4: Zero Drift Verifier (`--check`)
   |       - Verifies in-place specs match canonical inheritance expansion exactly
   |
   +--> Pass 5: Groundtalk Relational Reasoner & Verifier (`GroundtalkVerifier`)
   |       - Verifies first-order Horn clauses, bi-conditional member access (`<->`), and single-given proofs
   |       - Enforces the state meta-rule and checks for unbound consequent wildcards (`_`)
   |       - Verifies universal member coverage and flags duplicate provisions/requirements
   |
   +--> Pass 6: Groundtalk Explanation & Witness Inspection (`--explain`)
           - Pretty-prints capability wiring, verified relational derivation steps, and near-misses
```

### 2.2 Pass 1: Custom "By-Hand" AST Linter (`SpecLintVisitor`)

External type checkers like Pyright are designed to verify that *executable code* matches type signatures. In pure `.pyi` grounding stubs where every member body is strictly `...`, Pyright only checks basic Python syntax while struggling with Cleanroom's custom domain meta-types (`@singleton_type`, `@poly_type`, `@data_type`, `@variant`).

Cleanroom replaces external checkers with a custom, deterministic AST visitor (`SpecLintVisitor`):
1. **Pure Ellipsis Body Invariant**: Every property and operation body must contain strictly an optional docstring followed by an `ast.Constant(value=...)` (the ellipsis `...`). Any assignments, expressions, control flow, or `pass` statements are rejected with compiler-style diagnostics (`<file>:<line>:<col>: error: ...`).
2. **Decorator Taxonomy Enforcement**:
   - Every class must have exactly one structural decorator: `@singleton_type("system")`, `@singleton_type("agent_session")`, `@poly_type`, `@data_type`, or `@variant`.
   - Every member must be decorated with `@property` or `@operation` (and optionally `@override`). Free-floating un-decorated methods are rejected.
3. **Symbol Table & Typo Detection**:
   - Collects all imported and locally declared symbols across the module.
   - Verifies every type annotation in property return types, parameter types, and base class lists.
   - When an unimported or undeclared symbol is encountered, it computes Levenshtein-based fuzzy matching to suggest typos (e.g. `Unknown type 'DirecotryPath'. Did you mean 'DirectoryPath'?`).
4. **Structured Docstring Parsing**:
   - Parses docstrings into structured sections: `PURPOSE:`, `GROUNDING_ARGUMENT:`, `FRESH_ASSUMPTIONS:`, `INHERITED_ASSUMPTIONS:`, `FRESH_REQUIREMENTS:`, and `INHERITED_REQUIREMENTS:`.
   - Rejects unstructured paragraphs or missing purpose headers.
5. **Orphan Function Validation**:
   - Strictly permits at most one top-level function per module: `__orphan__()`.
   - Verifies that `__orphan__()` takes no arguments, returns `None`, contains a pure ellipsis body, and defines strictly `PURPOSE:` and `FRESH_REQUIREMENTS:` docstring headers.

### 2.3 Pass 2: Closed-World Linker (`ClosedWorldLinker`)

The linker verifies systemic, multi-file ontological rules across the entire specification corpus:
1. **Base Class Resolution**: Ensures all referenced supertypes exist in imported modules and match valid inheritance rules (e.g., active services cannot inherit from passive data types; `@variant` classes must inherit from `@data_type` or another `@variant`).
2. **Lifecycle Tier Isolation**:
   - Long-lived `@singleton_type("system")` services cannot hold references or return types belonging to short-lived `@singleton_type("agent_session")` services.
   - Session services may freely reference system services.
3. **Closed Variant Completeness**: Verifies that polymorphic methods handling variants exhaustively match the closed sum-type hierarchy.

### 2.4 Pass 3: Zero-Token In-Place Requirements Synchronizer

Relying on LLMs to copy requirements down class hierarchies burns hundreds of thousands of tokens, introduces latency, and drops edge cases. In Cleanroom, requirements inheritance is mathematical and deterministic:

- **MRO Traversal**: For every child class, the engine computes its Method Resolution Order (MRO), extracting all ancestor assumptions and requirements.
- **Provenance Labeling**: Inherited requirements are grouped under `INHERITED_REQUIREMENTS:` labeled with their source ancestor (`- [<AncestorName>] <statement>`).
- **Idempotent In-Place Sync (`--sync`)**:
  1. *Wipe*: Existing `INHERITED_ASSUMPTIONS:` and `INHERITED_REQUIREMENTS:` blocks are cleared.
  2. *Recompute*: Ancestor contracts are resolved and injected with provenance labels.
  3. *Synthesize*: Any ancestor operations or properties not declared in the child class are automatically synthesized as `@override` stubs.
  4. *Prune*: Stale `@override` stubs with no fresh requirements whose ancestor members were removed are pruned. If a stale override has fresh requirements, the tool raises a compiler error to prevent lost work.
  5. *Preserve*: Local `FRESH_ASSUMPTIONS:` and `FRESH_REQUIREMENTS:` are untouched.

### 2.5 CLI Invocation & Commands

```bash
# Validate AST syntax, decorators, imports, and zero inheritance drift across .pyi:
bazel run //update_with_ai/support/lib:grounding_tool -- --check

# Validate Groundtalk specifications (.gt):
python3 update_with_ai/support/lib/grounding_tool.py --check update_with_ai/support/lib/core.gt update_with_ai/parts/sandbox/grounding/tool_provider.gt

# Explain Groundtalk capability wiring, rules, and proofs:
python3 update_with_ai/support/lib/grounding_tool.py --explain update_with_ai/parts/sandbox/grounding/tool_provider.gt

# Mechanically derive Groundtalk scaffolding from low-level Python stubs:
python3 update_with_ai/support/lib/pyi_to_groundtalk.py update_with_ai/parts/sandbox/low/tool_provider.pyi

# Synchronize inherited requirements and @override stubs in place:
bazel run //update_with_ai/support/lib:grounding_tool -- --sync

# Compile fully expanded stubs into an output directory:
bazel run //update_with_ai/support/lib:grounding_tool -- --out-dir bazel-bin/specs/grounding/ update_with_ai/specs/grounding/*.pyi

# Run test suite:
bazel test --test_output=errors --test_timeout=100 --noshow_progress --noshow_loading_progress //update_with_ai/parts/groundtalk/... //update_with_ai/support/tests:test_spec_toolchain
```

---

## 3. The Coverage Evaluation Tool: `evaluate_coverage.py`

### 3.1 Motivation & Single-Target Architecture

In traditional codebases, coverage tools run across the entire test suite simultaneously. In Cleanroom, this produces a critical flaw: **cross-test pollution**. If Test A indirectly touches an internal helper in Module B, Module B falsely appears covered even if its dedicated unit test suite never tested that behavior.

Cleanroom requires **1:1 Test-to-Implementation Isolation**:
- Each `*_impl_test.py` unit test suite is evaluated strictly against its corresponding `*_impl.py` file.
- The tool measures exactly one target at a time.
- All 20 Cleanroom implementation modules must independently achieve **100.0% statement coverage** against their dedicated unit tests.

The coverage evaluation tool is implemented in [`update_with_ai/support/lib/evaluate_coverage.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/support/lib/evaluate_coverage.py) and registered as Bazel binary `//update_with_ai/support/lib:evaluate_coverage`.

### 3.2 AST Statement Normalization & Pragma Filtering

Standard Python `trace` and line coverage tools incorrectly count non-executable syntax lines as missed statements:
- Multiline function definition signatures (`def foo(\n  arg1,\n  arg2\n):`).
- Class definition headers spanning multiple lines.
- Docstrings at the module, class, or function level.
- Multi-line type annotations.

`evaluate_coverage.py` solves this via **AST Statement Normalization**:
1. **AST Parse**: Parses the target `_impl.py` into an `ast.AST` tree.
2. **Signature Continuation Filtering**: Identifies all lines between a `FunctionDef` or `ClassDef` header and its first body statement, classifying them as non-executable.
3. **Docstring Filtering**: Locates all `ast.Expr(value=ast.Constant(str))` docstring nodes across all scopes and excludes their line ranges.
4. **Pragma Exclusion**: Recognizes comments containing `# pragma: no cover` or `# no cover`. When a statement or block is marked with pragma, its entire AST subtree line range is excluded from the executable statement denominator.

### 3.3 Enforcement of Cleanroom Assumption Rules

A foundational rule of Cleanroom is:
> **Callees expect assumptions; callers satisfy them.**

If callee code includes checks for caller assumptions (e.g., checking if an acyclic graph contains a cycle, or checking if a declared bound workspace file exists on disk), those checks represent **dead assumption code**.

The coverage tool enforces this:
- If an assumption check exists in `_impl.py`, it cannot be tested by the unit test suite (because tests are forbidden from simulating assumption violations).
- Consequently, the assumption check shows up as an **uncovered line**.
- The developer must either:
  1. **Remove the assumption check** from the implementation file (the primary Cleanroom remedy).
  2. Mark defensive OS-level environment fallbacks (such as external package imports) with `# pragma: no cover`.

### 3.4 CLI Invocation & Target Resolution

In role workspaces, coverage evaluation is executed directly by the `coverage` arbiter via `bin/check_files`, or explicitly via `cleanroom_role_tool.py`:

```bash
# In coverage role workspace: verify pending target
bin/check_files

# In coverage role workspace: verify specific unit
bin/check_files staging/parts/sandbox/lib/sandbox_file_reader_impl.py

# Direct tool runner invocation:
python3 update_with_ai/support/lib/cleanroom_role_tool.py coverage \
    --impl staging/parts/sandbox/lib/sandbox_file_reader_impl.py \
    --test staging/parts/sandbox/tests/sandbox_file_reader_impl_test.py \
    --threshold 100.0
```

**Terminal Output Example**:
```text
=== Checking sandbox_file_reader_impl (role: coverage, part: staging/parts/sandbox) ===
//staging/parts/sandbox/tests:sandbox_file_reader_impl_test PASSED in 0.3s
================================================================================
COVERAGE DEFICIT DETECTED: 97.5% (Threshold: 100.0%)
================================================================================
Test Suite:      sandbox_file_reader_impl_test.py
Implementation:  sandbox_file_reader_impl.py
Statements:      363 executable, 354 covered, 9 missed
Total Spans:     5 non-continuous spans
--------------------------------------------------------------------------------
Uncovered statement spans in sandbox_file_reader_impl.py:

  Span 1 (lines 124-126):
     124:         except (
     125:             LookupError,
     126:             KeyError,
...
================================================================================
```

### 3.5 Full Verification Benchmark Across All 20 Modules

| Subsystem | Implementation File | Total Statements | Covered | Coverage |
| :--- | :--- | :--- | :--- | :--- |
| **DAG & Telemetry** | `agent_conversation_history_impl.py` | 55 | 55 | **100.0%** |
| | `agent_loop_guard_impl.py` | 33 | 33 | **100.0%** |
| | `dag_cleaner_impl.py` | 65 | 65 | **100.0%** |
| | `runner_logger_impl.py` | 23 | 23 | **100.0%** |
| | `tool_provider_impl.py` | 105 | 105 | **100.0%** |
| **Bazel Subsystem** | `bazel_graph_storage_impl.py` | 129 | 129 | **100.0%** |
| | `bazel_manifest_loader_impl.py` | 50 | 50 | **100.0%** |
| | `bazel_openai_config_impl.py` | 101 | 101 | **100.0%** |
| | `bazel_node_config_impl.py` | 74 | 74 | **100.0%** |
| | `bazel_node_id_utils_impl.py` | 29 | 29 | **100.0%** |
| | `bazel_runner_impl.py` | 56 | 56 | **100.0%** |
| **Agent Subsystem** | `agent_node_cleaner_impl.py` | 82 | 82 | **100.0%** |
| | `agent_runner_impl.py` | 132 | 132 | **100.0%** |
| **Paths & Filesystem** | `file_paths_impl.py` | 47 | 47 | **100.0%** |
| **Sandbox Subsystem** | `sandbox_change_summary_validator_impl.py` | 20 | 20 | **100.0%** |
| | `sandbox_file_editor_impl.py` | 219 | 219 | **100.0%** |
| | `sandbox_file_reader_impl.py` | 180 | 180 | **100.0%** |
| | `sandbox_guide_delivery_impl.py` | 72 | 72 | **100.0%** |
| | `sandbox_impl.py` | 50 | 50 | **100.0%** |
| | `sandbox_run_control_impl.py` | 165 | 165 | **100.0%** |
| **Total** | **All 20 Modules** | **1,687** | **1,687** | **100.0%** |

---

## 4. The Specification & Code Linters: `update_python_with_ai/support/lib/`

Cleanroom provides specialized deterministic AST linters in `update_python_with_ai/support/lib/` (sharing parsing logic via `build_lint_common.py`) that validate specification authoring and code alignment:

### 4.1 `high_lint.py`: High-Level Specification Linter
- Validates Markdown structure under `## Purpose` and `## Types and Behavior`.
- Enforces literate prose requirements: flat single-level bullets, blank lines between paragraphs, and no nested bullet trees.
- Validates italic semantic markers (`*term*`), verifying that terms are italicized upon initial introduction for a concept and plain text on subsequent reference.
- Enforces component dependency rules: front-matter `imports:` and component isolation.

### 4.2 `spec_lint.py`: Planning Canvas Linter
- Enforces the requirements of `update_python_with_ai/guides/spec_qa.md`.
- Verifies `## Intent` prose separation from `## Factored Contracts`.
- Enforces the Zero-Conjunction Rule on atomic contract statements (`[slug]`).
- Validates epistemic grounding completeness under `## Grounding`, verifying that all `### Knowledge Requirements` are grounded against imported capability provisions.

### 4.3 `low_lint.py`: Low-Level Specification Linter
- Enforces pure Python interface stub rules (`.pyi`): ellipsis bodies (`...`), structural decorators (`@singleton_type`, `@poly_type`, `@data_type`, `@variant`, `@operation`, `@override`).
- Validates Design-by-Contract docstring headers (`INVARIANTS:`, `PRECONDITIONS:`, `POSTCONDITIONS:`).
- Validates Natural Language Grounding Arguments (`GROUNDING:`) in `*_impl.pyi` files.

### 4.4 `lib_lint.py`: Library Implementation Linter
- Validates concrete implementation modules in `{unit_dir}/lib/`.
- Verifies singleton registration parity, lifecycle registry integration, and imports against low-level stub declarations.
- Automatically maintains `{unit_dir}/lib/BUILD.bazel`, extracting external dependencies and inserting required build rules.

### 4.5 `test_lint.py`: Unit Test Alignment Linter
- Enforces the requirements of `update_python_with_ai/guides/low_to_test.md`.
- Verifies that test assertions carry `# Requirement: <exact text>` comments matching canonical contract statements.
- Verifies that every test file concludes with `# Untested requirements: None` or an explicit bulleted list of untestable requirements.

### 4.6 Planned Linter Migration into Parts Components (TODO)
Currently, all linters reside as monolithic procedural scripts in `update_python_with_ai/support/lib/`. The next critical architectural milestone is refactoring them into modular Cleanroom parts under `update_with_ai/parts/` (e.g. `parts/lint/` or expanding `parts/tools/`):
- Author High-Level Specifications (`high/*.md`) for AST parsing, contract extraction, and rule validation.
- Author Planning Canvases (`planning/*.md`) proving epistemic grounding of linter AST traversal capabilities.
- Formalize Low-Level Specifications (`low/*.pyi`) with typed DbC interfaces.
- Separate implementation (`lib/*.py`) and contract-driven unit tests (`tests/*_test.py`), eliminating procedural scripts from `support/lib/`.

---


## 5. Verification of Untestable Natural Language Diagnostics: Supervising LLM Protocol (TODO)

### 5.1 The Natural Language Testing Dilemma

Grounding specifications for agent tools stipulate that failure responses must deliver actionable diagnostics and recovery guidance:
- *Requirement*: `When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.`

In deterministic unit testing:
1. **String Content Unassertable**: Tests must never assert exact English wording or substrings, as prompt wording may evolve.
2. **Semantic Efficacy Untestable**: A deterministic string assertion cannot determine whether an error message actually provides sufficient, actionable guidance to enable an LLM agent to recover from a mistake.

Currently, these requirements are cataloged under the `# Untested requirements:` footer in test suites.

### 5.2 The Supervising LLM Architecture (TODO)

To bridge this gap without degrading the determinism of standard unit tests, Cleanroom specifies a future **Supervising LLM Evaluation Protocol**:

1. **Question Suite Generation**: During test execution, the test framework captures the runtime `tool_provider.Response(is_failed=True, content=...)` and generates a structured questionnaire:
   - *Q1*: Does the response explain why the invocation failed?
   - *Q2*: Does the response state the allowed input parameters or valid options?
   - *Q3*: Given this response, can an agent determine the exact corrective action?
2. **Supervising Model Evaluation**: The questionnaire and failure response are submitted to an independent supervising LLM.
3. **Structured Boolean Scoring**: The supervisor returns a validated schema (e.g. `{"diagnoses_issue": true, "provides_recovery": true}`).
4. **Offline / CI Gating**: This check runs in an asynchronous verification tier, preserving the millisecond speed of local unit tests while guaranteeing end-to-end communication quality.

---

## 6. Closed-World Type Verification & Solved vs. Open Challenges

### 6.1 Hermetic Bazel Type Checking (`bin/pyright_library.bzl`)

Cleanroom integrates Pyright type checking into Bazel builds via `pyright_library`, `pyright_test`, and `pyright_binary` macros. Type checking is subject to the same hermeticity and boundary requirements as executable compilation:

1. **Failure-Resilient Pipe Execution**: `_pyright_test_impl` executes under `set -e -o pipefail`, ensuring that test failures in downstream pipes (e.g. `xargs python3 -m pyright`) fail the Bazel action immediately rather than exiting cleanly.
2. **Runfiles Hermeticity**: Test scripts run against explicit Bazel `runfiles`, guaranteeing that external modules and transitive dependencies are physically isolated within the test sandbox.
3. **Dependency Namespace Hygiene**: Third-party wheel dependencies (via `site-packages`) are trimmed to the package root, preventing submodules from shadowing Python standard library namespaces (e.g. `openai/types` shadowing standard `types`).
4. **Closed-World Architectural Boundaries**: Specification-only infrastructure (`//update_with_ai/support/lib:framework`) is strictly forbidden as a dependency in library targets. `_pyright_test_impl` actively validates declared dependencies and aborts analysis if `:framework` is referenced.

### 6.2 Problem Ledger: Solved vs. Open Verification Challenges

For full analysis of grounding problems that resist prompt engineering, see **[`groundtalk.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/groundtalk.md)** and **[`grounding_format.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/grounding_format.md)**.

| Subsystem / Area | Challenge | Status | Solution Mechanism / Open Path |
| :--- | :--- | :--- | :--- |
| **AST Linting** | Framework import leakage into library code | **SOLVED** | AST visitor in `lib_lint.py` rejects `import framework` and `from ...framework...`. |
| **AST Linting** | Dataclass empty method stubs (`__init__` / `@property`) | **SOLVED** | AST visitor in `lib_lint.py` enforces class-level type annotations. |
| **Bazel Harness** | Silent pass bug on Pyright invocation failure | **SOLVED** | Added `set -e -o pipefail` and explicit runfiles closure in `bin/pyright_library.bzl`. |
| **Build Architecture** | Framework dependency leakage | **SOLVED** | Analysis-phase assertion in `_pyright_test_impl` disallows `:framework`. |
| **Proof Synthesis** | Unautomated Horn proof generation without operational actions | **UNSOLVED** *(Fundamental)* | Unguided forward-chaining and SMT solvers cannot invent existential terms across AND/OR hypergraphs; requires dense operational action steps. |
| **Proof Authoring** | LLM logic programming limitations (Gemini 3.8 Flash) | **UNSOLVED** *(Fundamental)* | Lightweight LLMs struggle with variable unification, polarity, and citing formal 25+ step logic proofs; requires DSL compilation or AST extraction. |
| **Test Verification** | Mock-to-protocol parity drift (`extract_target_name`) | **UNSOLVED** *(Hard)* | Requires protocol-typed mock variables (`x: Protocol = Mock()`) validated by Pyright. |
| **API Completeness** | Missing ergonomic query accessors in protocols | **UNSOLVED** *(Hard)* | Requires formal protocol expansion rather than prompt-directed ad-hoc workarounds. |
| **Type Hermeticity** | Primitive literals passed to domain `NewType`s | **SOLVED** | Explicit domain `NewType` constructor wrapping enforced in `low_to_lib.md` and Pyright. |
| **Type Hermeticity** | Container type invariance (`Set[Base]` vs `Set[Sub]`) in test assertions | **SOLVED** | Explicit collection annotations or `cast(Base, ...)` documented in `low_to_test.md`. |
| **Build Architecture** | Undeclared cross-package types in read-only `BUILD.bazel` | **SOLVED** | Private fallback container in interface aliased by implementation module. |
| **Build Architecture** | Undeclared collaborator nominal types in test fixtures | **SOLVED** | Type-erased `cast(Any, ...)` in test fixtures to respect read-only `pyright_deps`. |
| **Module Resolution** | Subsystem assembly cross-package constituent imports | **SOLVED** | Full package paths mandated for cross-package assembly constituents in `*_asm.py`. |
| **Test Verification** | Mock collaborator protocol return type mismatch | **SOLVED** | Strict protocol signature & property return type checking matching `low/*.pyi`. |
| **Test Verification** | Phantom types and illegal `TypeAliasType` constructor calls | **SOLVED** | Replaced phantom types with standard typing mappings in `low_to_test.md`. |
| **API Hygiene** | Residual legacy members and divergent class names | **SOLVED** | Strict contract parity pruning against `low/*.pyi` enforced in `low_to_lib.md`. |
| **Type Hermeticity** | Per-target closed typing vs. global `pyrightconfig.json` | **UNSOLVED** *(Hard)* | Requires generating per-target config files passed via `--project <file>`. |
| **Agent QA** | Natural language diagnostic efficacy verification | **UNSOLVED** *(Hard)* | Requires asynchronous Supervising LLM evaluation questionnaire protocol. |

---

### 6.3 Library Implementation Alignment Patterns & Nominal Type Hermeticity

During cleanroom alignment across packages in isolated role workspaces, library implementations operate under strict constraints: `BUILD.bazel` files are read-only (`chmod 444`), specifications are immutable, and Pyright enforces strict nominal subtyping. Four foundational alignment patterns govern this boundary:

1. **Domain `NewType` Nominal Wrapping**:
   - Cleanroom specifications define domain-specific nominal types (e.g. `EventName`, `MessageContent`, `TargetIdentifier`, `BuildSummary`) using `typing.NewType`.
   - Python type checkers treat `NewType` as a distinct subtype of its underlying primitive. Passing bare primitive literals or formatting expressions (such as `event_name="build_pass_start"` or `summary=f"Pass {n}"`) produces `reportArgumentType` errors.
   - All return values, dataclass parameters, message payloads, and collaborator method arguments typed as domain `NewType`s must be explicitly instantiated via their constructor (e.g. `EventName("build_pass_start")`, `BuildSummary(f"Pass {n}")`).

2. **Undeclared Cross-Package Types & Nominal Identity Sharing**:
   - When low-level specifications reference types from other packages (e.g. `sandbox_run_control.pyi` referencing `dag_config.BatchSize`) that are omitted from the unit's read-only `pyright_deps` in `BUILD.bazel`, importing the external package directly triggers `reportAttributeAccessIssue`.
   - *Fallback Container Pattern*: The interface module declares a private fallback container defining the missing nominal types:
     ```python
     class _Types:
         BatchSize = NewType("BatchSize", int)
     dag_config = _Types
     ```
   - *Nominal Identity Collision in Split Modules*: Pyright treats distinct `NewType` calls with the same name as entirely separate nominal types. If `*_impl.py` defines its own `BatchSize = NewType(...)`, overriding methods fail with `reportIncompatibleMethodOverride`. Paired implementation modules must therefore alias the exact container instance from their companion interface module:
     ```python
     dag_config = sandbox_run_control.dag_config
     ```
     This preserves nominal type identity across split interface and implementation modules.

3. **Subsystem Assembly Import Resolution**:
   - Subsystem assembly modules (`*_asm.py`) wire together constituent singletons across both the local package and foreign packages.
   - Intra-package constituents within the same directory use relative imports (`from . import constituent_impl`).
   - Cross-package constituents located in other packages must be imported using their full package paths (e.g. `from update_with_ai.parts.core.lib import file_paths_impl` or `from parts.core.lib import file_paths_impl`) rather than relative imports, preventing module resolution failures during assembly registration.

4. **API Hygiene & Legacy Member Pruning**:
   - As specifications iterate, library implementations can retain divergent class names or obsolete members from earlier prototypes (such as residual properties or surplus public type aliases).
   - Cleanroom library alignment mandates exact parity with `low/<name>.pyi` and `low/<name>_impl.pyi`. Any public class, method, property, or type alias not declared in the upstream specification must be aggressively pruned to prevent contract drift and public API pollution.

---

### 6.4 Unit Test Alignment Patterns: Nominal Typing, Container Invariance, and Hermetic Fixtures

When authoring unit test suites (`tests/*_test.py`) against low-level specifications, test doubles and fixtures face four strict static typing and dependency boundaries:

1. **Nominal Typing on Test Inputs & Factory Helpers**:
   - Cleanroom domain specifications make extensive use of `typing.NewType` (e.g. `ToolResponseContent`, `MessageContent`, `UnitAddress`, `RoleAddress`, `ParameterName`, `ParameterDescription`, `ToolReminder`, `SuppressionKey`, `LoopFeedback`, `FailureExplanation`).
   - Because `NewType` is invariant and not implicitly converted from `str` or `int`, test fixtures passing raw literals directly into dataclass fields (e.g. `DagNode("//pkg:unit", "lib")`) fail Pyright with `reportArgumentType`.
   - Test suites should establish module-level factory helpers (e.g., `_make_dag_node`, `_make_response`, `_make_msg`, `_make_tool_param`) or explicitly instantiate domain constructors to guarantee 100% type soundness across test fixtures.

2. **Container Type Invariance (`Set[T]`, `Mapping[K, V]`)**:
   - In Python typing, mutable containers like `set` are invariant with respect to their type arguments. Assigning `{ChangeMessage(...)}` to a state field typed as `Set[DagMessage]` fails type analysis (`"set[ChangeMessage]" is not assignable to "Set[DagMessage]"`), even though `ChangeMessage` subclasses `DagMessage`.
   - Test authors must either provide explicit container type annotations on fixture variables:
     ```python
     msgs: Set[DagMessage] = {ChangeMessage(...)}
     ```
     or use explicit element-level casting (`cast(DagMessage, msg)`).

3. **Hermetic Test Build Boundaries & Undeclared Collaborator Types**:
   - `test_lint.py` enforces that every library module imported by a test file must be declared in the test target's `pyright_deps` in `BUILD.bazel`.
   - Because `BUILD.bazel` is read-only for the Test Engineer, when a collaborator nominal type is needed strictly to construct fixture inputs (for example, constructing `DagNode` where an argument type originates from an undeclared package like `file_paths`), importing that external package triggers lint failure.
   - Test fixtures resolve this boundary via type-erased casts (`cast(Any, ...)`), constructing valid fixture objects without polluting declared build dependencies.

4. **Mock Interface Parity & Phantom Type Elimination**:
   - Test doubles mocking collaborator protocols must implement properties and methods with exact nominal type signatures matching `low/*.pyi` (for example, `Tool.parameters` returning `Mapping[ParameterName, ToolParameter[Any, Any]]` rather than loose `Mapping[str, Any]`).
   - Legacy test suites sometimes retain phantom types (e.g. `ActualParameterBindings`, `WireParameterBindings`) or invoke `TypeAliasType` as a constructor (`WireType("1")`). Tests must use canonical standard library mappings (`Mapping[ParameterName, WireType]`) and valid parameter instances.

5. **Local Linter Invocation & Multi-Package PYTHONPATH**:
   - `test_lint.py` performs dynamic dry-run module imports (`check_test_dry_run`) to catch runtime syntax and structural errors. When invoking `test_lint.py` outside of Bazel across cleanroom subsystems, `PYTHONPATH` must include `update_python_with_ai` and all constituent library directories (`update_with_ai/parts/*/lib`) to prevent false-positive `ModuleNotFoundError` failures during test dry runs.

---

## 7. The Formal Proof Verification Dilemma

Section 12 of **[`groundtalk.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/groundtalk.md)** identifies the primary architectural friction point in Cleanroom's formal verification layer:

1. **Solvers Are Verifiers, Not Synthesizers**:
   Neither Groundtalk's semi-naive Datalog engine nor external SMT/Horn solvers like Z3 can synthesize complete proofs from entry givens and leaf requirements alone. Because program methods generate new values (existential value invention) across an AND/OR hypergraph, unguided solvers return `unsat` unless supplied with the sequence of operational action facts.
2. **Lightweight LLMs Cannot Author Formal Logic Programs**:
   Relying on fast LLM models (e.g. Gemini 3.8 Flash) to author 27-step formal first-order relational proofs directly leads to severe failure modes: variable capture across unified terms, polarity inversions (`has_type(out x, T)`), hallucinated rule citations, and illegal shortcuts (`_` wildcards or arbitrary subtype substitutions).
3. **Architectural Direction**:
   Cleanroom must eliminate the requirement that the LLM write raw first-order logic programs. Future development will evaluate:
   - **Path A**: An ergonomic high-level action DSL that elaborates into Groundtalk relational steps.
   - **Path B**: Reverse-extracting Groundtalk proof steps directly from the Python implementation AST in `lib/*.py`.


