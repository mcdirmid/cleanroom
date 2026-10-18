# Cleanroom System Architecture & Technical Design

> **Authoritative Technical Design Document**  
> This document provides the comprehensive technical design and architectural specifications for the Cleanroom system. It condenses and synthesizes the engineering designs for execution paradigms, double-blind physical workspaces, in-band metadata, logless auditor roles, specification grounding, packaging, and multi-harness telemetry.
>
> *(Note: Operational tracking, completed milestones, and forward development tasks are maintained in [`todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md). Academic research formulations and the formal specification calculus are in [`paper_submission_design_doc.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md) and [`grounded_specification_language_and_neural_compilation.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/grounded_specification_language_and_neural_compilation.md)).*

---

## Table of Contents

1. [System Overview & Architectural Philosophy](#1-system-overview--architectural-philosophy)
   - [Core Invariants](#core-invariants)
   - [The 5-Stage Transformation Pipeline](#the-5-stage-transformation-pipeline)
   - [Modular Package Decomposition (`update_with_ai/parts/*`)](#modular-package-decomposition-update_with_aiparts)
2. [Execution Paradigms & Isolation Architecture](#2-execution-paradigms--isolation-architecture)
   - [Paradigm Comparison Matrix](#paradigm-comparison-matrix)
   - [Option 4: Subagent-Driven Workspaces with Zero-Execution Coordinator (Primary)](#option-4-subagent-driven-workspaces-with-zero-execution-coordinator-primary)
   - [Option 3: Subagentless Interactive Workspaces](#option-3-subagentless-interactive-workspaces)
   - [Option 1: Custom In-Process Headless Loop](#option-1-custom-in-process-headless-loop)
3. [Historical Post-Mortems & Decommissioned Systems](#3-historical-post-mortems--decommissioned-systems)
   - [Option 2 Post-Mortem: Why In-Tree FastMCP Subagents Failed](#option-2-post-mortem-why-in-tree-fastmcp-subagents-failed)
   - [Goose Harness Post-Mortem: Why Goose Was Decommissioned](#goose-harness-post-mortem-why-goose-was-decommissioned)
4. [Logless State & In-Band Source Metadata Specification](#4-logless-state--in-band-source-metadata-specification)
   - [The Logless State Invariant](#the-logless-state-invariant)
   - [Header Syntax & Field Schema](#header-syntax--field-schema)
   - [Sanitization & Hashing Algorithm](#sanitization--hashing-algorithm)
   - [Star-Dependency Cascades & Forward Dirtiness Evaluation](#star-dependency-cascades--forward-dirtiness-evaluation)
5. [Auditor Roles, Attestation & Feedback Architecture](#5-auditor-roles-attestation--feedback-architecture)
   - [Auditor Roles as First-Class Certifiers](#auditor-roles-as-first-class-certifiers)
   - [Resolving the "0-Byte Paradox" via In-Band Attestation](#resolving-the-0-byte-paradox-via-in-band-attestation)
   - [Auditor Dirtiness Evaluation](#auditor-dirtiness-evaluation)
   - [Feedback Injection & Context Budget Protection](#feedback-injection--context-budget-protection)
6. [Specification Grounding & Physical Workspace Assembly](#6-specification-grounding--physical-workspace-assembly)
   - [The Formal Grounding Invariant](#the-formal-grounding-invariant)
   - [Physical Workspace Provisioning & Permission Masking](#physical-workspace-provisioning--permission-masking)
   - [Retirement of Legacy Build Artifacts](#retirement-of-legacy-build-artifacts)
7. [Packaging, Distribution & CLI Execution Architecture](#7-packaging-distribution--cli-execution-architecture)
   - [Native Python Packaging (`pyproject.toml` + `uv`)](#native-python-packaging-pyprojecttoml--uv)
   - [Dynamic Workspace Root Derivation](#dynamic-workspace-root-derivation)
   - [Ephemeral Zero-Install Distribution (`uvx`)](#ephemeral-zero-install-distribution-uvx)
   - [Unified CLI Command Architecture](#unified-cli-command-architecture)
8. [Multi-Harness Telemetry & Desktop Integration](#8-multi-harness-telemetry--desktop-integration)
   - [DeepSeek Harness (`dsh`), Telemetry & Cordis Shell](#deepseek-harness-dsh-telemetry--cordis-shell)
   - [Google Antigravity Integration & Rate Economics](#google-antigravity-integration--rate-economics)

---

## 1. System Overview & Architectural Philosophy

Cleanroom is a literate, specification-driven neural compilation and software engineering framework. It guarantees that software produced by autonomous AI agents is mathematically verifiable, grounded in formal contracts, and free from hallucinations, context poisoning, and accidental implementation drift.

### Core Invariants

1. **Mandatory Specification-First (HLS-First)**:  
   No code or test is authored directly. Every capability, data type, state machine transition, and invariant originates in literate High-Level Specifications (`high/*.md`) and cascades deterministically downstream:
   $$\text{HLS} \longrightarrow \text{Planning} \longrightarrow \text{Scenarios} \land \text{Low} \longrightarrow \text{Spec QA} \longrightarrow \text{Lib} \land \text{Tests} \longrightarrow \text{QA} \land \text{Coverage}$$
   Every defect discovered in implementation or testing is treated as a defect in specification. Stealth edits to `lib/*.py` or `tests/*_test.py` are strictly blocked.

2. **Physical Double-Blind Isolation via Operating System Filesystem Controls**:  
   Prompt agreements and software interceptors fail under autonomous agent execution. Cleanroom enforces double-blind isolation physically using OS-level filesystem permissions (`chmod 444`) and isolated sibling directories. Implementation authors are physically denied access to test code, and test authors are physically denied access to implementation code.

3. **Logless State via In-Band Source Metadata**:  
   External state databases, SQLite registries, and sidecar textproto files create synchronization drift and concurrency corruption. Cleanroom embeds all state (Git commit hashes, content hashes, auditor attestations, and failure feedback) directly into managed source files as in-band comment headers.

4. **Zero-Execution Multi-Agent Coordination**:  
   The top-level coordinator agent never executes code, never views source files, and never runs tests. Its sole purpose is calculating the directed acyclic graph (DAG) of dirty nodes, grouping unblocked nodes into parallel execution waves, provisioning physical sibling workspaces, and dispatching workspace-bound worker subagents.

---

### The 5-Stage Transformation Pipeline

```
       ┌────────────────────────────────────────────────────────┐
       │             High-Level Specification (HLS)             │
       │                   (high/*.md)                          │
       │  Literate architectural prose, italic semantic markers │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │                 Planning Specification                 │
       │                 (planning/*.md)                        │
       │  Factored contracts, citation slugs, epistemic reach   │
       └───────────────────────────┬────────────────────────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
       ┌─────────────────────┐           ┌──────────────────────┐
       │ Concrete Scenarios  │           │ Low-Level Spec (AST) │
       │  (scenarios/*.md)   │           │    (low/*.pyi)       │
       │ Step-by-step traces │           │ Typed Python stubs,  │
       │ of caller journeys  │           │ DbC, GROUNDING doc   │
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
       │ Verbatim contract   │           │ Production runtime,  │
       │ assertions          │           │ no test access       │
       └──────────┬──────────┘           └──────────┬───────────┘
                  │                                 │
                  │        ┌──────────────┐         │
                  └───────►│  QA Arbiter  │◄────────┘
                           │  & Coverage  │
                           └──────────────┘
```

---

### Modular Package Decomposition (`update_with_ai/parts/*`)

Cleanroom is decomposed into single-responsibility, decoupled Python packages under `update_with_ai/parts/`:

| Package Path | Core Responsibility | Key Components |
| :--- | :--- | :--- |
| **`parts/tools`** | Deterministic language-agnostic verification engines | `tool_runner.py`, `tool_coverage.py`, `tool_linter.py` |
| **`parts/storage`** | In-band metadata persistence, hashing & DAG dirtiness | `src_metadata.py`, `manifest_ext.py`, `hash_util.py` |
| **`parts/workspace`** | Physical sibling sandboxes & OS `chmod 444` permission masking | `workspace_factory.py`, `workspace_clean.py` |
| **`parts/subagent`** | Multi-agent wave scheduler & worker life-cycle manager | `subagent_coordinator.py`, `subagent_worker.py` |
| **`parts/control`** | CLI suite, target resolution, and methodology discovery | `cleanroom_cli.py`, `target_resolver.py` |
| **`parts/loop`** | In-process autonomous agent execution loop (Option 1) | `loop_driver.py`, `loop_cleaner.py`, `loop_guard.py` |
| **`parts/dsh`** | DeepSeek Harness (`dsh`) integration, telemetry daemon | `dsh_telemetry.py`, `dsh_harness_impl.py`, Cordis overlay |
| **`parts/antigravity`** | Google Antigravity coordinator & subagent directives | `antigravity_harness_impl.py`, agent configurations |
| **`parts/openai`** | Direct OpenAI/Gemini REST API client for headless loops | `openai_client.py` |
| **`parts/systems`** | Platform detection, POSIX permissions, subprocess runners | `sys_util.py`, `shell_runner.py` |
| **`parts/uv`** | Isolated virtual environment management via `uv` | `uv_runner.py` |

---

## 2. Execution Paradigms & Isolation Architecture

Cleanroom defines three active operational paradigms, each tailored to distinct execution environments:

### Paradigm Comparison Matrix

| Architectural Feature | Option 1: Custom Loop (`--harness loop`) | Option 3: Subagentless Workspaces | Option 4: Subagent-Driven Workspaces (Primary) | Option 2: In-Tree FastMCP Subagents (*Archived*) |
| :--- | :--- | :--- | :--- | :--- |
| **Execution Mode** | Headless in-process Python loop | Interactive developer CLI / IDE turn | Autonomous multi-agent wave coordinator | Multi-subagent hierarchy in single working dir |
| **Supervisor Role** | Algorithmic Python loop driver | Human developer or IDE agent | Zero-execution coordinator subagent | Subagent coordinator with file edit permissions |
| **Isolation Mechanism** | Ephemeral in-process state | Sibling directories with `chmod 444` mounts | Sibling directories with `chmod 444` mounts | Software lifecycle hooks (`cleanroom_sandbox_hook.py`) |
| **Double-Blind Safety** | Procedural tool-masking | Physical OS filesystem enforcement | Physical OS filesystem enforcement | Software prompt rules (Repeatedly bypassed) |
| **Target Harness** | Any OpenAI/Gemini-compatible endpoint | Google Antigravity, Cursor, VS Code, CLI | Google Antigravity, DeepSeek Harness (`dsh`) | Antigravity FastMCP tool server |
| **Token Consumption** | Low (Minimal prompt overhead) | Very Low (Zero supervisor overhead) | Low (Scoped worker contexts, parallel waves) | Catastrophic (1.5M+ tokens/run; rate-limit burst) |
| **Production Status** | **Active & Production** | **Active & Production** | **Active & Production (Primary)** | **Failed & Permanently Archived** |

---

### Option 4: Subagent-Driven Workspaces with Zero-Execution Coordinator (Primary)

Option 4 combines the physical isolation of Option 3's sibling workspaces with autonomous multi-agent wave scheduling.

```
                      ┌────────────────────────────────────────┐
                      │      Cleanroom Coordinator Agent       │
                      │       (Zero-Execution Supervisor)      │
                      └───────────────────┬────────────────────┘
                                          │
                        Calculates Wave 1 │ (Independent Ready Nodes)
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
                             │ Both Nodes Cleaned    │
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

#### The Zero-Execution Coordinator Invariant
The coordinator subagent (`cleanroom_coordinator`) is granted strictly restricted tool permissions:
- **Stripped Tools**: Denied all file editing tools (`write_to_file`, `replace_file_content`), viewing tools (`view_file`), web searching, and terminal execution except for query commands.
- **Allowed Tools**: `run_command` (restricted to `uv run cleanroom work-queue`), `send_message`, `invoke_subagent`, and `manage_subagents`.
- **Zero File Custody**: The coordinator never reads source code, runs tests, or touches project files.

#### Wave-Based DAG Scheduling Algorithm
1. Coordinator executes `uv run cleanroom work-queue <scope>`.
2. Inspects returned topologically sorted list of dirty nodes.
3. Groups all ready nodes (nodes whose upstream dependencies are 100% clean) into **Wave $N$**.
4. Dispatches subagents in parallel, each pinned to its dedicated workspace:
   `Workspace: "inherit"` is prohibited; each worker is pinned to `../role_workspaces/<session_id>/<scope>_<role>/`.
5. Awaits wave completion. When all nodes in Wave $N$ report clean, re-evaluates `work-queue` for Wave $N+1$.
6. Terminates when `work-queue` returns empty (all nodes clean).

---

### Option 3: Subagentless Interactive Workspaces

Designed for human-directed or single-agent interactive development:
- **Workspace Directory Structure**:
  ```
  projects/
  ├── cleanroom/                              # Main workspace (Supervisor context)
  └── role_workspaces/                        # Sibling workspaces directory
      └── session_12345/
          ├── parts_storage_high/             # High role workspace
          ├── parts_storage_planning/         # Planning role workspace
          ├── parts_storage_low/              # Low role workspace
          ├── parts_storage_lib/              # Lib role workspace (tests/ hidden)
          └── parts_storage_test/             # Test role workspace (lib/ hidden)
  ```
- **The 4-Tier Sandboxing Model**:
  1. **Tier 1 (Directory Isolation)**: Sibling directories outside main workspace prevent accidental file modification.
  2. **Tier 2 (Upstream Read-Only Masking)**: Upstream specifications are mounted with POSIX `chmod 444` write protection.
  3. **Tier 3 (Double-Blind Role Masking)**: Opposing roles are omitted completely. For example, `parts_storage_lib` contains no test files; `parts_storage_test` contains interface stubs raising `NotImplementedError`.
  4. **Tier 4 (Zero-Execution Supervisor)**: Interactive chat inspects queues and triggers CLI mutations without executing implementation logic directly.

---

### Option 1: Custom In-Process Headless Loop

An autonomous in-process agent loop designed for unattended CI/CD environments (`uv run cleanroom clean --harness loop`):
- **`loop_cleaner.py`**: Traverses the DAG in topological order, identifying the next dirty node.
- **`loop_driver.py`**: Runs a closed ReAct cycle:
  $$\text{Prompt(Guide, Target, Header)} \longrightarrow \text{LLM Call} \longrightarrow \text{Tool Execution} \longrightarrow \text{Observation} \longrightarrow \text{Verification}$$
- **`loop_guard.py`**: Enforces strict safety fences:
  - Repetition guard: Detects identical sequential tool invocations and breaks execution loops.
  - Turn limit: Enforces maximum turns per node (default: 15) to prevent run-away token drain.
  - Test gate: Invokes `tool_runner.py` after each turn; breaks out immediately upon passing all tests.

---

## 3. Historical Post-Mortems & Decommissioned Systems

### Option 2 Post-Mortem: Why In-Tree FastMCP Subagents Failed

In Option 2, Cleanroom attempted to enforce role isolation in a single shared directory using an external FastMCP server daemon and Antigravity `PreToolUse` hooks (`cleanroom_sandbox_hook.py`).

**Root Causes of Failure**:
1. **Context Window Token Explosion**: The coordinator and all subagents shared a monolithic context. Tool definitions, JSON schemas, stdout/stderr streams, and diffs accumulated rapidly. A single 4-node cleaning pass consumed 1,500,000+ tokens in 40 minutes, burning through 5-hour Google One Ultra burst quotas ($30–$50 per run).
2. **Tool-Call Indirection Overhead**: Workers did not access the filesystem directly; they invoked Python CLI wrappers that called a local HTTP daemon. Serialization latency and JSON truncation caused frequent network timeouts.
3. **Daemon Process Brittleness**: The FastMCP server process frequently orphaned locks (`.mcp.active`), failed to shut down on IDE restarts, and deadlocked on concurrent IPC sockets.
4. **Failure of Software-Only Sandboxing**: LLMs repeatedly hallucinated shell commands or bypassed software hooks using alternative shell utilities.

*Verdict*: Option 2 was completely decommissioned. Physical filesystem isolation (Option 3 and Option 4) solved all four issues permanently.

---

### Goose Harness Post-Mortem: Why Goose Was Decommissioned

An experimental harness adapter for Block's Goose CLI agent (`--harness goose`) was developed and tested.

**Root Causes of Decommissioning**:
1. **Lack of Structured IPC**: Goose operated via an interactive TTY shell without a stable JSON RPC interface, causing frequent terminal parsing deadlocks during long test executions.
2. **Incompatible Working Directory Model**: Goose did not support dynamic workspace context switching per turn, requiring fragile symlink-swapping hacks at the shell root.
3. **Platform Redundancy**: DeepSeek Harness (`dsh`) provided identical local CLI capabilities with superior structured telemetry, native socket event streaming, and rock-solid process stability.

*Verdict*: Goose was turndowned, and all related code was deleted.

---

## 4. Logless State & In-Band Source Metadata Specification

### The Logless State Invariant

Cleanroom maintains **zero external state registries** (no `.update_with_ai.textproto`, no SQLite databases, and no out-of-band audit logs). The repository file system and Git object tree are the sole sources of truth. All lifecycle state is embedded directly inside managed source files.

---

### Header Syntax & Field Schema

#### Markdown Artifacts (`high/*.md`, `planning/*.md`, `scenarios/*.md`)
```markdown
<!-- CLEANROOM METADATA
LAST_CLEANED: 047a949f2b8e3a1d9c7e5f4a8b2c1d0e9f8a7b6c
LAST_CHANGED: 047a949f2b8e3a1d9c7e5f4a8b2c1d0e9f8a7b6c
CODE_HASH: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
FEEDBACK: [from qa at 2026-10-16T12:00:00Z]
Verification failed: PathNormalizer rejects valid Windows UNC paths.
-->
```

#### Python / Python Interface Artifacts (`low/*.pyi`, `lib/*.py`, `tests/*_test.py`)
```python
# CLEANROOM METADATA
# LAST_CLEANED: 047a949f2b8e3a1d9c7e5f4a8b2c1d0e9f8a7b6c
# LAST_CHANGED: 047a949f2b8e3a1d9c7e5f4a8b2c1d0e9f8a7b6c
# CODE_HASH: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
# SPEC_QA_AUDIT: 2026-10-16T12:00:00Z PASSED git:047a949f
# QA_AUDIT: 2026-10-16T12:05:00Z PASSED git:047a949f
```

- **`LAST_CLEANED`**: The UTC timestamp (or Git commit hash) at the moment this node passed all verification gates and was stamped clean.
- **`LAST_CHANGED`**: The UTC timestamp (or Git commit hash) of the latest substantive edit to this file or any of its upstream dependency contracts.
- **`CODE_HASH`**: SHA-256 hex digest of the sanitized file body. In the main workspace, code hashes are omitted or stripped; in role workspaces, ephemeral code hashes are computed dynamically on writable files during synchronization to detect agent modifications.
- **`DIRTY:`**: Explicit in-band dirty tag (`# DIRTY: <reason>`) recording why a target requires cleaning. Marking a node dirty sets this tag without deleting `LAST_CLEANED`, preserving clean provenance while unambiguously signaling dirtiness. Marking clean clears the `DIRTY:` tag.
- **`FEEDBACK:`**: Ephemeral diagnosis block injected upon failure or blame.
- **`<ROLE>_AUDIT:`**: In-band attestation stamps applied by auditor roles.

#### Role Workspace Metadata Projection
To protect model context budgets and prevent subagents from misinterpreting internal lifecycle state, role workspaces receive filtered metadata headers:
- Only `CHANGE`, `FEEDBACK`, and ephemeral `CODE_HASH` are projected into role workspaces.
- Canonical lifecycle stamps (`LAST_CLEANED`, `LAST_CHANGED`, audit stamps) remain exclusively in the main workspace.
- The in-process loop harness (`--harness loop`) operates directly against main workspace metadata.

---

### Sanitization & Hashing Algorithm

To ensure hashing is deterministic and immune to metadata changes:
1. Parse the file lines sequentially.
2. Strip out all lines belonging to the metadata block (`<!-- CLEANROOM METADATA ... -->` or `# CLEANROOM METADATA ...`).
3. Strip trailing whitespace from remaining lines and normalize line endings to `\n`.
4. Compute `sha256(sanitized_utf8_bytes).hexdigest()`.

When a file is submitted, Cleanroom checks if `current_code_hash == recorded_code_hash`. If equal, no substantive content changed, preventing redundant cascading invalidations.

---

### Star-Dependency Cascades & Forward Dirtiness Evaluation

Cleanroom models dependencies as a directed acyclic graph (DAG). Dirtiness is evaluated dynamically:

$$\text{is\_dirty}(N) \iff \begin{cases}
\text{True} & \text{if } N.\text{LAST\_CLEANED is missing} \\
\text{True} & \text{if } \text{sha256}(N.\text{body}) \neq N.\text{CODE\_HASH} \\
\text{True} & \text{if } \exists U \in \text{Upstream}(N) : U.\text{LAST\_CHANGED} \neq N.\text{LAST\_CLEANED} \\
\text{False} & \text{otherwise}
\end{cases}$$

When an upstream specification ($U$) changes, `cleanroom submit` sets $U.\text{LAST\_CHANGED} = \text{HEAD}$.
Every downstream dependent $N$ immediately evaluates to dirty because $U.\text{LAST\_CHANGED} \neq N.\text{LAST\_CLEANED}$, triggering an automatic downstream cleaning cascade.

---

## 5. Auditor Roles, Attestation & Feedback Architecture

### Auditor Roles as First-Class Certifiers

Auditors are read-only certifiers that verify consistency between artifacts:
- **`spec_qa`**: Verifies that `low/*.pyi` and `scenarios/*.md` completely ground all contracts in `planning/*.md`.
- **`qa`**: Verifies that `tests/*_test.py` strictly adheres to `low/*.pyi` and exercises 100% of contracts against `lib/*.py`.
- **`coverage`**: Verifies 100% statement and semantic branch coverage.

---

### Resolving the "0-Byte Paradox" via In-Band Attestation

In traditional build systems, tools require output files. Since an auditor does not author new code, running an audit produced 0 bytes of output, making it impossible to record that the audit passed without an external database.

Cleanroom resolves the **0-byte paradox** by stamping verification attestations directly into the target file's in-band header:
```python
# SPEC_QA_AUDIT: 2026-10-16T12:00:00Z PASSED git:047a949f2b8e
```
The audit stamp embeds the ISO timestamp, the verdict (`PASSED`), and the Git tree hash at the time of verification.

---

### Auditor Dirtiness Evaluation

An auditor role is evaluated as dirty if:
1. The target file lacks a `<ROLE>_AUDIT:` stamp matching the current Git commit hash.
2. Any input artifact verified by the auditor has a `LAST_CHANGED` hash newer than the audit stamp.
3. For `qa` and `coverage`, if either `lib/*.py` or `tests/*_test.py` has changed since the last audit.

---

### Feedback Injection & Context Budget Protection

When an audit fails or a worker blames an upstream artifact, feedback is injected directly into the upstream file's `FEEDBACK:` header:
```markdown
<!-- CLEANROOM METADATA
FEEDBACK: [from spec_qa at 2026-10-16T12:00:00Z]
Low stub `PathNormalizer.normalize()` missing precondition checking for null bytes.
Amend planning/core.md [contract:path_sanitization] before re-stamping.
LAST_CLEANED: ...
-->
```

**Context Budget Protection Rules**:
- **Bounded Size**: The `FEEDBACK:` block is clamped to `max_feedback_chars` (default: 1,000 characters).
- **FIFO Eviction**: New feedback replaces older entries to avoid context window explosion.
- **Automatic Clearance**: When the upstream node successfully passes cleaning and is stamped clean, the `FEEDBACK:` block is automatically purged.

---

## 6. Specification Grounding & Physical Workspace Assembly

### The Formal Grounding Invariant

Every class, method, helper function, and external import in `lib/*.py` must be explicitly grounded in an upstream specification. Uncontracted "speculative" code is strictly prohibited.

In `low/*.pyi`, every non-public member and internal collaborator must declare a `GROUNDING:` section:
```python
class ManifestHasher:
    """Computes deterministic tree hashes for workspace manifests.
    
    GROUNDING:
    Implements manifest integrity contracts from planning/manifest_impl.md Section 4.
    Used by WorkspaceAssembler to certify sandbox immutability.
    """
    def compute_tree_hash(self, root: str) -> str: ...
```

---

### Physical Workspace Provisioning & Permission Masking

The `parts/workspace` module provisions isolated sibling sandboxes:
```
../role_workspaces/<session_id>/<scope>_<role>/
├── update_with_ai/                     # Symlinked package root
│   └── parts/
│       └── storage/
│           ├── high/                   # Upstream: chmod 444 (Read-Only)
│           ├── planning/               # Upstream: chmod 444 (Read-Only)
│           ├── scenarios/              # Upstream: chmod 444 (Read-Only)
│           ├── low/                    # Target: chmod 644 (Writable)
│           └── lib/                    # HIDDEN (Double-blind isolation)
```

1. **Target File**: Staged as a writable file (`chmod 644`).
2. **Upstream Specifications**: Mounted as read-only copies or symlinks with `chmod 444`. Any attempt by the worker to edit an upstream file results in an OS permission denied error.
3. **Hidden Roles**: Sibling and downstream roles are omitted entirely. A `lib/` worker cannot see `tests/`; a `tests/` worker cannot see `lib/`.
4. **Package Projections**: Top-level packages are symlinked so native imports (`import update_with_ai...`) work seamlessly without PYTHONPATH hacks.

---

### Retirement of Legacy Build Artifacts

All legacy Bazel markers have been purged:
- Deleted all `MODULE.bazel`, `BUILD.bazel`, and `bazel_manifest_ext` references.
- All tools dynamically resolve package roots relative to the nearest `.git` directory, `pyproject.toml`, or `BUILD_WORKSPACE_DIRECTORY`.

---

## 7. Packaging, Distribution & CLI Execution Architecture

### Native Python Packaging (`pyproject.toml` + `uv`)

Cleanroom is packaged as a standard Python package managed with `hatchling` and `uv`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cleanroom"
version = "0.1.0"
description = "Literate, specification-driven neural compilation and double-blind agentic engineering framework"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "tomli>=2.0; python_version < '3.11'",
]

[project.scripts]
cleanroom = "update_with_ai.parts.control.lib.cleanroom_cli:main"
```

---

### Dynamic Workspace Root Derivation

Cleanroom tools derive the active workspace root dynamically in this precedence order:
1. Explicit `--workspace-root <path>` CLI argument.
2. `BUILD_WORKSPACE_DIRECTORY` environment variable (if invoked via build runners).
3. Ascending filesystem search for `pyproject.toml` or `.git`.
4. Current working directory (`os.getcwd()`).

Hardcoded repository paths or directory names are strictly prohibited by Cleanroom behavioral rules.

---

### Ephemeral Zero-Install Distribution (`uvx`)

Cleanroom supports zero-install execution on arbitrary repositories via `uvx`:
```bash
uvx cleanroom orchestrate //my_project/parts/auth#lib
```
`uvx` downloads the ephemeral Cleanroom wheel, executes the coordinator, builds the sibling workspaces, and cleans the target without requiring Cleanroom to be cloned into the target project.

---

### Unified CLI Command Architecture

All CLI commands are routed through `update_with_ai/parts/control/lib/cleanroom_cli.py`:

```
cleanroom <subcommand> [arguments] [options]
```

- **`orchestrate <scope> [target_role]`**: Launches autonomous multi-agent wave coordinator (Option 4).
- **`clean <scope> [target_role] [--harness loop|dsh|antigravity]`**: Cleans target using chosen harness.
- **`work-queue <scope> [target_role]`**: Returns topologically sorted list of dirty nodes.
- **`commission <target>#<role>`**: Provisions isolated sibling workspace sandbox.
- **`decommission <target>#<role>`**: Destroys active sibling workspace sandbox.
- **`submit <target>#<role> --change-summary="..."`**: Verifies tests and marks target clean.
- **`fail <target>#<role> --reason="..."`**: Rejects target and records failure feedback.
- **`blame <target>#<role> --upstream=<node> --reason="..."`**: Injects feedback into upstream spec.
- **`mark-clean <target>#<role>`**: Explicitly marks target clean without code changes.
- **`dirty <scope>`**: Lists all dirty nodes and their triggering dependency causes.
- **`coverage <scope>`**: Runs statement and branch coverage analysis.
- **`check_files <scope>`**: Validates file format compliance and metadata headers.

---

## 8. Multi-Harness Telemetry & Desktop Integration

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

4. **DSH Skill (`skills/dsh/SKILL.md`)**:
   - Provides turnkey system instructions for DSH workers operating inside sibling sandboxes.

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
