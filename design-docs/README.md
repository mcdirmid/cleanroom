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
│              │ high_to_scenario.md               │ high_to_planning.md           │
│              ▼                                   ▼                               │
│   2. Concrete Scenarios (scenarios/*.md)    3. Planning Canvas (planning/*.md)   │
│      End-to-end action walkthroughs,           Intent prose, Factored Contracts, │
│      expected parameter & outcome bindings     Epistemic Grounding DAG           │
│                                                  │                               │
│                                                  │ planning_to_low.md            │
│                                                  ▼                               │
│                                             4. Low-Level Spec (low/*.pyi)        │
│                                                Typed Python stubs, DbC docstrings│
│                                                Natural Language GROUNDING: args  │
│                                                  │                               │
│                                                  ├── Gate 1: SPEC_QA Arbiter     │
│                                                  ▼   (high + scenario +          │
│                                                       planning + low stubs)      │
│                                             5. Library & Tests                   │
│                                                (lib/*.py & tests/*_test.py)      │
│                                                Double-blind code & contract tests│
│                                                  │                               │
│                                                  └── Gate 2: QA & Coverage       │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Foundational Principles
1. **Mandatory Specification-First (HLS-First)**: Production code and tests are never authored directly. Every capability and constraint originates in literate High-Level Specifications (`high/*.md`) and cascades automatically downstream.
2. **The Anti-Drift Principle**: Structural validation, closed-world symbol linking, relational feasibility, and test coverage auditing are enforced by **100% deterministic, zero-token Python tooling** running in milliseconds under native **`uv`**. LLMs are reserved for generative synthesis; deterministic tools enforce the guardrails.
3. **Double-Blind Verification**: Implementers write code against specifications without seeing tests. Test authors write assertions against specifications without seeing implementation code. Neither role can cheat or bias the other.
4. **Concrete Scenario Grounding**: Scenarios walk continuous operational journeys through the high-level specification, verifying that every interface operation is grounded and realizable before low-level stubbing.
5. **Epistemic Feasibility in Planning**: Knowledge provisions and consumer requirements form an acyclic reachability DAG directly in planning specifications, proving capability reachability before low-level stub formalization and implementation.
6. **Authors Author; Arbiters Lint and Audit**: Authoring models are insulated from interactive linters and type checkers to prevent mechanistic gaming; independent auditor roles (`spec_qa`, `qa`, `coverage`) run automated verification suites internally and deliver diagnostic blame attribution.
7. **Canonical `parts/` Over `support/lib/`**: All production domain logic, workspace management, statement coverage measurement, and session coordination live in modular Cleanroom parts (`parts/workspace`, `parts/tools`, `parts/control`, `parts/uv`, `parts/systems`), leaving `support/lib/` strictly for foundational metaclasses (`framework.py`, `lifecycle.py`) and procedural AST linters.

---

## 2. The 5-Stage Specification & Verification Pipeline

### Stage 1: High-Level Specification (`high/*.md`)
- **Role**: Human-readable, literate architectural specification.
- **Key Concepts**:
  - Continuous prose with selective, single-level standalone bullet paragraphs.
  - Italics as lightweight semantic markers (`*term*`) introducing domain entities, properties, states, variants, and operations.
  - Lifecycle tiers (`*system*`, `*agent session*`, `*turn*`) governing service scope and custody.
- **Reference**: [`high_level_spec_format.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/high_level_spec_format.md)

### Stage 2: Concrete Scenarios (`scenarios/*.md`)
- **Role**: Behavioral scenario grounding and end-to-end interface walkthroughs.
- **Key Concepts**:
  - Authored by `scenario` role via [`high_to_scenario.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/guides/high_to_scenario.md).
  - Concrete step-by-step journeys exercising operations with realistic inputs, state transitions, and observable outcomes.
  - Validates that high-level specifications contain no ungrounded or unreachable operations.
- **Reference**: [`concrete_scenario_validation.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/concrete_scenario_validation.md)

### Stage 3: Planning Canvas (`planning/*.md`)
- **Role**: Semantic factorization, intent purification, and epistemic grounding.
- **Key Concepts**:
  - Architectural rationale is segregated into continuous prose under `## Intent`.
  - Contracts are factored into static `### Typing` and atomic `### Contracts` with unique bracketed citation slugs (`[slug]`).
  - Zero-Conjunction Rule: contract statements contain no coordinating conjunctions (`and`, `or`).
  - Flat bullet list of cross-cutting operational interactions (`### Woven Contracts`), avoiding markdown tables.
  - Constructive feasibility is proven under `## Grounding`: exported capabilities (`### Knowledge Provisions`) pair with consumer obligations (`### Knowledge Requirements`).
  - Zero-Deferred Invariant: implementation canvases (`_impl.md`) repeat interface deferrals verbatim and ground 100% of requirements.
  - External components (`_ext.md`) strictly export provisions under `## Grounding`, omitting factored contracts and knowledge requirements.
- **Reference**: [`planning_format.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/planning_format.md)

### Stage 4: Low-Level Specification (`low/*.pyi`)
- **Role**: Formal Python interface stubs and implementation blueprints.
- **Key Concepts**:
  - Pure Python interface stubs with ellipsis bodies (`...`).
  - Structural decorators: `@singleton_type`, `@poly_type`, `@data_type`, `@variant`, `@operation`, `@override`.
  - Design-by-Contract docstrings organizing obligations into `INVARIANTS:`, `PRECONDITIONS:`, and `POSTCONDITIONS:`.
  - Natural Language Grounding Arguments (`GROUNDING:`) in `low/*_impl.pyi` translating planning provisions into concrete collaborator classes and methods.
  - Verified hermetically by native Pyright (via `update_python_with_ai/pyright_spec.json`), `low_lint.py`, and `spec_lint.py` through the `spec_qa` arbiter (Gate 1).
- **Reference**: [`low_level_spec_format.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/low_level_spec_format.md)

### Stage 5: Library Code & Contract-Driven Tests
- **Role**: Executable Python implementation and deterministic test suites.
- **Key Concepts**:
  - `lib/*.py`: Implements production runtime logic against low-level stubs.
  - `tests/*_test.py`: Verifies contracts by citing verbatim requirement strings (`# Requirement: <exact text>`).
  - Double-blind isolation: test authors never see implementation code; implementers never see tests.
  - Validated by native type checking (`uv run pyright`) and 100% statement test coverage via `parts/tools` (`tool_coverage.py`) through `qa` and `coverage` arbiters (Gate 2).
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
   - In-process autonomous runner driving the OpenAI API (`update_with_ai/parts/systems/uv_cleanroom_asm`).
   - Traverses dependency graph nodes in topological order (`loop_cleaner.py`), running isolated turn loops (`loop_driver.py`) with repetition guards (`loop_guard.py`).
   - Production engine for headless continuous integration and batch cleaning via `bin/cleanroom-loop` and root `cleanroom.toml`.
2. **Option 3: Subagentless Cleanroom Workspaces** ([`subagentless_cleanroom_workspaces.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/subagentless_cleanroom_workspaces.md)):
   - Sibling workspace directories (`../role_workspaces/<workspace-name>_<role>_<dir>`) running independent conversational sessions in Antigravity.
   - Enforces double-blind isolation via OS-level `chmod 444` read-only mounts and orchestrates role coordination via `parts/workspace`, direct CLI mutations (`submit`, `blame`, `fail`), and self-synchronizing `bin/get_work`.
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

### 4.1 Specification Formats & Verification Pipeline
- **[High-Level Specification Format (HLS)](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/high_level_spec_format.md)** (`high_level_spec_format.md`): Literate prose specifications, italic semantic markers, single-level bullets, and lifecycle tiers.
- **[Concrete Scenario Validation for HLS Translation](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/concrete_scenario_validation.md)** (`concrete_scenario_validation.md`): Concrete scenario-based evaluation of the HLS-to-LLS translation, with per-action interface requirement support and implementation realization checks, a triage for requirements no walk exercises, and a worked `workspace_work` example whose findings name the translation losses, missing realizations, and ungrounded imports.
- **[Planning Canvas Specification Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/planning_format.md)** (`planning_format.md`): Authoritative specification for Intent separation, factored typing/contracts with slugs, flat woven interactions, epistemic grounding DAG, external boundary specs (`_ext`), and `spec_qa` auditor verification.
- **[Low-Level Specification Architecture (LLS)](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/low_level_spec_format.md)** (`low_level_spec_format.md`): Strong AST types, lifecycle decorators, Design-by-Contract docstrings, and Natural Language Grounding Arguments (`GROUNDING:`).
- **[Specification Grounding, External Boundaries, & Assembly Pipeline](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/specification_grounding_boundaries_and_assembly_architecture.md)** (`specification_grounding_boundaries_and_assembly_architecture.md`): Grounding external files via `cleanroom_files_ext`, swatting residual `MODULE.bazel` markers, streamlining the mechanical assembly (`_asm`) lifecycle, and enforcing implementation (`_impl`) import accountability.
- **[Auditor Roles & Verification Dirtiness Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/auditor_roles_and_dirtiness_architecture.md)** (`auditor_roles_and_dirtiness_architecture.md`): In-band verification attestations (`<ROLE>_AUDIT:`), resolving the 0-byte paradox, and formalizing auditor dirty predicates.
- **[Toolchain & Verification Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/toolchain_and_verification.md)** (`toolchain_and_verification.md`): Deterministic linters, modular test coverage engine (`update_with_ai/parts/tools/lib/tool_coverage.py`), and native Pyright static type checking.

### 4.2 Execution & Cleaning Paradigms
- **[Subagent-Driven Cleanroom Workspaces (TODO)](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/subagent_driven_cleanroom_workspaces_todo.md)** (`subagent_driven_cleanroom_workspaces_todo.md`): Authoritative design for multi-harness autonomous subagent orchestration across Antigravity, DeepSeek Harness, and Goose with DeepSeek-V4 Flash economics.
- **[Subagentless Cleanroom Workspaces](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/subagentless_cleanroom_workspaces.md)** (`subagentless_cleanroom_workspaces.md`): Primary interactive architecture with convention-driven zero-sync isolated role workspaces, pathless descriptors, direct Python CLI mutations, and self-synchronizing global DAG work queues.
- **[Custom Loop Cleanroom](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/custom_loop_cleanroom.md)** (`custom_loop_cleanroom.md`): Headless in-process autonomous runner driving the OpenAI API via `parts/systems/uv_cleanroom_asm`.
- **[Archived Post-Mortem: Antigravity Subagents](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/antigravity_integration_failed.md)** (`antigravity_integration_failed.md`): Comprehensive post-mortem on why in-tree subagents failed (superseded by `subagent_driven_cleanroom_workspaces_todo.md`).
- **[Cleaning Paradigms Comparative Overview](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/cleaning_paradigms.md)** (`cleaning_paradigms.md`): Architectural comparison across all cleaning paradigms.

### 4.3 Packaging, Workspaces, & Shared Infrastructure
- **[Packaging, Distribution, & uv Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/packaging_and_distribution_architecture.md)** (`packaging_and_distribution_architecture.md`): Authoritative architecture for Hatchling wheel packaging, uv toolchain, PEP 621 pyproject.toml configuration, zero-install uvx CLI execution, hierarchical cleanroom.toml discovery, and complete Bazel retirement.
- **[In-Band Source Metadata & State Persistence](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/in_band_source_metadata.md)** (`in_band_source_metadata.md`): Completed production architecture eliminating `.update_with_ai.textproto` in favor of comment-embedded timestamps, single-entry change summaries, unacted feedback sections, dynamic forward dirty evaluation, and canonicalization into `parts/control/lib/src_metadata.py`.
- **[Markdown Template Format & System Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/template_format.md)** (`template_format.md`): CommonMark HTML comment template directives (`<!-- if -->`, `<!-- for -->`, `<var>`).

### 4.4 Research & Academic Publications
- **[Paper Submission Design Document](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md)** (`paper_submission_design_doc.md`): Authoritative research paper design, specification calculus, information-flow isolation invariants, multi-gate verification pipeline, and 5-RQ experimental evaluation plan.
