# Cleanroom Architecture, Execution Paradigms, Progress & Master Roadmap

> **Authoritative Master Operational & Roadmap Document**  
> This document consolidates Cleanroom's system execution status, operational workflows, completed milestones, and forward actionable roadmap.
> For in-depth technical specifications, physical sandboxing models, in-band metadata parsing algorithms, and system designs, see the companion document: [`design.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/design.md).
>
> *(Note: Foundational specification language semantics and formal academic papers are maintained separately in [`grounded_specification_language_and_neural_compilation.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/grounded_specification_language_and_neural_compilation.md) and [`paper_submission_design_doc.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md)).*

---

## Table of Contents

1. [Executive Summary & Core Philosophy](#1-executive-summary--core-philosophy)
2. [Modular System Architecture (`update_with_ai/parts/*`)](#2-modular-system-architecture-update_with_aiparts)
3. [Execution Paradigms & Historical Post-Mortems](#3-execution-paradigms--historical-post-mortems)
   - [Comparative Paradigm Matrix](#comparative-paradigm-matrix)
   - [Option 4: Subagent-Driven with Zero-Execution Coordinator (Primary)](#option-4-subagent-driven-with-zero-execution-coordinator-primary)
   - [Option 3: Subagentless Interactive Cleanroom](#option-3-subagentless-interactive-cleanroom)
   - [Option 1: Custom In-Process Headless Loop](#option-1-custom-in-process-headless-loop)
   - [Option 2 Post-Mortem: Why In-Tree FastMCP Subagents Failed](#option-2-post-mortem-why-in-tree-fastmcp-subagents-failed)
   - [Goose Harness Post-Mortem: Why Goose Was Decommissioned](#goose-harness-post-mortem-why-goose-was-decommissioned)
4. [In-Band Source Metadata, Dirtiness & Auditor Architecture](#4-in-band-source-metadata-dirtiness--auditor-architecture)
   - [Logless Design & In-Band Headers](#logless-design--in-band-headers)
   - [Star-Dependency Propagation & Dirtiness Calculation](#star-dependency-propagation--dirtiness-calculation)
   - [Logless Auditor Roles (`spec_qa`, `qa`, `coverage`)](#logless-auditor-roles-spec_qa-qa-coverage)
   - [Feedback Injection & Context Budget Protection](#feedback-injection--context-budget-protection)
5. [Specification Grounding & Boundary Assembly](#5-specification-grounding--boundary-assembly)
   - [The Grounding Invariant](#the-grounding-invariant)
   - [Physical Workspace Assembly & Permission Masking](#physical-workspace-assembly--permission-masking)
   - [Elimination of Legacy Build Artifacts](#elimination-of-legacy-build-artifacts)
6. [Packaging, Distribution & CLI Command Reference](#6-packaging-distribution--cli-command-reference)
   - [Native Python Packaging (`pyproject.toml` + `uv`)](#native-python-packaging-pyprojecttoml--uv)
   - [Comprehensive CLI Reference](#comprehensive-cli-reference)
7. [Multi-Harness Telemetry & Desktop Integration](#7-multi-harness-telemetry--desktop-integration)
   - [DeepSeek Harness (`dsh`), Direct JSON-RPC Integration & Cordis Shell](#deepseek-harness-dsh-direct-json-rpc-integration--cordis-shell)
   - [Google Antigravity Integration & Rate Economics](#google-antigravity-integration--rate-economics)
8. [Current Implementation Progress & Verification Health](#8-current-implementation-progress--verification-health)
9. [Master Actionable Roadmap & Next TODOs](#9-master-actionable-roadmap--next-todos)
   - [Task 1: DSH Remote JSON-RPC Orchestration & Desktop Session Reconciliation](#task-1-dsh-remote-json-rpc-orchestration--desktop-session-reconciliation)
   - [Task 2: Phase 3 Harness Adapters (Claude Code & OpenAI Codex CLI)](#task-2-phase-3-harness-adapters-claude-code--openai-codex-cli)
   - [Task 3: Phase 4 Cross-Model Empirical Benchmarking Suite](#task-3-phase-4-cross-model-empirical-benchmarking-suite)
   - [Task 4: Multi-Wave End-to-End Orchestration Stress Testing](#task-4-multi-wave-end-to-end-orchestration-stress-testing)
   - [Task 5: Standalone Ephemeral Distribution (`uvx cleanroom`)](#task-5-standalone-ephemeral-distribution-uvx-cleanroom)
   - [Task 6: Role Workspace Metadata Filtering & Ephemeral Code Hashing](#task-6-role-workspace-metadata-filtering--ephemeral-code-hashing)
   - [Task 7: Dirty Reasoning Propagation & LAST_CLEANED Preservation](#task-7-dirty-reasoning-propagation--last_cleaned-preservation)

---

## 1. Executive Summary & Core Philosophy

Cleanroom is an agentic software development and neural compilation framework designed to eliminate hallucination, architectural drift, and accidental contamination in autonomous AI coding pipelines.

```
       ┌────────────────────────────────────────────────────────┐
       │             High-Level Specification (HLS)             │
       │                   (high/*.md)                          │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │                 Planning Specification                 │
       │                 (planning/*.md)                        │
       └───────────────────────────┬────────────────────────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
       ┌─────────────────────┐           ┌──────────────────────┐
       │ Concrete Scenarios  │           │ Low-Level Spec (AST) │
       │  (scenarios/*.md)   │           │    (low/*.pyi)       │
       └──────────┬──────────┘           └──────────┬───────────┘
                  │                                 │
                  │        ┌──────────────┐         │
                  └───────►│   Spec QA    │◄────────┘
                           │   Auditor    │
                           └──────┬───────┘
                                  │
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
       ┌─────────────────────┐           ┌──────────────────────┐
       │   Unit Tests        │           │    Library Code      │
       │ (tests/*_test.py)   │           │     (lib/*.py)       │
       └──────────┬──────────┘           └──────────┬───────────┘
                  │                                 │
                  │        ┌──────────────┐         │
                  └───────►│  QA Arbiter  │◄────────┘
                           │  & Coverage  │
                           └──────────────┘
```

### Core Principles

1. **Mandatory Specification-First (HLS-First)**:
   Code and tests are derivative artifacts, never primary sources of truth. Any functional change or bug fix must originate in the High-Level Specification (`high/*.md`) and cascade deterministically downstream:
   $$\text{HLS} \longrightarrow \text{Planning} \longrightarrow \text{Scenarios} \land \text{Low} \longrightarrow \text{Spec QA} \longrightarrow \text{Lib} \land \text{Tests} \longrightarrow \text{QA} \land \text{Coverage}$$
   Every defect in code is treated as an upstream defect in specification. Stealth edits to `lib/` or `tests/` are rejected.

2. **Physical Double-Blind Isolation via Operating System Permissions**:
   Software-based "prompt agreements" or in-process interception hooks fail under scale. Cleanroom enforces double-blind isolation physically at the OS filesystem level. Downstream artifacts are authored in ephemeral sibling workspaces where upstream specifications are mounted read-only (`chmod 444`), sibling roles are hidden, and test code cannot be read by library implementers (and vice versa).

3. **Logless State & In-Band Source Metadata**:
   Cleanroom maintains zero external state databases, SQLite registries, or out-of-band audit log files. All lifecycle state—including Git commit hashes (`LAST_CLEANED`, `LAST_CHANGED`, `CODE_HASH`), auditor verification stamps, and targeted feedback—is stored directly in the source artifacts as in-band metadata headers.

4. **Zero-Execution Coordinator**:
   In multi-agent orchestration, the top-level supervisor never executes domain code, runs tests, or modifies source files. The coordinator acts purely as a DAG scheduler, inspecting cleanliness, calculating parallel execution waves, provisioning physical workspaces, and dispatching workspace-bound workers.

---

## 2. Modular System Architecture (`update_with_ai/parts/*`)

Cleanroom has been decomposed from a monolithic script into modular, single-responsibility packages under `update_with_ai/parts/`:

```
update_with_ai/parts/
├── tools/          # Verification, linter, pyright, and pytest runners
├── storage/        # In-band metadata parser, hash manifest, dirtiness DAG
├── workspace/      # Physical sibling workspace provisioning & OS chmod masking
├── subagent/       # Wave-based multi-agent scheduler & worker execution
├── control/        # CLI commands, target resolution, and methodology discovery
├── loop/           # In-process autonomous agent execution loop (Option 1)
├── dsh/            # DeepSeek Harness integration, telemetry daemon, Cordis patches
├── antigravity/    # Google Antigravity coordinator & subagent integration
├── openai/         # Direct LLM client integration for custom loops
├── systems/        # Platform detection, OS shell subprocess runner
└── uv/             # Isolated virtual environment management
```

### Module Responsibilities

- **`parts/tools`**: Encapsulates language-agnostic verification pipelines. Executes linters, Pyright type checking, pytest suites, and Markdown scenario validators. Exposes deterministic `run_tests()` and `run_lint()` APIs.
- **`parts/storage`**: Manages the single source of truth. Parses and updates in-band metadata headers (`LAST_CLEANED`, `LAST_CHANGED`, `CODE_HASH`, `FEEDBACK:`). Calculates Git object tree hashes, derives the star-dependency DAG, and identifies dirty nodes.
- **`parts/workspace`**: Manages ephemeral physical sandboxes (`../role_workspaces/<session>/...`). Handles symlink creation, package-root projection, and read-only permission masking (`chmod 444`) to enforce double-blind isolation.
- **`parts/subagent`**: Orchestrates parallel wave execution. Groups non-dependent dirty nodes into concurrent execution waves and manages subagent process lifecycles.
- **`parts/control`**: Houses the Cleanroom CLI suite (`orchestrate`, `clean`, `commission`, `submit`, `fail`, `work-queue`, etc.) and methodology resolution logic (`cleanroom_roles.toml`).
- **`parts/loop`**: The self-contained autonomous agent loop for Option 1, executing LLM completion calls, tool invocations, and test verification without an external IDE harness.
- **`parts/dsh`**: Integrates with DeepSeek Harness (`dsh`). Provides background telemetry streaming via `dsh_telemetry`, Cordis UI status injection, and worker instructions.
- **`parts/antigravity`**: Integrates with Google Antigravity. Defines the zero-execution coordinator prompt, installs the coordinator agent, and formats subagent invocation payloads.
- **`parts/openai`**: Provides OpenAI-compatible API bindings for custom headless loop execution.
- **`parts/systems`**: Cross-platform system utilities, environment detection, and POSIX file permission wrappers.
- **`parts/uv`**: Manages Python virtual environments, resolving packages dynamically via `uv` without system pollution.

---

## 3. Execution Paradigms & Historical Post-Mortems

Cleanroom supports three primary operational paradigms, synthesized from extensive empirical trials.

### Comparative Paradigm Matrix

| Dimension | Option 1: Custom Loop (`--harness loop`) | Option 3: Subagentless Workspaces | Option 4: Subagent-Driven Workspaces (Primary) | Option 2: In-Tree FastMCP Subagents (*Decommissioned*) |
| :--- | :--- | :--- | :--- | :--- |
| **Execution Model** | Autonomous in-process Python loop | Interactive single-agent / developer CLI | Multi-agent wave scheduler + zero-execution coordinator | Hierarchical subagents in single working directory |
| **Context Isolation** | None (Single API conversation context) | Complete (Separate interactive chats or human turns) | Complete (Physical OS workspace per subagent) | Weak (Software prompt instructions; single directory) |
| **Sandbox Boundary** | In-process execution | Ephemeral sibling directories (`chmod 444`) | Ephemeral sibling directories (`chmod 444`) | Software hooks (`cleanroom_sandbox_hook.py`) |
| **Harness Support** | Headless CLI (Any OpenAI/Gemini endpoint) | Any terminal, IDE, or chat agent | Google Antigravity, DeepSeek Harness (`dsh`) | FastMCP server via Antigravity tool calling |
| **Token Efficiency** | High (Direct targeted prompt calls) | Very High (Zero supervisor token overhead) | Optimal (Parallel subagents, bounded wave contexts) | Catastrophic (10x-20x explosion via tool churn) |
| **Verification State** | Production-ready | Production-ready | Production-ready | **Failed & Permanently Archived** |

---

### Option 4: Subagent-Driven with Zero-Execution Coordinator (Primary)

Option 4 combines the physical isolation of sibling workspaces with autonomous multi-agent wave scheduling.

```
                      ┌────────────────────────────────────────┐
                      │      Cleanroom Coordinator Agent       │
                      │       (Zero-Execution Supervisor)      │
                      └───────────────────┬────────────────────┘
                                          │
                        Calculates Wave 1 │ (Independent Nodes)
                                          ▼
                ┌──────────────────────────────────────────────────┐
                │ Wave 1: Parallel Workspace-Bound Subagents       │
                │                                                  │
                │  ┌────────────────────┐  ┌────────────────────┐  │
                │  │ Subagent: Scope A  │  │ Subagent: Scope B  │  │
                │  │ Role: planning     │  │ Role: planning     │  │
                │  │ Workspace: ws_a_pl │  │ Workspace: ws_b_pl │  │
                │  └─────────┬──────────┘  └─────────┬──────────┘  │
                └────────────┼───────────────────────┼─────────────┘
                             │ Both Clean            │
                             ▼                       ▼
                        Calculates Wave 2 (Downstream Dependents)
                                          │
                ┌─────────────────────────┴────────────────────────┐
                │ Wave 2: Parallel Workspace-Bound Subagents       │
                │                                                  │
                │  ┌────────────────────┐  ┌────────────────────┐  │
                │  │ Subagent: Scope A  │  │ Subagent: Scope A  │  │
                │  │ Role: scenarios    │  │ Role: low          │  │
                │  │ Workspace: ws_a_sc │  │ Workspace: ws_a_lo │  │
                │  └────────────────────┘  └────────────────────┘  │
                └──────────────────────────────────────────────────┘
```

#### The Zero-Execution Coordinator Contract
- **No File Edits**: The coordinator never creates, modifies, or deletes repository files.
- **No Test Execution**: The coordinator never runs `bin/test`, `pytest`, or `pyright`.
- **Pure Scheduling**: The coordinator evaluates the dirtiness DAG (`uv run cleanroom work-queue`), groups independent nodes into concurrent waves, commissions workspaces, and invokes subagents.
- **Autonomous Directive**: When launched via `uv run cleanroom orchestrate <scope>`, the CLI outputs the autonomous coordinator directive, signaling the agentic host to invoke `cleanroom_coordinator` without human intervention.

---

### Option 3: Subagentless Interactive Cleanroom

Designed for human-in-the-loop development or single-agent IDE execution (such as Antigravity chat, Cursor, or VS Code):
- **User or Supervisor Turn**: Inspects work queue via `uv run cleanroom work-queue <scope>`.
- **Commissioning**: Runs `uv run cleanroom commission <target>#<role>` to build an isolated sibling directory in `../role_workspaces/<session>/`.
- **Worker Execution**: The agent or developer switches context to the sibling workspace, edits the isolated target, and tests via `bin/test`.
- **Promotion**: Runs `uv run cleanroom submit <target>#<role>`, verifying tests and updating in-band metadata.
- **Rejection**: If upstream defects are found, runs `uv run cleanroom fail <target>#<role> --reason="..."` or `blame`, injecting feedback into upstream headers.

---

### Option 1: Custom In-Process Headless Loop

An autonomous in-process agent runner for headless environments and CI/CD pipelines (`uv run cleanroom clean <target> --harness loop`):
- Connects directly to OpenAI, Gemini, or local LLM inference endpoints.
- Runs a deterministic ReAct loop: Prompts model with active guide and target $\to$ executes tool calls (file edit, test run) $\to$ feeds output back $\to$ loops until `bin/test` passes and target is stamped clean.

---

### Option 2 Post-Mortem: Why In-Tree FastMCP Subagents Failed

In early architectural iterations, Cleanroom attempted to enforce role isolation in-tree within a single shared working directory using an external FastMCP server daemon and Antigravity `PreToolUse` hooks (`cleanroom_sandbox_hook.py`).

**Root Causes of Failure**:
1. **Context Window Token Explosion**: The coordinator and all subagents shared a single monolithic context. Tool definitions, MCP schemas, stdout/stderr streams, and file diffs accumulated rapidly, consuming over 1,500,000 tokens within 3–4 cleaning turns and triggering rate-limit quotas under Google One Ultra.
2. **Tool-Call Indirection Overhead**: Subagents did not read/write files directly; they routed calls through FastMCP endpoints (`cleanroom_read_file`, `cleanroom_write_file`), introducing high serialization latency and frequent JSON truncation.
3. **Flaky Daemon Process Lifecycles**: The long-running FastMCP background process suffered from socket disconnections, orphan daemon locks, and zombie processes across IDE restarts.
4. **Lack of OS-Level Enforcement**: Software hooks were repeatedly bypassed by models inventing shell commands or using alternate edit tools.

*Decision*: Option 2 was completely decommissioned and replaced by Option 4 (Physical Workspaces + Native Subagents).

---

### Goose Harness Post-Mortem: Why Goose Was Decommissioned

An experimental harness adapter for the Block Goose CLI agent (`--harness goose`) was developed and evaluated.

**Root Causes of Decommissioning**:
1. **Unstable Subprocess IPC**: Goose relied on an interactive terminal session that lacked a structured JSON RPC interface, causing frequent deadlock during long-running test suites.
2. **Lack of Workspace Sandboxing**: Goose lacked native support for switching working directories per-turn, requiring aggressive shell symlink swapping that corrupted concurrent runs.
3. **Redundancy with DSH and Antigravity**: DeepSeek Harness (`dsh`) provided identical local CLI capabilities with superior structured telemetry, socket streaming, and zero process flakiness.

*Decision*: Goose integration was turndowned and purged from the active harness suite.

---

## 4. In-Band Source Metadata, Dirtiness & Auditor Architecture

### Logless Design & In-Band Headers

Cleanroom rejects out-of-band databases. All state is embedded directly inside the managed source files using in-band comment headers:

#### Markdown Artifacts (`high/*.md`, `planning/*.md`, `scenarios/*.md`)
```markdown
<!-- CLEANROOM METADATA
LAST_CLEANED: a1b2c3d4e5f678901234567890abcdef12345678
LAST_CHANGED: a1b2c3d4e5f678901234567890abcdef12345678
CODE_HASH: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
-->
```

#### Python / Python Interface Artifacts (`low/*.pyi`, `lib/*.py`, `tests/*_test.py`)
```python
# CLEANROOM METADATA
# LAST_CLEANED: a1b2c3d4e5f678901234567890abcdef12345678
# LAST_CHANGED: a1b2c3d4e5f678901234567890abcdef12345678
# CODE_HASH: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

- **`LAST_CLEANED`**: The Git tree commit hash at the moment this node successfully passed all verification checks and was stamped clean.
- **`LAST_CHANGED`**: The Git tree commit hash of the latest modification to this file or any of its upstream dependency contracts.
- **`CODE_HASH`**: SHA-256 hash of the sanitized file body (excluding metadata header comments).

---

### Star-Dependency Propagation & Dirtiness Calculation

A node is considered **DIRTY** if:
1. It has never been stamped (`LAST_CLEANED` is absent).
2. Its file content changed without a clean stamp (`CODE_HASH != sha256(body)`).
3. Any immediate upstream dependency has a `LAST_CHANGED` hash that differs from this node's `LAST_CLEANED` hash.

```
       Upstream Spec (high/core.md)
       [LAST_CHANGED = commit_B]
                 │
                 ▼ (Upstream changed!)
       Downstream Spec (planning/core.md)
       [LAST_CLEANED = commit_A]  <--- DIRTY (commit_A != commit_B)
```

When an upstream artifact is submitted with changes, Cleanroom propagates `LAST_CHANGED = current_head` downstream along the star-dependency DAG, instantly marking all dependents dirty.

---

### Logless Auditor Roles (`spec_qa`, `qa`, `coverage`)

Auditor roles do not generate new code files; they certify relationships between existing artifacts:
- **`spec_qa`**: Verifies that `low/*.pyi` and `scenarios/*.md` completely ground `planning/*.md`.
- **`qa`**: Verifies that `tests/*_test.py` thoroughly verifies `lib/*.py` against `low/*.pyi`.
- **`coverage`**: Verifies statement and semantic branch coverage.

Auditor stamps are embedded directly in the target file header:
```python
# SPEC_QA_AUDIT: 2026-10-16T12:00:00Z PASSED git:a1b2c3d4
# QA_AUDIT: 2026-10-16T12:05:00Z PASSED git:a1b2c3d4
```

---

### Feedback Injection & Context Budget Protection

When an auditor rejects a submission or a worker blames an upstream spec, feedback is prepended directly to the metadata header of the defective upstream file:
```markdown
<!-- CLEANROOM METADATA
FEEDBACK: [from qa at 2026-10-16T12:10:00Z]
Target method `resolve_scope` fails when given relative paths containing '../'.
Fix contracts in high/core.md to specify path normalization invariants.
LAST_CLEANED: ...
-->
```

**Context Budget Protection**:
To prevent infinite prompt bloat, the feedback channel is strictly budget-bounded:
- `max_feedback_chars = 1000` (configurable in `cleanroom.toml`).
- Older feedback entries are automatically truncated or evicted when new feedback is injected.
- Upon successful clean stamping of the defective node, the `FEEDBACK:` block is wiped clean.

---

## 5. Specification Grounding & Boundary Assembly

### The Grounding Invariant

Every implementation detail in `lib/*.py` must be explicitly grounded in upstream specifications. Uncontracted code or speculative helper functions are strictly prohibited.

In `low/*.pyi`, every internal class, method, or non-public import must contain an explicit `GROUNDING:` docstring defining its role:
```python
class PathNormalizer:
    """Utility for sanitizing user-supplied relative path strings.
    
    GROUNDING:
    Implements path normalization invariants specified in planning/core.md Section 3.2.
    Required by WorkspaceResolver to prevent directory traversal attacks.
    """
    def normalize(self, raw_path: str) -> str: ...
```

---

### Physical Workspace Assembly & Permission Masking

When Cleanroom provisions a workspace (`parts/workspace`), it mounts files into an isolated sibling directory:
- **Target File**: Staged as a writable file (`chmod 644`).
- **Upstream Dependencies**: Mounted as read-only symlinks or copies with write protection (`chmod 444`).
- **Hidden Artifacts**: Sibling role files (e.g., `tests/` for a `lib/` worker, or `lib/` for a `tests/` worker) are excluded entirely to maintain double-blind purity.
- **Package Projections**: Top-level packages are symlinked so native imports (`import update_with_ai...`) resolve seamlessly without path-munging hacks.

---

### Elimination of Legacy Build Artifacts

Cleanroom has completely eliminated legacy Bazel artifacts:
- Purged all `MODULE.bazel`, `BUILD.bazel`, and `bazel_manifest_ext` references.
- All workspace resolution relies dynamically on Git repository roots, `pyproject.toml`, or `BUILD_WORKSPACE_DIRECTORY`.

---

## 6. Packaging, Distribution & CLI Command Reference

### Native Python Packaging (`pyproject.toml` + `uv`)

Cleanroom is packaged as a standard Python application using `hatchling` and managed via `uv`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cleanroom"
version = "0.1.0"
dependencies = [
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "tomli>=2.0; python_version < '3.11'",
]

[project.scripts]
cleanroom = "update_with_ai.parts.control.lib.cleanroom_cli:main"
```

---

### Comprehensive CLI Reference

All commands are invoked via `uv run cleanroom <command>`:

| Command | Usage | Description |
| :--- | :--- | :--- |
| **`orchestrate`** | `cleanroom orchestrate <scope> [target_role]` | Dispatches autonomous multi-agent wave coordinator (Option 4). |
| **`clean`** | `cleanroom clean <scope> [target_role] [--harness loop\|dsh\|antigravity]` | Executes cleaning pipeline using specified harness. |
| **`work-queue`** | `cleanroom work-queue <scope> [target_role]` | Displays topological DAG order of dirty nodes requiring cleaning. |
| **`commission`** | `cleanroom commission <target>#<role>` | Provisions isolated sibling workspace with `chmod 444` masks. |
| **`decommission`**| `cleanroom decommission <target>#<role>` | Tears down and deletes an active sibling workspace sandbox. |
| **`submit`** | `cleanroom submit <target>#<role> --change-summary="..."` | Runs tests, verifies contracts, and stamps target clean. |
| **`fail`** | `cleanroom fail <target>#<role> --reason="..."` | Rejects target and records failure reason in feedback header. |
| **`feedback`** | `cleanroom feedback <target>#<role>` | Displays active feedback and audit stamps for a target. |
| **`blame`** | `cleanroom blame <target>#<role> --upstream=<node> --reason="..."` | Injects defect feedback into upstream specification header. |
| **`mark-clean`** | `cleanroom mark-clean <target>#<role>` | Explicitly stamps target clean without modifying code. |
| **`dirty`** | `cleanroom dirty <scope>` | Lists all dirty nodes and their triggering dependency causes. |
| **`coverage`** | `cleanroom coverage <scope>` | Evaluates test suite statement and semantic branch coverage. |
| **`check_files`** | `cleanroom check_files <scope>` | Validates file format compliance, line breaks, and headers. |

---

## 7. Multi-Harness Telemetry & Desktop Integration

### DeepSeek Harness (`dsh`), Direct JSON-RPC Integration & Cordis Shell

Cleanroom provides deep integration with DeepSeek Harness (`dsh`) across both direct JSON-RPC client-server communication and local CLI workflows:

1. **Direct JSON-RPC Remote Orchestration**:
   - Cleanroom connects directly to the running DeepSeek Harness server over JSON-RPC via HTTP.
   - Discovers active desktop endpoints and authentication credentials dynamically from the Cordis desktop SQLite cookie store (`cookies.sqlite`).
   - Invokes structured RPC methods (`workspace/create`, `session/create`, `session/prompt`) to drive subagent turns directly against the running server.
   - Completely eliminates kernel write-lease contention (`flock` on `session.lock`) when running alongside an active Cordis desktop UI session, preventing UI session forking and deadlocks.
   - Retains automatic fallback to headless CLI invocation (`dsh exec`) when no desktop server instance is discovered.

2. **`dsh_telemetry` Background Daemon**:
   - Runs a non-blocking UNIX domain socket server listening for subagent lifecycle events.
   - Emits structured JSON events: `{"event": "subagent_start", "scope": "...", "role": "...", "workspace": "..."}`.
   - Tracks per-turn token usage, execution time, and tool call frequency.

3. **Cordis Desktop Shell Overlay**:
   - Injects real-time status badges into the Cordis desktop shell.
   - Displays active cleaning waves, dirty dependency DAGs, and subagent process health.

---

### Google Antigravity Integration & Rate Economics

In Google Antigravity environments:
- Cleanroom registers the `cleanroom_coordinator` agent definition.
- Emits the `AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE` for zero-friction handoff.
- Employs token-conscious prompting adhering to production rate limits:

| Model Tier | Cost per 1M Input Tokens | Cost per 1M Output Tokens | Role Suitability |
| :--- | :--- | :--- | :--- |
| **Gemini 2.5 Flash** | \$0.075 | \$0.30 | High-speed linting, scenario formatting, syntax validation |
| **Gemini 2.5 Pro** | \$1.25 | \$5.00 | Planning, low-level spec generation, complex test authoring |
| **Gemini 3.0 Pro** | \$2.50 | \$10.00 | Architectural HLS authoring, cross-package arbitration |

---

## 8. Current Implementation Progress & Verification Health

### Completed Milestones

- [x] **Phase 0: Baseline Specification & Formatting Engine**
  - High-level, Planning, Scenario, and Low-level specification formats codified.
  - In-band metadata specification finalized and implemented.
- [x] **Phase 1: Core Cleanroom Architecture & Workspaces**
  - Physical sibling workspace provisioner with OS `chmod 444` permission masks.
  - Dynamic star-dependency dirtiness graph calculation.
  - Complete CLI suite implemented under native Python (`hatchling` + `uv`).
  - Logless auditor roles (`spec_qa`, `qa`, `coverage`) with bounded feedback injection.
- [x] **Phase 2: Modular Decomposition & Multi-Harness Integration**
  - Decomposed monolith into modular `parts/*` structure.
  - Option 1 (Custom Headless Loop) fully operational.
  - Option 3 (Subagentless Interactive Workspaces) fully operational.
  - Option 4 (Subagent-Driven Wave Coordinator) fully operational.
  - DeepSeek Harness (`dsh`) telemetry daemon and Cordis desktop shell overlay completed.
  - Decommissioned legacy FastMCP daemon (Option 2) and Goose CLI adapter.
- [x] **Phase 3: DSH Remote JSON-RPC Orchestration & Desktop Session Reconciliation (Task 1)**
  - Dual-mode subagent turn dispatch implemented in `parts/dsh`: opportunistic JSON-RPC bridge when DSH Desktop / server is active, with headless CLI fallback.
  - Full specification cascade completed across HLS, Planning, Scenarios, Low-level stubs, Library implementations, and Unit tests.
  - Zero `session.lock` contention with live desktop UI; real-time session streaming preserved.
  - Option A (`maxDepth: 2` native coordinator) analyzed and documented for future adoption.
- [x] **Phase 4: Role Workspace Metadata Filtering & Ephemeral Code Hashing (Task 6)**
  - Metadata maintained canonically in main repository; role workspaces receive projected headers exposing only `CHANGE`, `FEEDBACK`, and ephemeral `CODE_HASH`.
  - Ephemeral `CODE_HASH` computed dynamically on writable files during commissioning and synchronization.
  - Harvest and direct submission strip `CODE_HASH` from canonical files in the main workspace and refresh ephemeral `CODE_HASH` in role workspaces.
  - Unmodified submissions preserve canonical `LAST_CHANGED` timestamps and metadata.
  - Loop harness continues unmediated operation directly against main workspace metadata.
- [x] **Phase 5: Dirty Reasoning Propagation & LAST_CLEANED Preservation (Task 7)**
  - Preserved canonical `LAST_CLEANED` timestamp when marking nodes dirty (`dag_storage.mark_node_dirty`), using `# DIRTY: <reason>` as the definitive in-band dirty indicator without erasing clean provenance.
  - Reordered dirtiness checks in `src_storage_impl.py` and `dirtiness_impl.py` to evaluate explicit `DIRTY:` tags and `FEEDBACK:` messages before checking `LAST_CLEANED`.
  - Replaced misleading diagnostic message `Header missing LAST_CLEANED in {target}` with `Target has not been cleaned ({target})`.
  - Enriched Rule 4 ("Metadata Projection & Inviolability") across `AGENTS.md` and role worker prompts (`cleanroom_role_tool.py`), explicitly instructing LLM subagents that role workspaces intentionally project out lifecycle timestamps so workers never diagnose missing `LAST_CLEANED` as a defect.
  - Cascaded across full specification pipeline: HLS (`high/`) $\to$ Planning (`planning/`) $\to$ Scenarios (`scenarios/`) $\to$ Low (`low/`) $\to$ Lib (`lib/`) $\to$ Tests (`tests/`).
  - Validated end-to-end multi-agent convergence with `uv run cleanroom clean staging#qa --harness antigravity` using the autonomous `cleanroom_coordinator`.

### Current Verification Health

Cleanroom maintains 100% test pass rates across all validation suites:
- **`bin/test`**: **627 passed tests, 9 subtests passed**
- **Pyright Type Checking**: **0 errors, 0 warnings, 0 informations**
- **Specification Linter**: **127 High-Level, 101 Planning, 127 Low-Level specifications validated**

---

## 9. Master Actionable Roadmap & Next TODOs

The following prioritized roadmap outlines the next development tasks for Cleanroom engineering (excluding academic paper drafting and neural language specification, which are tracked independently).

---

### [COMPLETED] Task 1: DSH Remote JSON-RPC Orchestration & Desktop Session Reconciliation
- **Status**: Completed (2026-10-18)
- **Component**: `update_with_ai/parts/dsh/`
- **Architecture**: Option B (Python Remote Coordinator over JSON-RPC client-server bridge to DSH Server / Cordis Desktop), with Option A analysis preserved for future adoption.
- **Problem**: When the DeepSeek Harness CLI (`dsh`) runs concurrently with an active Cordis desktop UI session, kernel write leases (`flock` on `session.lock`) block CLI turn dispatch, causing session forking and frozen UI conversations.
- **Implementation Completed**:
  1. [x] Updated HLS in `parts/dsh/high/dsh_harness.md` and `parts/dsh/high/dsh_harness_impl.md` specifying dual-mode turn dispatch (opportunistic JSON-RPC bridge when DSH Desktop / server is active, with headless CLI fallback).
  2. [x] Grounded DSH wire protocol and cookie discovery in `parts/dsh/high/dsh_ext.md` and `parts/dsh/low/dsh_ext.pyi`.
  3. [x] Implemented JSON-RPC turn dispatch (`workspace/create`, `session/create`, `session/prompt`), server discovery via immutable SQLite Cookies DB, and status polling in `parts/dsh/lib/dsh_telemetry_impl.py` and `parts/dsh/lib/dsh_harness_impl.py`.
  4. [x] Cascaded downstream across all Cleanroom phases: Planning $\to$ Scenarios $\to$ Low $\to$ Lib $\to$ Unit Tests.
  5. [x] Analyzed and documented Option A (`maxDepth: 2` support in `@deepseek-ai/dsh-tool-subagent`) for future native agentic coordinator adoption.

---


### Task 2: Phase 3 Harness Adapters (Claude Code & OpenAI Codex CLI)
- **Priority**: High
- **Component**: `update_with_ai/parts/harnesses/`
- **Objective**: Expand Cleanroom's multi-agent execution beyond Antigravity and DSH to support Anthropic Claude Code and OpenAI Codex CLI.
- **Implementation Steps**:
  1. Author HLS in `parts/control/high/external_harness_adapters.md`.
  2. Define uniform `HarnessAdapter` interface supporting `spawn_worker()`, `await_turn()`, and `collect_telemetry()`.
  3. Implement `ClaudeCodeHarnessAdapter` invoking `claude --dangerously-skip-permissions` inside sibling workspaces.
  4. Implement `CodexHarnessAdapter` utilizing OpenAI developer CLI primitives.
  5. Add unit test suite verifying workspace isolation and clean exit codes across all adapters.

---

### Task 3: Phase 4 Cross-Model Empirical Benchmarking Suite
- **Priority**: Medium
- **Component**: `bin/evaluate_model_efficiency.py`
- **Objective**: Provide automated benchmarking measuring token cost, turn latency, and specification adherence across competing frontier models.
- **Implementation Steps**:
  1. Author specification in `parts/tools/high/benchmark_runner.md`.
  2. Build benchmarking matrix covering:
     - Gemini 2.5 Flash / Pro
     - Gemini 3.0 Pro
     - Claude 3.7 Sonnet (Thinking & Non-Thinking)
     - DeepSeek V3 & R1
     - OpenAI o3-mini / GPT-4.5
  3. Execute automated test runs across standardized Cleanroom parts (`parts/storage`, `parts/tools`).
  4. Output comparative Markdown report with token efficiency and pass-rate metrics.

---

### Task 4: Multi-Wave End-to-End Orchestration Stress Testing
- **Priority**: Medium
- **Component**: `update_with_ai/parts/subagent/tests/`
- **Objective**: Rigorously test the zero-execution coordinator under deep dependency hierarchies (4+ waves deep, 10+ concurrent subagents).
- **Implementation Steps**:
  1. Create synthetic mock project tree with complex diamond and star dependencies.
  2. Simulate simulated worker failures and verify upstream `blame` feedback propagation.
  3. Confirm that wave barriers properly block downstream execution until all upstream workers succeed.
  4. Assert that orphan workspaces are cleanly decommissioned on SIGINT/SIGTERM.

---

### Task 5: Standalone Ephemeral Distribution (`uvx cleanroom`)
- **Priority**: Low
- **Component**: `pyproject.toml`, distribution scripts
- **Objective**: Enable developers to run Cleanroom on any target project without cloning the Cleanroom codebase (`uvx cleanroom orchestrate .`).
- **Implementation Steps**:
  1. Audit package data inclusion in `pyproject.toml` to ensure methodology templates and default configs are bundled into wheels.
  2. Test `uvx --from . cleanroom --help` in an isolated directory.
  3. Provide pre-built binary distributions via GitHub Releases.

---

### [COMPLETED] Task 6: Role Workspace Metadata Filtering & Ephemeral Code Hashing
- **Status**: Completed (2026-10-18)
- **Component**: [`update_with_ai/parts/metadata/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/metadata/), [`update_with_ai/parts/workspace/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/), [`update_with_ai/parts/control/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/)
- **Objective**: Manage metadata primarily in the main workspace, expose only projected fields (`CHANGE`, `FEEDBACK`, and ephemeral `CODE_HASH`) to role workspaces, compute `CODE_HASH` dynamically on writable files during sync, and strip `CODE_HASH` when syncing back to main.
- **Specification & Behavioral Invariants**:
  1. **Primary Metadata in Main Workspace**: Metadata is primarily maintained in the main workspace. Canonical lifecycle headers (such as `LAST_CLEANED`, `LAST_CHANGED`, and audit attestation stamps) live in the main workspace and are not projected into worker workspaces.
  2. **Role Workspace Projection Filtering**: Only `CHANGE`, `FEEDBACK`, and `CODE_HASH` are visible when files are moved over to the role workspace. All other metadata fields are filtered out to protect context budgets, eliminate prompt noise, and prevent accidental tampering by role subagents.
  3. **Ephemeral Code Hash**: The `CODE_HASH` is not preserved in the main workspace. Instead, it is computed dynamically on writable files when the role workspace is synced, and is only used to determine if the agent updated a file or not in the role workspace.
  4. **Harvest & Sync-Back Strip**: When a file is synced back (harvested) or submitted to the main workspace, the ephemeral `CODE_HASH` is removed and not written back to the canonical file in the main workspace, while the role workspace copy is refreshed with a newly computed ephemeral code hash.
  5. **Loop Harness Invariant**: The loop harness (`--harness loop`) continues to see files as they exist in the main workspace since it operates directly in the main workspace.
- **Implementation Completed**:
  1. [x] Updated metadata projection and formatting in [`provision_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/lib/provision_impl.py), [`sync_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/lib/sync_impl.py), and [`submit_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/lib/submit_impl.py) to support workspace projection filtering (emitting only `CHANGE`, `FEEDBACK`, and ephemeral `CODE_HASH`).
  2. [x] Updated workspace provisioning and synchronization to compute `CODE_HASH` exclusively on writable files when staging or pulling into the role workspace.
  3. [x] Updated harvesting logic in [`sync_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/lib/sync_impl.py) and submit logic in [`submit_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/lib/submit_impl.py) to compare workspace file contents against the ephemeral baseline hash to detect agent modifications, strip `CODE_HASH` from canonical files in the main workspace, and refresh ephemeral code hashes in the role workspace.
  4. [x] Preserved canonical `LAST_CHANGED` timestamps and metadata in the main workspace during clean submissions without code changes.
  5. [x] Full specification cascade completed across all Cleanroom methodologies: HLS (`high/*.md`) $\to$ Planning (`planning/*.md`) $\to$ Scenarios (`scenarios/*.md`) $\to$ Low stubs (`low/*.pyi`) $\to$ Lib (`lib/*.py`) $\to$ Tests (`tests/*_test.py`).
  6. [x] Validated across the entire repository with `bin/test` (625 passed tests, 9 subtests passed, 0 linter/pyright errors).

---

### [COMPLETED] Task 7: Dirty Reasoning Propagation & LAST_CLEANED Preservation
- **Status**: Completed (2026-10-18)
- **Component**: [`update_with_ai/parts/metadata/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/metadata/), [`update_with_ai/parts/workspace_cli/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace_cli/), [`update_with_ai/support/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/support/)
- **Objective**: Ensure that dirtiness reasons are accurately propagated and surfaced to role workers, eliminate false diagnoses of missing header tags, preserve `LAST_CLEANED` timestamps during dirty operations, and protect subagents from confusing internal metadata projection with file defects.
- **Specification & Behavioral Invariants**:
  1. **Preservation of `LAST_CLEANED` on Dirty**: Marking a node dirty (`uv run cleanroom dirty` / `dag_storage.mark_node_dirty`) sets the `# DIRTY: <reason>` tag (defaulting to `"dirty"` if no reason is given) without clearing or deleting the `# LAST_CLEANED: <timestamp>` header tag. The presence of the `DIRTY:` tag is what makes the node dirty, preserving historical clean provenance.
  2. **Prioritization of Explicit Dirty Reasons & Feedback**: `src_storage_impl.is_dirty` and `dirtiness_impl.evaluate_unit_dirty` evaluate `meta.dirty` and `meta.feedback` before checking `meta.last_cleaned`. Explicit failure explanations and blame diagnostics are always prioritized over fallback reasons.
  3. **Accurate Uncleaned Diagnostics**: Replaced misleading reason `Header missing LAST_CLEANED in {target_rel}` with `Target has not been cleaned ({target_rel})`.
  4. **Subagent Orientation (Rule 4: Metadata Projection & Inviolability)**: Updated `AGENTS.md` and `cleanroom_worker` system prompt instructions (`cleanroom_role_tool.py`) explaining that role workspaces intentionally project out internal lifecycle timestamps (`LAST_CLEANED`, `LAST_CHANGED`, audit stamps), explicitly forbidding workers from treating the absence of lifecycle timestamps as formatting defects.
- **Implementation Completed**:
  1. [x] Updated HLS in [`high/src_storage_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/metadata/high/src_storage_impl.md) contracting that `mark_node_dirty` sets the dirty tag without clearing the last cleaned timestamp.
  2. [x] Updated Planning in [`planning/src_storage_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/metadata/planning/src_storage_impl.md) replacing `mark_node_dirty_clears_last_cleaned` with `mark_node_dirty_preserves_last_cleaned`.
  3. [x] Updated Scenarios in [`scenarios/src_storage_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/metadata/scenarios/src_storage_impl.md) Scenario 17.
  4. [x] Updated Low-level stubs in [`low/src_storage_impl.pyi`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/metadata/low/src_storage_impl.pyi) postconditions and grounding.
  5. [x] Implemented in [`lib/src_storage_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/metadata/lib/src_storage_impl.py) preserving `last_cleaned` and checking `dirty`/`feedback` first in `is_dirty`.
  6. [x] Updated unit tests in [`tests/src_storage_impl_test.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/metadata/tests/src_storage_impl_test.py) asserting `LAST_CLEANED:` is preserved when dirty is marked with or without reason.
  7. [x] Updated `dirtiness_impl.py` and `pending_impl.py` candidate resolution order across main and role workspaces.
  8. [x] Added Rule 4 ("Metadata Projection & Inviolability") across `AGENTS.md`, `cleanroom_role_tool.py`, and refreshed all 18 role workspaces.
  9. [x] Verified full repository with `bin/test` (627 passed tests, 9 subtests passed) and validated live end-to-end convergence via `uv run cleanroom clean staging#qa --harness antigravity`.


