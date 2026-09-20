# Cleanroom Architecture & Design Documentation

Welcome to the Cleanroom design documentation index. Cleanroom is a literate, specification-driven software engineering paradigm designed for AI pair-programming and deterministic verification.

---

## Document Index & Reading Guide

The design documentation is organized across four foundational areas:

### 1. Specification Architecture & Literate Formats
- **[Specification Format & Architecture Design](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/specification_format.md)** (`specification_format.md`):
  - Definitive reference for literate High-Level Specifications (HLS).
  - Explains the prose philosophy, single-level standalone bullet paragraphs, italic semantic markers (`*term*`), and lifecycle tiers (`*system*` and `*agent session*`).
  - Outlines strict tier custody, knowledge derivation, and elimination of object type hierarchies.
- **[Requirements Specification Format](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/requirements_format.md)** (`requirements_format.md`):
  - Formulates natural language behavioral contracts and assumption preconditions.
  - Distinguishes caller-satisfied assumptions (preconditions) from callee guarantees (requirements).
  - Outlines the grounded failure principle, boundary defense, and rules for avoiding ungrounded error branches.
  - **Requirement Ordering & Prioritization Formalization (Section 7, TODO)**: Resolving the precedence gap in declarative `.pyi` contracts when HLS documents are absent from implementation and test authoring context.
  - **Decomposing Compound Failure & Response Requirements (Section 8, TODO)**: Decoupling deterministic failure predicates (`X fails if A`) from diagnostic guidance payloads (`reminding that...`).
- **[Markdown Template Format & System Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/template_format.md)** (`template_format.md`):
  - Definitive reference for Cleanroom's formatter-resilient Markdown templating system.
  - Explains the spec-as-sample philosophy, CommonMark HTML comment block and line-suffix directives (`<!-- if: ... -->`, `<!-- for: ... in ... -->`), parameter interpolation (`<name>`), and preservation of unrendered template structures.
  - Details integration with Starlark build rules (`update_with_ai.bzl`), session configuration (`node_config`), read tooling (`ReadTool`), and startup template materialization (`EditManager`).

### 2. Grounding & Ontological Modeling
- **[Grounding Specification Format: Python Interface Stubs (`.pyi`)](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/new_grounding_format.md)** (`new_grounding_format.md`):
  - Definitive reference for Cleanroom's canonical `.pyi` grounding format.
  - Explains the structural infrastructure split (`framework.py` vs. pure `.pyi` stubs), pure ellipsis bodies (`...`), and decorators (`@singleton_type`, `@poly_type`, `@data_type`, `@variant`, `@property`, `@operation`, `@override`).
  - Details the custom "by-hand" AST linter, closed-world linker, and zero-token MRO requirements inheritance engine.
  - **Architectural Extensions (Section 8, TODO)**: Unused import ledgers, supervising LLM diagnostics evaluation, requirement prioritization, and atomic failure/response requirement decomposition.
  - **Grounding Translation & Alignment Challenges (Section 9)**: In-depth ledger of solved vs. open grounding problems, analyzing why prompt engineering alone fails at boundary enforcement, mock-to-protocol parity, and structural type translation.
- **[Logic-Based Grounding Verification & Formal Specification](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/logic_based_grounding_verification.md)** (`logic_based_grounding_verification.md`):
  - Formal analysis of logic programming paradigms (First-Order Logic, Prolog, Datalog, and Constructive Type Theory) for specification grounding.
  - Explains why classical First-Order Logic falls short (monotonicity, frame problem, constructive value synthesis vs propositional truth, lifecycle scoping, exhaustive branching).
  - Clarifies Datalog's forward chaining and goal-directed Magic Sets query evaluation.
  - Proposes a 3-tier formal verification architecture combining Datalog scope checking, typed dataflow reachability, and effect framing to replace unverified natural language `GROUNDING_ARGUMENT:` blocks.
- **[Legacy Grounding Format (Historical Archive)](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/grounding_format.md)** (`grounding_format.md`):
  - *Archived / Superseded*: Historical documentation of the earlier 4-column Markdown table format (`type | name | signature | comment`). Preserved for context on the evolution of Cleanroom grounding.

### 3. Toolchain & Verification Architecture
- **[Toolchain & Verification Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/toolchain_and_verification.md)** (`toolchain_and_verification.md`):
  - Comprehensive guide to all deterministic tools implemented in Cleanroom.
  - **Specification Toolchain (`grounding_tool.py`)**: AST linter, linker, and zero-token in-place inheritance synchronizer.
  - **Coverage Evaluation Tool (`evaluate_coverage.py`)**: 1:1 single-target test isolation, AST statement normalization, exclusion of non-executable lines, pragma handling, and Cleanroom assumption enforcement.
  - **Specification & Code Linters (`update_with_ai/support/lib/`)**: `hls_lint.py`, `lib_lint.py`, `test_lint.py` (supported by `build_lint_common.py`).
  - **Closed-World Type Verification & Problem Ledger (Section 6)**: Hermetic Bazel type checking via `bin/pyright_library.bzl` and tracking of solved vs. open challenges.
  - **Supervising LLM Verification Protocol (TODO)**: Automated questionnaire generation for evaluating natural language tool failure diagnostics and agent recovery guidance.

### 4. Agent Platform Integrations
- **[Antigravity Tiered Sub-Agent Architecture & Integration Design](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/antigravity_integration.md)** (`antigravity_integration.md`):
  - Architecture for integrating Cleanroom with Google Antigravity under Google One Ultra subscriptions.
  - Covers the Coordinator $\rightarrow$ Worker subagent delegation hierarchy, sandbox hardening via disabled write tools, out-of-process Python MCP service, per-node context isolation, and quota/token efficiency trade-offs.
- **[Cleanroom Bazel Role Sub-Agent FastMCP Server & Unified Sandbox Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/bazel_role_mcp_server.md)** (`bazel_role_mcp_server.md`):
  - Definitive reference for the centralized FastMCP server and unified "double-duty" sandbox core orchestrating Antigravity role sub-agents.
  - Covers the shared sandbox domain engine, typed tool-like objects (`McpTool`), Bazel target label addressing, async zero-token long-polling, self-contained dynamic prompt dispatch, and real-time confinement via Antigravity lifecycle hooks.

---

## Cleanroom Specification Lifecycle

```
[High-Level Specification (HLS)]
  format: literate Markdown (.md)
  linter: hls_lint.py
  doc: design-docs/specification_format.md
         |
         v
[Grounding Interface Stubs]
  format: Python stubs (.pyi)
  tool: grounding_tool.py (--lint, --link, --sync, --check)
  doc: design-docs/new_grounding_format.md
         |
         +---------------------------------------+
         |                                       |
         v                                       v
[Library Implementation]                [Unit Test Suites]
  format: Python (_impl.py)               format: Python (_impl_test.py)
  linter: lib_lint.py                     linter: test_lint.py
  type check: pyright                     guide: update_python_with_ai/guides/grounding_to_test.md
         |                                       |
         +-------------------+-------------------+
                             |
                             v
              [Coverage Evaluation Tool]
                tool: evaluate_coverage.py (bazel run)
                benchmark: 100.0% statement coverage across 20 modules (1,687 statements)
                doc: design-docs/toolchain_and_verification.md
```
