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
   - [Task 1: Cross-Model Empirical Benchmarking Suite](#task-1-cross-model-empirical-benchmarking-suite)
   - [Task 2: Standalone Ephemeral Distribution (`uvx cleanroom`)](#task-2-standalone-ephemeral-distribution-uvx-cleanroom)
   - [Task 3: Contract Slug Integration in Low-Level Specifications & Test Requirement Traceability](#task-3-contract-slug-integration-in-low-level-specifications--test-requirement-traceability)
   - [Task 4: Feedback Embargo Checker Sub-Agent & Anti-Pruning Verification Gate](#task-4-feedback-embargo-checker-sub-agent--anti-pruning-verification-gate)
   - [Task 5: 100% Statement & Branch Coverage Enforcement in Property Fuzzing](#task-5-100-statement--branch-coverage-enforcement-in-property-fuzzing)

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
| **Context Isolation** | None (Single API conversation context) | Complete (Separate interactive chats or human rounds) | Complete (Physical OS workspace per subagent) | Weak (Software prompt instructions; single directory) |
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
- **User or Supervisor Round**: Inspects work queue via `uv run cleanroom work-queue <scope>`.
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
1. **Context Window Token Explosion**: The coordinator and all subagents shared a single monolithic context. Tool definitions, MCP schemas, stdout/stderr streams, and file diffs accumulated rapidly, consuming over 1,500,000 tokens within 3–4 cleaning rounds and triggering rate-limit quotas under Google One Ultra.
2. **Tool-Call Indirection Overhead**: Subagents did not read/write files directly; they routed calls through FastMCP endpoints (`cleanroom_read_file`, `cleanroom_write_file`), introducing high serialization latency and frequent JSON truncation.
3. **Flaky Daemon Process Lifecycles**: The long-running FastMCP background process suffered from socket disconnections, orphan daemon locks, and zombie processes across IDE restarts.
4. **Lack of OS-Level Enforcement**: Software hooks were repeatedly bypassed by models inventing shell commands or using alternate edit tools.

*Decision*: Option 2 was completely decommissioned and replaced by Option 4 (Physical Workspaces + Native Subagents).

---

### Goose Harness Post-Mortem: Why Goose Was Decommissioned

An experimental harness adapter for the Block Goose CLI agent (`--harness goose`) was developed and evaluated.

**Root Causes of Decommissioning**:
1. **Unstable Subprocess IPC**: Goose relied on an interactive terminal session that lacked a structured JSON RPC interface, causing frequent deadlock during long-running test suites.
2. **Lack of Workspace Sandboxing**: Goose lacked native support for switching working directories per-round, requiring aggressive shell symlink swapping that corrupted concurrent runs.
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
   - Invokes structured RPC methods (`workspace/create`, `session/create`, `session/prompt`) to drive subagent rounds directly against the running server.
   - Completely eliminates kernel write-lease contention (`flock` on `session.lock`) when running alongside an active Cordis desktop UI session, preventing UI session forking and deadlocks.
   - Retains automatic fallback to headless CLI invocation (`dsh exec`) when no desktop server instance is discovered.

2. **`dsh_telemetry` Background Daemon**:
   - Runs a non-blocking UNIX domain socket server listening for subagent lifecycle events.
   - Emits structured JSON events: `{"event": "subagent_start", "scope": "...", "role": "...", "workspace": "..."}`.
   - Tracks per-round token usage, execution time, and tool call frequency.

3. **Cordis Desktop Shell Overlay**:
   - Injects real-time status badges into the Cordis desktop shell.
   - Displays active cleaning waves, dirty dependency DAGs, and subagent process health.

---

### Google Antigravity Integration & Rate Economics

In Google Antigravity environments:
- Cleanroom registers the `cleanroom_coordinator` agent definition.
- Emits the `AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE` for zero-friction handoff.
- Supports native desktop app IPC integration via `agentapi` (`$ANTIGRAVITY_AGENTAPI_EXE` or `~/.gemini/antigravity/bin/agentapi`):
  - **Reactive Wakeup (`agentapi send-message`)**: Injects high-priority directives directly into `$ANTIGRAVITY_CONVERSATION_ID`, waking up the active conversation agent even when long-running CLI commands background into tasks.
  - **Headless Tab Spawning (`agentapi new-conversation`)**: Spawns dedicated coordinator tabs in the desktop sidebar directly from Python processes.
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
  - Dual-mode subagent round dispatch implemented in `parts/dsh`: opportunistic JSON-RPC bridge when DSH Desktop / server is active, with headless CLI fallback.
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
- [x] **Phase 6: Multi-Wave End-to-End Orchestration Stress Testing**
  - Synthetic mock project trees with diamond and star dependencies across 5 roles and 13 targets verified through 5 execution waves.
  - Multi-agent wave barriers validated: parallel implementation roles (`lib` + `test`) cluster dynamically into concurrent waves, and downstream auditor roles (`qa`) remain blocked until all parallel dependencies succeed.
  - Upstream blame defect propagation verified: failing rounds generate structured blame feedback that propagates upstream, halts downstream workers, and automatically resumes upon defect resolution.
  - Cancellation & termination handling: `SubagentCoordinator.orchestrate` traps interruption signals (SIGINT/SIGTERM/KeyboardInterrupt), interrupts active worker processes via `harness.interrupt_role`, and deletes all provisioned role workspace sandboxes in scope.
  - Full specification cascade verified across all Cleanroom methodologies (129 HLS, 103 Planning, 129 Low, 0 Pyright errors, 703 passed tests).
- [x] **Phase 7: Native Antigravity Desktop `agentapi` Coordinator Dispatch & Reactive IPC**
  - Solved Antigravity Desktop background-task prompt starvation and stdout suppression for long-running CLI and benchmark commands.
  - Environment detection: detects `ANTIGRAVITY_AGENT == "1"`, retrieves `ANTIGRAVITY_CONVERSATION_ID`, and locates the `agentapi` binary via `$ANTIGRAVITY_AGENTAPI_EXE`, `PATH`, or `~/.gemini/antigravity/bin/agentapi`.
  - Reactive Wakeup (`send-message`): dispatches `agentapi send-message --title "Cleanroom Coordinator Directive" "$ANTIGRAVITY_CONVERSATION_ID" "Clean all dirty nodes in <scope> using cleanroom_coordinator"`, waking the desktop model reactively with explicit scope targets.
  - Headless Tab Dispatch (`new-conversation`): supports `--antigravity-dispatch=new-conversation` (or `--antigravity-mode=new-conversation`) spawning dedicated sidebar coordinator tabs to decouple long-running flight polling from active chat canvases.
  - Resilient Fallback: persists active run metadata to `.cleanroom/active_flight.json` and falls back gracefully to standard synchronous stdout directives if `agentapi` or conversation IDs are absent.
  - Cascaded across full specification pipeline (`update_with_ai/parts/benchmark/` HLS $\to$ Planning $\to$ Scenarios $\to$ Low $\to$ Lib $\to$ Tests) and validated with unit test suite in `cleanroom_role_tool_test.py`.
- [x] **Phase 8: Pretense Stateful Fuzzing, Baseline Equalizer & Watchdog Hardening**
  - Implemented the Pretense state-machine and fake synthesis engine (`pretense/`) across Cleanroom roles (`pretense`, `pretense_qa`, `pretense_coverage`) and single-agent baselines (`--baseline --pretense`).
  - Executed empirical cross-model benchmark campaigns on `dag_engine_lite` comparing Cleanroom against Pretense Baselines across DeepSeek-Flash (DSH), Gemini 3.8 Flash (Antigravity), and Qwen-MoE (Local omlx).
  - Hardened Pretense runner (`pretense/cli.py`) with per-target watchdog timeout (`--timeout`, `PRETENSE_TIMEOUT=45.0s`), GIL-independent native thread dump (`faulthandler.dump_traceback_later`), and non-zero exit on infinite loop/deadlock hangs.
  - Resolved `reportOptionalCall` typing defect in `pretense/transition.py` to achieve 0 Pyright errors out-of-the-box.
  - **Empirical Breakthrough**: Pretense serves as an architectural equalizer, allowing single-agent baselines to achieve 100% test pass rates and 98% coverage at 37%–74% lower token cost and 2x–4x faster wall-clock execution than multi-role Cleanroom pipelines.
- [x] **Phase 9: Minimal Hermetic Role Workspace Provisioning & Clutter Eradication** (Homed in [`design.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/design.md#L443))
  - Bundled `cleanroom_roles.toml` inside zipapps, eliminated workspace root clutter, purged ghost manifest references, and implemented selective single-guide provisioning.
- [x] **Phase 10: Broad Exception Linter & Semantic Reification** (Homed in [`toolchain_and_verification.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/toolchain_and_verification.md#L164))
  - Implemented semantic AST exception reification analysis in `check_exception_eating` with explicit pragma directives (`# cleanroom: allow-broad-exception`) for task execution engines.
- [x] **Phase 11: Class-Based Pretense State Machine Redesign & Repository-Wide Migration** (Homed in [`pretense.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/pretense.md#L2042))
  - Redesigned Pretense state machines from verbose 4-function `StateMachineProto` definitions into an ergonomic class-based DSL (`class TargetStateMachine(StateMachine[StateT]): ...`) with single decorated methods (`@transition(Target.method)` or `@transition.seeding()`).
  - Implemented generic `TransitionContext[Target, P, R]` with `ctx.antecedent()`, `ctx.arguments(generate=..., recognize=...)`, `ctx.returns(...)`, `ctx.consequent(...)`, and `ctx.raises(...)`, keeping the reference model pure by decoupling concrete target instances from transition lambdas.
  - Supported dual-role execution: underneath target singleton dispatch via `singletons={Target: instance}` during test runs, and dynamic in-memory fake synthesis via `sm.as_fake(Target)`.
  - Migrated 100% of all Pretense test suites repo-wide: 54 canonical suites across `update_with_ai/parts/` and `update_python_with_ai/parts/`, and 18 historical benchmark suites in `benchmarks/results/` (`dag_engine_lite` and `semver_solver`).
  - Updated Pretense scaffolding tooling and templates (`update_python_with_ai/templates/pretense_template.py`, `update_python_with_ai/support/lib/pretense_lint.py`, verified with `update_python_with_ai/support/tests/pretense_lint_test.py`).

### Current Verification Health

Cleanroom maintains 100% test pass rates across all validation suites:
- **`bin/test` & Unit Suites**: **778 passed unit tests, 9 subtests passed**
- **Pretense State Machine Suites**: **148 passed test suites (100% passing)**
- **Pyright Type Checking**: **0 errors, 0 warnings, 0 informations repo-wide**
- **Specification Linter**: **129 High-Level, 103 Planning, 129 Low-Level specifications validated**

---

## 9. Master Actionable Roadmap & Next TODOs

The following prioritized roadmap outlines the active forward engineering tasks for Cleanroom:

---

### Task 1: Cross-Model Empirical Benchmarking Suite
- **Priority**: Medium
- **Component**: `update_with_ai/parts/benchmark/` & `bin/evaluate_model_efficiency.py`
- **Design Specification**: [`benchmark_design_doc.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/benchmark_design_doc.md) (complements [`paper_submission_design_doc.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md))
- **Objective**: Provide automated benchmarking measuring token cost, step latency, KV prompt-cache efficiency, and specification adherence across a 4-tier model spectrum, using `omlx` for local models, restricting expensive Tier 3 & 4 models to two premier anchor targets, and executing a lean, time-calibrated unit scale across a 3-tier code size hierarchy (~500 LOC workhorses, ~1,000 LOC Tier 1 local ceiling, 2,000+ LOC frontier stress ceiling).
- **Implementation Steps**:
  1. [x] Complete authoritative benchmarking design doc: [`benchmark_design_doc.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/benchmark_design_doc.md).
  2. [x] Implement automated runner `bin/evaluate_model_efficiency.py` backed by the contracted component `update_with_ai/parts/benchmark/`:
     - **Tier 1 (Free Local)**: Qwen 3.6 35B MoE & Qwen 27B Dense running strictly via **`omlx`** on Apple Silicon (demonstrating ~1,000 LOC capacity ceiling).
     - **Tier 2 (Budget Cloud)**: DeepSeek V4.1 Flash (DSH JSON-RPC) & Gemini 3.8 Flash (Antigravity).
     - **Tier 3 & Tier 4 (Selective Anchors)**: Evaluated strictly against **Anchor Target 1 (Heavyweight Systems Engine - 2,000+ LOC)** and **Anchor Target 2 (CPython `graphlib`/`heapq`)** using OpenAI o3-mini, Claude Sonnet 3.5/3.7, Gemini 4 Argon, Claude Opus 5.5, OpenAI gpt-6.1-sol, and Meta Muse Wonder Full.
     - **Unified Telemetry Stream**: Harvests non-cached inbound, cached inbound, outbound (with reasoning tokens), financial cost ($USD), step latencies, and wall-clock time; enforces two-pass verification gates (Spec Lint + Pyright + Pytest + Coverage + Mutmut) and emits Section 7 JSON traces to `logs/benchmarks/`.
  3. [ ] Execute empirical flight campaigns with **lean unit counts per RQ**:
     - **RQ1**: 8 curated units (4 CPython `heapq`/`graphlib`, 4 SemVer 2.0 solver) with 8 Attractor State Ambiguity tests.
     - **RQ2**: 10 boundary cases (5 CPython, 5 Generalized DAG engine) with 2 algorithmic guides ($\mathcal{G}$).
     - **RQ3**: Heavyweight Systems Subsystem (2,000+ LOC: 1 monolith vs. 4–5 decoupled units across 12 boundary edge cases).
     - **RQ4**: 6 controlled spec ungroundings (2 deletions, 2 erasures, 2 contradictions) with DAG batching $B \in \{1, 2, 4\}$ on Generalized DAG & Workspace Sandbox units.
     - **RQ5**: 10 autonomous evolution tasks on SemVer 2.0 solver and DAG engine (4 feature additions, 3 contract alterations, 3 refactorings).
     - **RQ6**: 6 injected concurrency defects and 15 mutants in Workspace Sandboxing Subsystem & Lock Manager.
     - **RQ7**: 25k record log stream & event pipeline parser evaluating the Hidden Benchmark Firewall ($GDI \approx 1.04$) across 3 conditions (3 trials each).
  4. Output comparative Markdown reports and publication-ready LaTeX tables (`reports/latex/rq*.tex`).

---

### Task 2: Standalone Ephemeral Distribution (`uvx cleanroom`)
- **Priority**: Low
- **Component**: `pyproject.toml`, distribution scripts
- **Objective**: Enable developers to run Cleanroom on any target project without cloning the Cleanroom codebase (`uvx cleanroom orchestrate .`).
- **Implementation Steps**:
  1. Audit package data inclusion in `pyproject.toml` to ensure methodology templates and default configs are bundled into wheels.
  2. Test `uvx --from . cleanroom --help` in an isolated directory.
  3. Provide pre-built binary distributions via GitHub Releases.

---

### Task 3: Contract Slug Integration in Low-Level Specifications & Test Requirement Traceability
- **Priority**: High
- **Component**: `update_python_with_ai/` (`support/tools/`), `update_with_ai/guides/low_to_test.md`
- **Design Specification**: [`pretense.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/pretense.md) Section 6 & Section 2
- **Objective**: Eliminate errors of omission and test suite blind spots without requiring expensive frontier models by formalizing requirement slugs in Low-Level Specifications (`low/*.pyi`) and asserting that every postcondition clause has matching comment/docstring slug tags in tests (`# [slug:<id>]`) verified via zero-token AST/regex linters, avoiding runtime decorators or metadata overhead.
- **Problem Statement**:
  - In `dag_engine_lite`, the Qwen Cleanroom run greenlit three genuine soundness defects (off-by-one retry counter, node re-registration edge retention, and scheduler state removal desynchronization) while achieving 100% test pass rates, 95% statement coverage, and 90% branch coverage.
  - The defects occurred because the test author never conceived of the edge-case postconditions declared in `low/*.pyi` docstrings.
  - AST code coverage and mutation testing (`mutmut`) only evaluate existing code and are fundamentally blind to errors of omission.
- **Implementation Steps**:
  1. **Low-Level Specification Slug Schema**:
     - Formalize `[slug:<interface>.<method>.<clause>]` syntax in `low/*.pyi` docstring postconditions (e.g. `[slug:dag.add_node.replace_existing]`).
     - Align with existing factored contract slugs in `planning/*.md` (`planning_format.md`).
  2. **Test Comment Tagging Convention**:
     - Test methods document covered requirements using standard comments or docstring tags (e.g. `# [slug:<slug_id>]` or `"""[slug:<slug_id>]"""`), keeping tests clean and free of runtime decorator dependencies.
  3. **Deterministic Traceability Linter**:
     - Implement a zero-token Python linter in `update_python_with_ai/` that parses all `[slug:...]` declarations from `low/*.pyi` and scans `tests/*_test.py` comments/docstrings for matching slug references.
     - Integrate into `bin/check_files`: fail Pass 1 if any slug declared in `low/*.pyi` lacks a corresponding test comment reference.
  4. **Guide & Prompt Alignment**:
     - Update `update_python_with_ai/guides/low_to_test.md` to instruct the Certifier ($W_{\text{test}}$) to systematically enumerate and tag test methods with the exact slug comments matching specification clauses.
  5. **Corpus Migration**:
     - Retrofit contract slugs into benchmark suites (`benchmarks/parts/dag_engine_lite/low/`), establishing the baseline for the upcoming `semver_solver` benchmark.

---

### Task 4: Feedback Embargo Checker Sub-Agent & Anti-Pruning Verification Gate
- **Priority**: High
- **Component**: `update_with_ai/parts/workspace_cli/` & `update_with_ai/parts/agent/`
- **Design Specification**: [`benchmark_design_doc.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/benchmark_design_doc.md)
- **Objective**: Prevent auditor overreach, code micromanagement, and destructive pruning during Cleanroom convergence by intercepting `bin/blame` and verifying that all auditor feedback strictly conforms to the information embargo and common specification grounding.
- **Problem Statement**:
  - In `semver_solver` benchmark runs, the `pretense_coverage` auditor repeatedly cited private internal helper lines in the library implementation (`_check_bare_partial`, lines 211 and 321) and demanded that valid defensive edge-case handling (empty clauses in `||` and wildcards `*`, `x`) be pruned as "dead code" because existing tests did not exercise them.
  - This bullied the library worker into deleting valid specification-compliant edge handling, causing cross-soundness failures against foreign test suites.
- **Implementation Steps**:
  1. **Information Embargo Filter**: Verify that blame messages do not cite or leak implementation details, private symbols (`_*`), or line numbers of companion files (line numbers permitted only for the file being blamed).
  2. **Specification Grounding Gate**: Require blame critiques to explicitly cite a contract, clause, or assumption from the common specification (`low/*.pyi`).
  3. **Anti-Pruning Gate**: Reject claims that input validation is "unreachable" when the input space is permitted by the specification; redirect critiques to the test author (`pretense`) to add test coverage instead of forcing the library author to delete functional code.
  4. **Sub-Agent / Verification Hook**: Implement either as a deterministic pre-check in `bin/blame` or a dedicated lightweight `feedback_checker` subagent.

---

### Task 5: 100% Statement & Branch Coverage Enforcement in Property Fuzzing
- **Priority**: High
- **Component**: `update_python_with_ai/` (`pretense/`, `support/tools/`), `update_python_with_ai/guides/pretense_coverage.md`
- **Design Specification**: [`pretense.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/pretense.md) Section 5 & Section 11
- **Objective**: Ensure that Hypothesis stateful property fuzzing suites (`Test<Target>Fuzz` / `compile_hypothesis_test_case`) achieve 100% statement and branch coverage across the library implementation under test, independently from or combined with fixed/deterministic unit tests (`Test<Target>Unit` / `Test<Target>ImplReal`).
- **Problem Statement**:
  - Historically, coverage certification was evaluated primarily under `--no-fuzz --cov`, measuring only deterministic scenario replay in `Test<Target>ImplReal`.
  - The stateful fuzzing suite was treated as an unmeasured "best-effort" execution pass. Consequently, test authors could achieve 100% coverage using static, hand-written unit tests while leaving state-machine transition argument generators crippled with single-sample constants (`generate=lambda: ("1.0.0",)`).
  - When state machines only execute static constants during fuzzing, random walks do not explore the data domain, and defensive branches in `lib/` are left unexercised by property tests.
- **Implementation Steps**:
  1. **Dual-Mode Coverage Instrumentation**:
     - Update `PretenseRunnerConfig` and `PretenseEngine` to measure statement and branch coverage during the fuzzing pass (`pretense run --fuzz --cov`).
     - Support isolated fuzz coverage reporting alongside deterministic scenario coverage reporting.
  2. **100% Fuzz Coverage Certification Gate**:
     - Update the `pretense_coverage` role verifier (`bin/check_files`) to enforce that the SUT achieves 100% statement and branch coverage under the fuzzing pass.
     - When unreached branches remain during property fuzzing, `pretense_coverage` blames the test author (`pretense`) to broaden transition argument strategies (`ctx.arguments(generate=...)`) with generative combinators (`st.integers`, `st.sampled_from`, `st.builds`) rather than blaming `lib` to prune defensive code.
  3. **Guide Alignment**:
     - Update `update_python_with_ai/guides/pretense.md` and `update_python_with_ai/guides/pretense_coverage.md` with explicit criteria requiring 100% branch coverage from state-machine fuzz transitions.





