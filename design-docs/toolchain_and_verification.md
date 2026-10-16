# Cleanroom Toolchain & Verification Architecture

## 1. Executive Summary & Philosophy

Cleanroom software engineering eliminates hallucinations, ambiguity, and implementation drift through a rigorous, closed-world verification pipeline. Rather than relying on non-deterministic LLMs to perform validation, synchronization, and coverage auditing, Cleanroom enforces an uncompromising principle:

> **The Anti-Drift Principle**: Structural validation, requirements inheritance, symbol linking, and coverage auditing must be executed by **100% deterministic, zero-token Python tooling** running in milliseconds under native **`uv`**. LLMs are reserved for generative synthesis; deterministic tools enforce the guardrails.

This document describes the complete toolchain architecture implemented in Cleanroom:
1. **The Modular Coverage Evaluation Engine (`update_with_ai/parts/tools/`)**: Modular single-target test tracing, AST statement normalization, and contiguous span deficit reporting ([`tool_coverage.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/lib/tool_coverage.py), [`tool_coverage_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/lib/tool_coverage_impl.py)), executed natively via `bin/check_files` under the `coverage` role.
2. **The Modular Workspace & Tools Engine (`update_with_ai/parts/workspace/` & `update_with_ai/parts/tools/`)**: Pure Python workspace lifecycle management (`workspace_roles`, `workspace_scaffold`, `workspace_stub`, `workspace_provision`, `workspace_registry`, `workspace_sync`), convention-based role provisioning, and in-band work queue evaluation (`workspace_tool.py`, `workspace_work.py`, `workspace_check.py`, `workspace_dirtiness.py`).
3. **The Specification Linters (`update_python_with_ai/support/lib/`)**: AST-based prose validation (`high_lint.py`), planning canvas structure validation (`spec_lint.py`), and pure interface stub verification (`low_lint.py`).
4. **The Code & Test Linters (`update_python_with_ai/support/lib/`)**: Concrete implementation compliance (`lib_lint.py`) and requirement comment citation validation (`test_lint.py`).
5. **Native Type Verification (`uv run pyright`)**: Hermetic, sub-second static type analysis driven by dynamic `PYTHONPATH` construction and package-level `pyproject.toml` configurations.

```
+---------------------------------------------------------------------------------------+
|                                CLEANROOM SPECIFICATION & VERIFICATION PIPELINE        |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|  [High-Level Spec: high/*.md]                                                         |
|           |                                                                           |
|           v                                                                           |
|  [Planning Canvas: planning/*.md]                                                     |
|           |                                                                           |
|           v                                                                           |
|  [Low-Level Stubs: low/*.pyi]                                                         |
|           |                                                                           |
|           v (high_lint.py, spec_lint.py, low_lint.py, pyright: Gate 1 SPEC_QA)        |
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
|                               v (uv run pyright && uv run pytest)                     |
|                 [Verified Cleanroom Subsystem]                                        |
+---------------------------------------------------------------------------------------+
```

---

## 2. Emphasizing Canonical `parts/` Over Procedural `support/lib/`

Cleanroom establishes a strict architectural boundary between **production domain logic** and **meta-framework primitives**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PARTS/ VS. SUPPORT/LIB/ DIVISION                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [update_with_ai/parts/*] (Modular 4-Stage Cleanroom Components)                       │
│  ───────────────────────────────────────────────────────────────                       │
│  • parts/tools: Statement coverage measurement, workspace tools, work queues, dirtiness │
│    (tool_coverage.py, workspace_tool.py, workspace_work.py, workspace_check.py)        │
│  • parts/workspace: Role workspace provisioning, scaffolding, stubs, and synchronization│
│    (workspace_provision.py, workspace_registry.py, workspace_roles.py, etc.)          │
│  • parts/storage: In-band metadata persistence, regex stamping, and source file storage │
│    (src_metadata.py, src_storage_impl.py, storage_asm.py)                              │
│  • parts/control: Change attribution, submission validation, and coordination          │
│    (control_submit_impl.py, control_attribution_impl.py)                               │
│  • parts/uv: Target resolution, manifest loading, and loop execution                   │
│    (uv_manifest_loader_impl.py, uv_loop_impl.py, uv_target_impl.py)                    │
│  • parts/systems: Unified system assembly initialization                               │
│    (uv_cleanroom_asm.py, uv_openai_loop_asm.py)                                        │
│                                                                                        │
│  [update_python_with_ai/support/lib/*] (Meta-Framework & Procedural Linters)           │
│  ───────────────────────────────────────────────────────────────────────────           │
│  • Metaclass Runtime Primitives: framework.py, lifecycle.py                            │
│    (Foundational spec decorators: @singleton_type, @data_type, @variant, @operation)   │
│  • Procedural AST Linters: high_lint.py, spec_lint.py, low_lint.py, lib_lint.py       │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

Monolithic scripts previously in `support/lib/` have been systematically modularized into canonical `parts/`:
- `evaluate_coverage.py` $\to$ [`update_with_ai/parts/tools/lib/tool_coverage.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/lib/tool_coverage.py)
- `cleanroom_workspace_tool.py` $\to$ [`update_with_ai/parts/tools/lib/workspace_tool.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/lib/workspace_tool.py) & [`update_with_ai/parts/workspace/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/)
- `src_metadata.py` $\to$ [`update_with_ai/parts/storage/lib/src_metadata.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/storage/lib/src_metadata.py)

---

## 3. The Coverage Evaluation Engine: `parts/tools`

### 3.1 Motivation & Single-Target 1:1 Isolation

In traditional codebases, coverage tools run across the entire test suite simultaneously. In Cleanroom, this produces a critical flaw: **cross-test pollution**. If Test A indirectly touches an internal helper in Module B, Module B falsely appears covered even if its dedicated unit test suite never tested that behavior.

Cleanroom enforces **1:1 Test-to-Implementation Isolation**:
- Each `*_impl_test.py` unit test suite is evaluated strictly against its corresponding `*_impl.py` file.
- The tool measures exactly one target at a time.
- All Cleanroom implementation modules must independently achieve **100.0% statement coverage** against their dedicated unit tests.

The coverage evaluation engine is implemented as a 4-stage Cleanroom component in [`update_with_ai/parts/tools/lib/tool_coverage.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/lib/tool_coverage.py) and [`tool_coverage_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/tools/lib/tool_coverage_impl.py).

### 3.2 AST Statement Normalization & Pragma Filtering

Standard Python `trace` and line coverage tools incorrectly count non-executable syntax lines as missed statements:
- Multiline function definition signatures (`def foo(\n  arg1,\n  arg2\n):`).
- Class definition headers spanning multiple lines.
- Docstrings at the module, class, or function level.
- Multi-line type annotations.

`tool_coverage_impl.py` solves this via **AST Statement Normalization**:
1. **AST Parse**: Parses the target `_impl.py` into an `ast.AST` tree.
2. **Signature Continuation Filtering**: Identifies all lines between a `FunctionDef` or `ClassDef` header and its first body statement, classifying them as non-executable.
3. **Docstring Filtering**: Locates all `ast.Expr(value=ast.Constant(str))` docstring nodes across all scopes and excludes their line ranges.
4. **Pragma Exclusion**: Recognizes comments containing `# pragma: no cover` or `# no cover`. When a statement or block is marked with pragma, its entire AST subtree line range is excluded from the executable statement denominator.

### 3.3 Enforcement of Cleanroom Assumption Rules

A foundational rule of Cleanroom is:
> **Callees expect assumptions; callers satisfy them.**

If callee code includes defensive checks for caller assumptions (e.g., checking if an acyclic graph contains a cycle when callers contractually guarantee acyclicity), those checks represent **dead assumption code**.

The coverage tool enforces this:
- If an assumption check exists in `_impl.py`, it cannot be tested by the unit test suite (because tests are forbidden from simulating assumption violations).
- Consequently, the assumption check shows up as an **uncovered line**.
- The developer must **remove the assumption check** from the implementation file.

### 3.4 CLI Invocation & Execution

In role workspaces, coverage evaluation is executed directly by the `coverage` arbiter via `bin/check_files`:

```bash
# In coverage role workspace: verify pending target
bin/check_files

# Direct tool runner invocation:
uv run python -m update_with_ai.support.lib.cleanroom_role_tool coverage \
    --impl update_with_ai/parts/sandbox/lib/sandbox_file_reader_impl.py \
    --test update_with_ai/parts/sandbox/tests/sandbox_file_reader_impl_test.py \
    --threshold 100.0
```

**Terminal Output Example**:
```text
=== Checking sandbox_file_reader_impl (role: coverage, part: parts/sandbox) ===
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

---

## 4. The Specification & Code Linters: `update_python_with_ai/support/lib/`

Cleanroom provides specialized deterministic AST linters in `update_python_with_ai/support/lib/` that validate specification authoring and code alignment:

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
- Enforces strict boundary rules preventing framework imports (`framework.py`) inside consumer library implementations.

### 4.5 `test_lint.py`: Unit Test Alignment Linter
- Enforces the requirements of `update_python_with_ai/guides/low_to_test.md`.
- Verifies that test assertions carry `# Requirement: <exact text>` comments matching canonical contract statements.
- Verifies that every test file concludes with `# Untested requirements: None` or an explicit bulleted list of untestable requirements.

---

## 5. Native Type Verification & Pyright Integration

Cleanroom runs Pyright natively via **`uv`** with zero Bazel dependency:

```bash
# Type-check entire repository:
uv run pyright

# Type-check specific package or target:
uv run pyright update_with_ai/parts/workspace
```

### 5.1 Dynamic `PYTHONPATH` Resolution
To ensure 100% type soundness without hardcoded static path lists:
1. `bin/test` dynamically constructs `PYTHONPATH` from repository packages and constituent parts.
2. Package-level `pyproject.toml` files (`update_with_ai/pyproject.toml`) configure standard `[tool.pyright]` settings.
3. Role workspaces run `uv run pyright` directly against the unit stubs and implementations with zero configuration file duplication.

---

## 6. Solved Verification Challenges & Patterns

| Subsystem / Area | Challenge | Status | Solution Mechanism |
| :--- | :--- | :--- | :--- |
| **AST Linting** | Framework import leakage into library code | **SOLVED** | AST visitor in `lib_lint.py` rejects `import framework`. |
| **Coverage Engine** | Monolithic coverage script & AST path mismatch | **SOLVED** | Modularized into `parts/tools/lib/tool_coverage.py` with relative workspace AST evaluation. |
| **Workspace Orchestration** | Monolithic `cleanroom_workspace_tool.py` | **SOLVED** | Modularized into 4-stage Cleanroom parts under `update_with_ai/parts/workspace/` and `update_with_ai/parts/tools/`. |
| **Toolchain Runtime** | Multi-second Bazel server overhead | **SOLVED** | Replaced with pure `uv` + Hatchling, reducing verification cycle to sub-100ms. |
| **Type Checking** | Brittle global `pyrightconfig.json` | **SOLVED** | Permanently deleted `pyrightconfig.json`; verification is driven by package-level `pyproject.toml` and dynamic `PYTHONPATH`. |
| **Scaffolding vs. Verification** | Accidental file generation during `check_files` | **SOLVED** | Separated `--scaffold` mode (for `get_work`) from strict verification mode in linters. |
| **Metadata Management** | Procedural `src_metadata.py` in support scripts | **SOLVED** | Canonicalized into `update_with_ai/parts/storage/lib/src_metadata.py`. |
| **Systems Assembly** | Bazel-bound root assemblies | **SOLVED** | Unified systems assembly under `uv_cleanroom_asm.py` and `uv_openai_loop_asm.py`. |

---

## 7. Execution Commands & Verification CLI

All verification is driven by Cleanroom's pure Python CLI:

```bash
# Run complete test suite and type check:
./bin/test

# Run type check and tests for specific unit or package:
./bin/test update_with_ai/parts/workspace

# Refresh system files across role workspaces:
uv run cleanroom refresh-sys

# Inspect work queues across the DAG:
uv run cleanroom work-queue staging

# Run autonomous cleaning against target or scope:
uv run cleanroom clean //staging/parts/sandbox:sandbox_file_reader_impl#lib
# or via convenient wrapper:
./bin/clean staging#lib
```
