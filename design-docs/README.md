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
7. **Canonical `parts/` Over `support/lib/`**: All production domain logic, workspace management, statement coverage measurement, CLI tools, persistent storage, and session coordination live in modular Cleanroom parts (`parts/workspace`, `parts/tools`, `parts/storage`, `parts/control`, `parts/subagent`, `parts/dsh`, `parts/uv`, `parts/systems`), leaving `support/lib/` strictly for foundational metaclasses (`framework.py`, `lifecycle.py`) and procedural AST linters.

---

## 2. The 5-Stage Specification & Verification Pipeline

### Stage 1: High-Level Specification (`high/*.md`)
- **Role**: Human-readable, literate architectural specification.
- **Key Concepts**:
  - Continuous prose with selective, single-level standalone bullet paragraphs.
  - Italics as lightweight semantic markers (`*term*`) introducing domain entities, properties, states, variants, and operations.
  - Lifecycle tiers (`*system*`, `*agent session*`, `*step*`) governing service scope and custody.
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

Cleanroom supports distinct cleaning paradigms, each optimized for different operational environments, along with an archived post-mortem of a decommissioned subagent approach. All paradigms, metadata standards, and roadmaps are consolidated in [`todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md):

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
│  - Doc: todo.md Section 3                - Doc: todo.md Section 3                        │
│                                                                                          │
│                                  ▲                             ▲                         │
│                                  │                             │ Extended by             │
│                                  │                             │                         │
│                     [Option 2: In-Tree Subagents]  [Option 4: Subagent-Driven Workspaces]│
│                     - In-tree subagents & FastMCP  - Drives Option 3 workspaces          │
│                     - FAILED & DECOMMISSIONED      - Antigravity, DSH                    │
│                     - Quota exhaustion ($30-$50)   - Zero-execution coordinator          │
│                     - Doc: todo.md Section 3       - DeepSeek-V4 Flash ($0.20/run) & G3.8│
│                                                    - Doc: todo.md Section 3              │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Option 4: Subagent-Driven Cleanroom Workspaces (Primary Orchestration)**:
   - Autonomous multi-agent architecture driving pre-confined workspaces via a **Zero-Execution Coordinator**.
   - Uniform support across **Google Antigravity** (with native desktop `agentapi` reactive IPC & headless tab dispatch) and **DeepSeek Harness (`dsh`)** (with direct JSON-RPC server reconciliation and `dsh_telemetry`; Goose support turned down and decommissioned).
   - Dynamic parallel wave clustering (`lib` + `test`), downstream synchronization barriers, closed-loop blame defect propagation, and automatic workspace cancellation teardown.
   - Built on canonical Cleanroom parts: `update_with_ai/parts/subagent/` (generic DAG coordinator and command harness) and platform parts (`parts/antigravity/` and `parts/dsh/`).
   - Detailed technical architecture in [`design.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/design.md) Section 2; operational status in [`todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md).
2. **Option 3: Subagentless Cleanroom Workspaces**:
   - Sibling workspace directories (`../role_workspaces/<workspace-name>_<role>_<dir>`) running independent conversational sessions in Antigravity or any IDE.
   - Enforces double-blind isolation via OS-level `chmod 444` read-only mounts and orchestrates role coordination via `parts/workspace`, direct CLI mutations (`submit`, `blame`, `fail`), and self-synchronizing `work-queue`.
   - Detailed technical architecture in [`design.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/design.md) Section 2; operational status in [`todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md).
3. **Option 1: Custom Loop Cleanroom**:
   - In-process autonomous runner driving OpenAI or Gemini APIs (`update_with_ai/parts/systems/uv_cleanroom_asm`).
   - Traverses dependency graph nodes in topological order (`loop_cleaner.py`), running isolated step loops (`loop_driver.py`) with repetition guards (`loop_guard.py`).
   - Production engine for headless continuous integration and batch cleaning via `uv run cleanroom clean --harness loop`.
   - Detailed technical architecture in [`design.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/design.md) Section 2; operational status in [`todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md).
4. **Option 2 (Archived Post-Mortem): Antigravity FastMCP Subagents**:
   - Detailed analysis of why in-tree subagents communicating with an execution server failed: token cost explosion ($30–$50 per run), multi-agent instruction degradation, and socket execution brittleness. Formally superseded by Option 4.
   - Detailed post-mortem in [`design.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/design.md) Section 3.

---

## 4. Master Document Index

### 4.1 Specification Formats & Verification Pipeline
- **[High-Level Specification Format (HLS)](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/high_level_spec_format.md)** (`high_level_spec_format.md`): Literate prose specifications, italic semantic markers, single-level bullets, and lifecycle tiers.
- **[Concrete Scenario Validation for HLS Translation](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/concrete_scenario_validation.md)** (`concrete_scenario_validation.md`): Concrete scenario-based evaluation of the HLS-to-LLS translation, with per-action interface requirement support and implementation realization checks.
- **[Planning Canvas Specification Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/planning_format.md)** (`planning_format.md`): Authoritative specification for Intent separation, factored typing/contracts with slugs, flat woven interactions, epistemic grounding DAG, external boundary specs (`_ext`), and `spec_qa` auditor verification.
- **[Low-Level Specification Architecture (LLS)](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/low_level_spec_format.md)** (`low_level_spec_format.md`): Strong AST types, lifecycle decorators, Design-by-Contract docstrings, and Natural Language Grounding Arguments (`GROUNDING:`).
- **[Toolchain & Verification Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/toolchain_and_verification.md)** (`toolchain_and_verification.md`): Deterministic linters, modular test coverage engine (`update_with_ai/parts/tools/lib/tool_coverage.py`), and native Pyright static type checking.
- **[Markdown Template Format & System Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/template_format.md)** (`template_format.md`): CommonMark HTML comment template directives (`<!-- if -->`, `<!-- for -->`, `<var>`).

### 4.2 Master Architecture, Technical Design & Roadmap
- **[Cleanroom System Architecture & Technical Design](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/design.md)** (`design.md`): Authoritative technical design specification covering execution paradigms (Options 1, 3, 4 and Option 2 post-mortem), multi-wave orchestration barriers and cancellation teardown, physical sibling workspaces (`chmod 444`), in-band source metadata schema, logless auditor roles, specification grounding, native Python packaging (`pyproject.toml` + `uv`), DeepSeek Harness JSON-RPC streaming, and native Google Antigravity Desktop `agentapi` reactive IPC.
- **[Cleanroom Subsystems & Modular Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/modular_subsystems_architecture.md)** (`modular_subsystems_architecture.md`): Architectural analysis of Cleanroom's 7 reusable subsystems, dependency audit post-mortem, strictly acyclic 5-layer greenfield architecture (10 standalone libraries), and phased migration roadmap.
- **[Cleanroom Architecture, Execution Paradigms, Progress & Master Roadmap](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md)** (`todo.md`): Operational master document covering system execution status, completed milestones, verification metrics, quick CLI reference, and prioritized forward development roadmap.

### 4.3 Research & Foundational Specification Language
- **[Grounded Specification Language & Neural Compilation Architecture](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/grounded_specification_language_and_neural_compilation.md)** (`grounded_specification_language_and_neural_compilation.md`): Declarative, non-procedural specification programming language whose static type system guarantees closed-world grounding, compiled via deterministic AST-to-prose transpilation and double-blind, statistically independent neural agents.
- **[Paper Submission Design Document](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md)** (`paper_submission_design_doc.md`): Authoritative research paper design, specification calculus, information-flow isolation invariants, multi-gate verification pipeline, non-functional auditing matrix with hidden benchmark firewall, and 7-RQ experimental evaluation plan.
- **[Empirical Benchmark Suite & Cross-Model Evaluation Design Document](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/benchmark_design_doc.md)** (`benchmark_design_doc.md`): Authoritative empirical benchmarking design document operationalizing Task 2 and the research paper's 7 Research Questions (RQ1–RQ7), defining the 4-tier model spectrum (Local Qwen, Budget DeepSeek/Gemini, Mid-Tier o3-mini/Sonnet, Frontier Argon/Opus/Sol), golden oracle benchmark suites, and automated evaluation tooling (`bin/evaluate_model_efficiency.py`).
- **[Pretense: Stateful State-Machine Verification & Fake Synthesis](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/pretense.md)** (`pretense.md`): Architectural design, empirical genesis, and implementation roadmap for Pretense—Cleanroom's unified state-machine-driven testing, verification, and fake synthesis engine. Integrates cross-model differential defect analysis (investigating coincident cognitive blind spots under 95% statement coverage), class-based state machine DSL (`StateMachine` and `@transition`), pure reference models via `TransitionContext`, dual-role fake synthesis (`sm.as_fake`) and test driver dispatch, stateful property fuzzing with Hypothesis to eliminate errors of omission, and empirical baseline equalization benchmarks.
- **[Dual-Baseline Synthesis & Differential Fuzzing](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/dual_baseline.md)** (`dual_baseline.md`): Comparative design document evaluating Dual-Baseline Synthesis with Differential Hypothesis Fuzzing against Cleanroom's Double-Blind Pipeline on an equal footing, addressing shared omission and underspecification vulnerabilities, token economics, and empirical benchmark protocols.

