# Cleanroom Toolchain & Verification Architecture

## 1. Executive Summary & Philosophy

Cleanroom software engineering eliminates hallucinations, ambiguity, and implementation drift through a rigorous, closed-world verification pipeline. Rather than relying on non-deterministic LLMs to perform validation, synchronization, and coverage auditing, Cleanroom enforces an uncompromising principle:

> **The Anti-Drift Principle**: Structural validation, requirements inheritance, symbol linking, and coverage auditing must be executed by **100% deterministic, zero-token Python tooling** running in milliseconds. LLMs are reserved for generative synthesis; deterministic tools enforce the guardrails.

This document describes the complete toolchain architecture implemented in Cleanroom:
1. **The Specification Toolchain (`grounding_tool.py`)**: AST-based linting, symbol resolution, closed-world linking, and zero-token in-place requirements synchronization for Python interface stubs (`.pyi`).
2. **The Coverage Evaluation Tool (`evaluate_coverage.py`)**: Single-target test isolation, AST-based executable statement normalization, and assumption violation detection.
3. **The Specification & Code Linters (`update_with_ai/support/lib/`)**: Static prose, italic semantic marker, library implementation, and test alignment linters.
4. **Verification Boundary & The Supervising LLM Protocol (TODO)**: Resolving untestable natural language agent diagnostics.

```
+---------------------------------------------------------------------------------------+
|                                CLEANROOM SPECIFICATION & VERIFICATION PIPELINE        |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|  [High-Level Spec: .md]                                                               |
|           |                                                                           |
|           v (hls_lint.py)                                                             |
|  [Grounding Stubs: .pyi]                                                              |
|           |                                                                           |
|           v (grounding_tool.py: Lint -> Link -> Sync)                                 |
|  [Inherited & Linked Groundings: .pyi]                                                |
|           |                                                                           |
|           +---------------------------------------+                                   |
|           |                                       |                                   |
|           v (lib_lint.py)                         v (test_lint.py)                    |
|  [Implementation: _impl.py]              [Unit Tests: _impl_test.py]                  |
|           |                                       |                                   |
|           +-------------------+-------------------+                                   |
|                               |                                                       |
|                               v (evaluate_coverage.py)                                |
|              [Single-Target 100% Statement Coverage]                                  |
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

`grounding_tool.py` unifies five core capabilities into a single multi-pass compilation pipeline:

```
Input: *.pyi Stubs
   |
   +--> Pass 1: AST Linter (SpecLintVisitor)
   |       - Pure ellipsis body verification (`...`)
   |       - Structural decorator classification (@singleton_type, @poly_type, etc.)
   |       - "By-hand" typo and symbol resolution
   |       - Docstring contract headers (PURPOSE, FRESH_REQUIREMENTS, etc.)
   |
   +--> Pass 2: Closed-World Linker (ClosedWorldLinker)
   |       - Cross-module import resolution
   |       - Supertype inheritance resolution
   |       - Lifecycle tier isolation (system vs. agent_session)
   |
   +--> Pass 3: Requirements & Stub Synchronizer (SpecRegistry & compile_module_inheritance)
   |       - Zero-token MRO requirements inheritance
   |       - Grouped provenance labeling: `[<Ancestor>] <requirement>`
   |       - Automatic `@override` member stub synthesis and stale member pruning
   |       - In-place file update (`--sync`) or compilation output (`--out-dir`)
   |
   +--> Pass 4: Zero Drift Verifier (`--check`)
           - Verifies in-place specs match canonical inheritance expansion exactly
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
# Validate AST syntax, decorators, imports, and zero inheritance drift:
bazel run //update_with_ai/support/lib:grounding_tool -- --check

# Synchronize inherited requirements and @override stubs in place:
bazel run //update_with_ai/support/lib:grounding_tool -- --sync

# Compile fully expanded stubs into an output directory:
bazel run //update_with_ai/support/lib:grounding_tool -- --out-dir bazel-bin/specs/grounding/ update_with_ai/specs/grounding/*.pyi

# Run test suite:
bazel test --test_output=errors --test_timeout=100 --noshow_progress --noshow_loading_progress //update_with_ai/support/tests:test_spec_toolchain
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

The tool accepts flexible target arguments, including Bazel target labels, file names, or module prefixes:

```bash
# Evaluate by Bazel target label:
bazel run //update_with_ai/support/lib:evaluate_coverage -- //update_with_ai/tests:dag_cleaner_impl_test

# Evaluate by test suite name:
bazel run //update_with_ai/support/lib:evaluate_coverage -- sandbox_file_editor_impl_test

# Evaluate by implementation module prefix:
bazel run //update_with_ai/support/lib:evaluate_coverage -- sandbox_run_control
```

**Terminal Output Example**:
```text
Evaluating single test coverage: sandbox_file_editor_impl_test.py -> sandbox_file_editor_impl.py
=====================================================================================
Test Suite:      update_with_ai/tests/sandbox_file_editor_impl_test.py
Implementation:  update_with_ai/lib/sandbox_file_editor_impl.py
-------------------------------------------------------------------------------------
Total Statements: 219   | Covered: 219   | Missed: 0     | Coverage: 100.0%
-------------------------------------------------------------------------------------
✓ 100.0% coverage - all statements executed by test suite.
=====================================================================================
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
| | `bazel_model_config_impl.py` | 101 | 101 | **100.0%** |
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

## 4. The Specification & Code Linters: `update_with_ai/support/lib/`

Cleanroom provides specialized linters in `update_with_ai/support/lib/` (sharing parsing logic via `build_lint_common.py`) that validate specification authoring and code alignment:

### 4.1 `hls_lint.py`: High-Level Specification Linter
- Validates Markdown structure under `## Purpose` and `## Types and Behavior`.
- Enforces literate prose requirements: flat single-level bullets, blank lines between paragraphs, and no nested bullet trees.
- Validates italic semantic markers (`*term*`), verifying that terms are italicized upon initial introduction for a concept and plain text on subsequent reference.
- Validates assembly specifications (`*_asm.md`), checking front-matter ordering and enforcing that non-assembly specifications never import `*_impl` or `*_asm` components.

### 4.2 `lib_lint.py`: Library Implementation Linter
- Validates concrete implementation modules in `update_with_ai/lib/`.
- Verifies singleton registration parity, lifecycle registry integration, and imports against grounding declarations.
- Automatically maintains `update_with_ai/lib/BUILD.bazel`, extracting third-party external requirements (such as `requirement("openai")`) from dependent `.pyi` specifications and inserting required `@pip` load statements.

### 4.3 `test_lint.py`: Unit Test Alignment Linter
- Enforces the requirements of `update_python_with_ai/guides/grounding_to_test.md`.
- Verifies that test assertions carry `# Requirement: <exact text>` comments matching canonical grounding statements.
- Verifies that every test file concludes with `# Untested requirements: None` or an explicit bulleted list of untestable requirements.
- Automatically maintains `update_with_ai/tests/BUILD.bazel` target definitions.

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

For full analysis of grounding problems that resist prompt engineering, see **[Section 9 of `new_grounding_format.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/new_grounding_format.md#9-grounding-translation--alignment-challenges-prompt-engineering-vs-deterministic-enforcement)**.

| Subsystem / Area | Challenge | Status | Solution Mechanism / Open Path |
| :--- | :--- | :--- | :--- |
| **AST Linting** | Framework import leakage into library code | **SOLVED** | AST visitor in `lib_lint.py` rejects `import framework` and `from ...framework...`. |
| **AST Linting** | Dataclass empty method stubs (`__init__` / `@property`) | **SOLVED** | AST visitor in `lib_lint.py` enforces class-level type annotations. |
| **Bazel Harness** | Silent pass bug on Pyright invocation failure | **SOLVED** | Added `set -e -o pipefail` and explicit runfiles closure in `bin/pyright_library.bzl`. |
| **Build Architecture** | Framework dependency leakage | **SOLVED** | Analysis-phase assertion in `_pyright_test_impl` disallows `:framework`. |
| **Test Verification** | Mock-to-protocol parity drift (`extract_target_name`) | **UNSOLVED** *(Hard)* | Requires protocol-typed mock variables (`x: Protocol = Mock()`) validated by Pyright. |
| **API Completeness** | Missing ergonomic query accessors in protocols | **UNSOLVED** *(Hard)* | Requires formal protocol expansion rather than prompt-directed ad-hoc workarounds. |
| **Type Hermeticity** | Per-target closed typing vs. global `pyrightconfig.json` | **UNSOLVED** *(Hard)* | Requires generating per-target config files passed via `--project <file>`. |
| **Agent QA** | Natural language diagnostic efficacy verification | **UNSOLVED** *(Hard)* | Requires asynchronous Supervising LLM evaluation questionnaire protocol. |

