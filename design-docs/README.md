# Cleanroom Engineering Architecture & Design Documentation

## 1. Executive Summary & Core Philosophy

**Cleanroom** is a literate, specification-driven software engineering paradigm designed for autonomous AI pair-programming and deterministic verification. It eliminates hallucinations, ambiguity, and implementation drift through a formal, unidirectional transformation pipeline:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         THE 5-STAGE CLEANROOM PIPELINE                           │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   1. High-Level Spec (high/*.md)                                                 │
│      Literate architectural prose, italic semantic markers, lifecycle tiers       │
│                                                                                  │
│                                  │  high_to_planning.md                          │
│                                  ▼                                               │
│   2. Planning Canvas (planning/*.md)                                             │
│      Intent vs Contracts, factored typing & atomic contracts with slugs          │
│                                                                                  │
│                                  │  planning_to_low.md                           │
│                                  ▼                                               │
│   3. Low-Level Spec (low/*.pyi)                                                  │
│      Typed Python stubs, INVARIANTS:, PRECONDITIONS:, POSTCONDITIONS:            │
│                                                                                  │
│                                  │  low_to_grounding.md                          │
│                                  ▼                                               │
│   4. Static Python Grounding (grounding/*.py)                                    │
│      Constructive feasibility proofs, COVERED: docstrings, straight-line checks  │
│                                                                                  │
│                                  │  low_to_lib.md / low_to_test.md             │
│                                  ▼                                               │
│   5. Library & Tests (lib/*.py & tests/*_test.py)                                │
│      Runtime implementation weaving derivation proofs & contract-driven tests    │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Foundational Principles
1. **Mandatory Specification-First (HLS-First)**: Production code and tests are never authored directly. Every capability and constraint originates in literate High-Level Specifications (`high/*.md`) and cascades automatically downstream.
2. **The Anti-Drift Principle**: Structural validation, closed-world symbol linking, relational feasibility, and test coverage auditing are enforced by **100% deterministic, zero-token Python tooling** running in milliseconds. LLMs are reserved for generative synthesis; deterministic tools enforce the guardrails.
3. **Double-Blind Verification**: Implementers write code against specifications without seeing tests. Test authors write assertions against specifications without seeing implementation code. Neither role can cheat or bias the other.
4. **Compile-Time Static Feasibility**: Typed Python grounding specifications prove that all required parameters, collaborator capabilities, and lifecycle states are reachable before runtime implementation begins.

---

## 2. The 5-Stage Specification & Verification Pipeline

### Stage 1: High-Level Specification (`high/*.md`)
- **Role**: Human-readable, literate architectural specification.
- **Key Concepts**:
  - Continuous prose with selective, single-level standalone bullet paragraphs.
  - Italics as lightweight semantic markers (`*term*`) introducing domain entities, properties, states, variants, and operations.
  - Lifecycle tiers (`*system*`, `*agent session*`, `*turn*`) governing service scope and custody.
- **Reference**: [`high_level_spec_format.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/high_level_spec_format.md)

### Stage 2: Planning Canvas (`planning/*.md`)
- **Role**: Semantic factorization and intent purification.
- **Key Concepts**:
  - Architectural rationale is segregated into continuous prose under `## Intent`.
  - Contracts are factored into static `### Typing` and atomic `### Contracts` with unique bracketed citation slugs (`[slug]`).
  - Zero-Conjunction Rule: contract statements contain no coordinating conjunctions (`and`, `or`).
  - Flat bullet list of cross-cutting operational interactions (`## Woven Contracts`), avoiding markdown tables.
- **Reference**: [`planning_format.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/planning_format.md)

### Stage 3: Low-Level Specification (`low/*.pyi`)
- **Role**: Formal Python interface and implementation stubs.
- **Key Concepts**:
  - Pure Python interface stubs with ellipsis bodies (`...`).
  - Structural decorators: `@singleton_type`, `@poly_type`, `@data_type`, `@variant`, `@operation`, `@override`.
  - Design-by-Contract docstrings organizing obligations into `INVARIANTS:`, `PRECONDITIONS:`, and `POSTCONDITIONS:`.
  - Pure Python stubs verified hermetically via Pyright.
- **Reference**: [`low_level_spec_format.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/low_level_spec_format.md)

### Stage 4: Static Python Grounding (`grounding/*.py`)
- **Role**: Compile-time capability reachability and knowledge custody proofs.
- **Key Concepts**:
  - Typed Python constructive feasibility proofs executed in straight-line execution blocks.
  - `COVERED:` and `DISCHARGED:` docstring sections citing low-level specification postconditions.
  - Proves variable-bound witness derivations without control flow statements, returning through terminal `raise NotImplementedError`.
  - Validated in milliseconds by `grounding_lint.py` and Pyright.
- **Reference**: [`python_grounding_architecture.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/python_grounding_architecture.md)

### Stage 5: Library Code & Contract-Driven Tests
- **Role**: Executable Python implementation and deterministic test suites.
- **Key Concepts**:
  - `lib/*.py`: Implements production runtime logic, linking to specifications in the file header (`# Requirements specified in <stem>.pyi`).
  - `tests/*_test.py`: Verifies contracts by citing verbatim requirement strings (`# Requirement: <exact text>`).
  - Validated by hermetic Bazel type checking (Pyright) and 100% statement test coverage via `evaluate_coverage.py`.
- **Reference**: [`toolchain_and_verification.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/toolchain_and_verification.md)

---

## 3. Cleaning Paradigms & Execution Architecture

Cleanroom supports distinct cleaning paradigms, each optimized for different operational environments, along with an archived post-mortem of a decommissioned subagent approach:

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                CLEANROOM EXECUTION PARADIGMS                             │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  [Option 1: Custom Headless Loop]        [Option 3: Subagentless Workspaces]             │
│  - In-process Python runner               - Independent sibling directories              │
│  - Native OpenAI API client              - Interactive Antigravity Chat UI               │
│  - Directed acyclic graph (DAG)          - OS chmod 444 double-blind isolation           │
│  - Best for: CI/CD & batch cleaning      - Best for: Interactive pair programming        │
│  - Doc: custom_loop_cleanroom.md         - Doc: subagentless_cleanroom_workspaces.md     │
│                                                                                          │
│                                  ▲                             ▲                         │
│                                  │                             │ Extended by             │
│                                  │                             │                         │
│                     [Option 2: In-Tree Subagents]  [Option 4: Subagent-Driven Workspaces]│
│                     - In-tree subagents & FastMCP  - Drives Option 3 workspaces          │
│                     - FAILED & DECOMMISSIONED      - Antigravity, dsh, Goose             │
│                     - Quota exhaustion ($30-$50)   - Zero-execution coordinator          │
│                     - Doc: antigravity_failed.md   - DeepSeek-V4 Flash ($0.20/run)       │
│                                                    - Doc: subagent_driven_workspaces.md  │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Option 1: Custom Loop Cleanroom** ([`custom_loop_cleanroom.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/custom_loop_cleanroom.md)):
   - In-process autonomous runner driving the OpenAI API (`update_with_ai/parts/systems/bazel_openai_loop_asm`).
   - Traverses build graph nodes in topological dependency order (`loop_cleaner.py`), running isolated turn loops (`loop_driver.py`) with repetition guards (`loop_guard.py`).
   - Production engine for headless continuous integration and batch cleaning.
2. **Option 3: Subagentless Cleanroom Workspaces** ([`subagentless_cleanroom_workspaces.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/subagentless_cleanroom_workspaces.md)):
   - Sibling workspace directories (`../role_workspaces/<workspace-name>_<role>_<dir>`) running independent conversational sessions in Antigravity.
   - Enforces double-blind isolation via OS-level `chmod 444` read-only mounts and orchestrates role coordination via relative convention discovery, direct Bazel mutations (`submit`, `blame`, `fail`), and self-synchronizing `bin/get_work`.
   - Production architecture for interactive AI pair programming managed via `bin/cleanroom`.
3. **Option 4: Subagent-Driven Cleanroom Workspaces** ([`subagent_driven_cleanroom_workspaces_todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/subagent_driven_cleanroom_workspaces_todo.md)):
   - Autonomous multi-agent architecture driving Option 3's pre-confined workspaces via a **Zero-Execution Coordinator**.
   - Uniform support across **Google Antigravity**, **DeepSeek Harness (`dsh`)**, and **Goose**.
   - Leverages **DeepSeek-V4 Flash** (`deepseek-flash`) for 98% token cost reductions and establishes a reproducible framework for side-by-side Gemini vs. DeepSeek model benchmarking.
4. **Option 2 (Archived Post-Mortem): Antigravity Subagents & MCP Server** ([`antigravity_integration_failed.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/antigravity_integration_failed.md)):
   - Detailed analysis of why in-tree subagents communicating with an execution server failed: token cost explosion ($30–$50 per run), multi-agent instruction degradation, and socket execution brittleness. Formally superseded by Option 4.
5. **Paradigms Comparative Guide** ([`cleaning_paradigms.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/cleaning_paradigms.md)):
   - Side-by-side comparative analysis of economics, isolation, and trade-offs across all cleaning options.

---

## 4. Master Document Index

### 4.1 Execution & Cleaning Paradigms
- **[Subagent-Driven Cleanroom Workspaces (TODO)](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/subagent_driven_cleanroom_workspaces_todo.md)** (`subagent_driven_cleanroom_workspaces_todo.md`): Authoritative design for multi-harness autonomous subagent orchestration across Antigravity, DeepSeek Harness, and Goose with DeepSeek-V4 Flash economics.
- **[Subagentless Cleanroom Workspaces](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/subagentless_cleanroom_workspaces.md)** (`subagentless_cleanroom_workspaces.md`): Primary interactive architecture with convention-driven zero-sync isolated role workspaces, pathless descriptors, direct Bazel mutations, and self-synchronizing global DAG work queues.
- **[Custom Loop Cleanroom](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/custom_loop_cleanroom.md)** (`custom_loop_cleanroom.md`): Headless in-process autonomous runner driving the OpenAI API.
- **[Archived Post-Mortem: Antigravity Subagents](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/antigravity_integration_failed.md)** (`antigravity_integration_failed.md`): Comprehensive post-mortem on why in-tree subagents failed (superseded by `subagent_driven_cleanroom_workspaces_todo.md`).
- **[Cleaning Paradigms Comparative Overview](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/cleaning_paradigms.md)** (`cleaning_paradigms.md`): Architectural comparison across all cleaning paradigms.

### 4.2 Specification Formats
- **[High-Level Specification Format (HLS)](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/high_level_spec_format.md)** (`high_level_spec_format.md`): Literate prose specifications, italic semantic markers, single-level bullets, and lifecycle tiers.
- **[Planning Canvas Specification Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/planning_format.md)** (`planning_format.md`): Intent separation, factored typing/contracts with slugs, and flat woven interactions.
- **[Rich Types & SSA Derivation Proofs in Planning](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/plan_rich_types_and_ssa_proofs.md)** (`plan_rich_types_and_ssa_proofs.md`): Rich dataclass typing, SSA step proofs, and state transformation derivation.
- **[Low-Level Specification Architecture (LLS)](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/low_level_spec_format.md)** (`low_level_spec_format.md`): Strong AST types, lifecycle decorators, and Design-by-Contract docstrings.
- **[Static Python Grounding Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/python_grounding_architecture.md)** (`python_grounding_architecture.md`): Static Python constructive reachability proofs replacing Horn clause solvers.

### 4.3 Synchronization & Workspace Architecture
- **[Subagentless Cleanroom Workspaces](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/subagentless_cleanroom_workspaces.md)** (`subagentless_cleanroom_workspaces.md`): Authoritative production architecture for convention-driven zero-sync workspaces with pathless descriptors, Bazel-backed direct mutations, canonical main workspace operations, symmetrical architecture, self-synchronizing `bin/get_work` with global DAG evaluation, and `bin/cleanroom`.
- **[In-Band Source Metadata & State Persistence](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/in_band_source_metadata.md)** (`in_band_source_metadata.md`): Completed production architecture eliminating `.update_with_ai.textproto` in favor of comment-embedded timestamps, single-entry change summaries, unacted feedback sections, and dynamic forward dirty evaluation.

### 4.4 Refactoring & Toolchain Infrastructure
- **[Component Modularization & Workspace Reuse (TODO)](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/component_modularization_todo.md)** (`component_modularization_todo.md`): Unified architectural refactoring plan for Cleanroom Workspaces, decomposing monoliths across both `parts/` (`sandbox_run_control_impl`, `bazel_node_config_impl`, `openai_driver_impl`) and `support/lib/` (`cleanroom_workspace_tool`, `cleanroom_role_tool`, `src_metadata`, linters) into shared, single-responsibility components to maximize code reuse and eliminate duplicate DAG/resolution implementations.
- **[Markdown Template Format & System Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/template_format.md)** (`template_format.md`): CommonMark HTML comment template directives (`<!-- if -->`, `<!-- for -->`, `<var>`).
- **[Toolchain & Verification Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/toolchain_and_verification.md)** (`toolchain_and_verification.md`): Deterministic linters, test coverage arbiter (`evaluate_coverage.py`), and Bazel type checking.
- **[Auditor Roles & Verification Dirtiness Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/auditor_roles_and_dirtiness_architecture.md)** (`auditor_roles_and_dirtiness_architecture.md`): Eliminating dummy `logs/` files in favor of co-located in-band verification attestations (`<ROLE>_AUDIT:`), resolving the 0-byte paradox, and formalizing auditor dirty predicates.


