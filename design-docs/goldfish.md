# Goldfish: A Purpose-Built Agent Harness for Weak-Memory Local Models

> **Document Type:** Architectural Design Proposal & Post-Mortem Synthesis  
> **Status:** Proposed  
> **Scope:** Custom headless `HarnessAdapter` (`harness = "goldfish"`) exclusively for `uv run autofab clean` and `uv run autofab benchmark`, targeting Tier 1 local "goldfish" models (e.g., `qwen-moe`, `qwen-dense`, `gemma-moe`, `gemma-dense` via `omlx`).

---

## 1. Executive Summary: Should We Try Again?

Autofab previously built an in-process custom agent loop (`autofab/parts/loop` and `autofab/parts/openai`, documented as **Option 1** in [`design.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/design.md)) and retired it. Meanwhile, **DeepSeek Harness (`dsh`)** and **Google Antigravity** have become the production harnesses.

However, DSH and Antigravity are **general-purpose interactive coding harnesses** designed around frontier or strong cloud models (`deepseek-flash`, `gemini-flash`, `claude-sonnet`). When we run Tier 1 local Mixture-of-Experts models like `qwen-moe` (Qwen 3.6 35B A3B MoE via `omlx`) through DSH for `uv run autofab clean` and `uv run autofab benchmark`, we hit a fundamental impedance mismatch:

- **DSH's leanest preset (`preset-standard`)** still pays a ~967-token system prompt + ~1.7K-token `bash_run` schema tax and gives the model an open-ended shell.
- **No Progressive Discovery or Goldfish Reminders**: Existing harnesses (DSH and Antigravity) force us to dump entire role guides (`guides/*.md`) upfront and *hope* the model reads them, remembers the right rule 6 steps later, and applies it at the right moment.
- **"Goldfish" models** (fast decode, sparse active parameters, narrow effective working attention) lose track of multi-step instructions after 4–6 tool calls, forget to run `bin/get_work` or `bin/submit`, get stuck in micro-read loops, hallucinate unified diff anchors, truncate monolithic file writes, and blow local `omlx` prefill budgets when conversation history mutates.

**Verdict: Yes, we should try again—but NOT by building another general-purpose ReAct loop.**  
Because `goldfish` only needs to execute `autofab clean` and `autofab benchmark` inside an already-provisioned physical role workspace (`../autofab_role_workspaces/...`), the harness already knows the role, the target file(s), the read-only specs, and the exact lifecycle binaries (`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, `bin/fail`, `bin/reject`, `bin/revert`, `bin/checkpoint`). Instead of asking a goldfish model to pilot a general-purpose CLI agent or own an entire file across every phase in one long trajectory, **`goldfish` turns the lifecycle into a deterministic Python state machine that breaks each role round into focused, short-horizon micro-tasks.**

---

## 2. Post-Mortem: Why the Old Agent Loop (`parts/loop`) Failed

Before designing `goldfish`, we must be honest about why the previous custom loop (`parts/loop` + `parts/openai`) failed horribly, as evidenced in [`design.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/design.md), [`todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md), [`agent_config.md`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/agent/high/agent_config.md), and [`json_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/core/high/json_ext.md).

### 2.1 Structural Root Causes of the Old Loop's Failure

1. **No Physical Workspace Isolation**:  
   `parts/loop` operated directly against the main repository metadata ([`design.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/design.md) §4) rather than Autofab's physical sibling role workspaces with OS `chmod 444` read-only mounts. It relied on procedural tool-masking, leaving it vulnerable to path confusion and cross-role contamination.
2. **Band-Aids for Goldfish Memory Inside a Generic Chat Loop**:  
   Look at the policy surface preserved in [`agent_config.md`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/agent/high/agent_config.md) and [`json_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/core/high/json_ext.md)—every single flag was a symptom of trying to patch a generic multi-step ReAct loop for weak models:
   - `supersede_arg_keep`: Retaining trailing characters of superseded string arguments as hints because models forgot what they had just edited.
   - `inject_followups`: Injecting follow-up tool calls inside tool responses because models forgot the next workflow step (`get_work` $\to$ edit $\to$ `check_files` $\to$ `submit`).
   - `is_step_mode`: Delivering role guides progressively because dumping a full guide into a ReAct context overwhelmed the model's attention.
   - `is_startup_reads` & `edit_delta_output`: Pre-loading files and shrinking edit echoes to fight context bloat.
   - `json_ext` truncated JSON salvage: Attempting to repair unclosed quotes and braces when models hit output token limits mid-tool-call.
3. **Unrecoverable Death Spirals in `loop_guard.py`**:  
   `loop_guard.py` had a repetition guard (detecting identical sequential tool calls) and a 15-step limit, but it could only **abort**—not recover, checkpoint, or reframe working memory.
4. **Conflation of Lifecycle Orchestration and Content Authoring**:  
   In a generic ReAct loop, the model spends half its cognitive budget and half its steps on *mechanics* (listing files, reading guides, running `bin/get_work`, remembering `bin/check_files`, remembering `bin/submit`) instead of *semantics* (satisfying the specification).

### 2.2 What Changed Since Then?

Autofab now has three pieces that `parts/loop` lacked:
1. **Physical Role Workspaces (`parts/workspace`)**: Every `RoleDispatch` already provisions an isolated sibling directory with `chmod 444` read-only dependencies and `bin/*` micro-binaries.
2. **Unified `HarnessAdapter` Protocol ([`subagent_harness.py`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/subagent/lib/subagent_harness.py) & [`subagent_coordinator.py`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/subagent/lib/subagent_coordinator.py))**: The DAG coordinator (`autofab/parts/subagent/`) already handles wave scheduling, blame propagation, `concurrent_subagents = 1` hardware contention bounding, and `RoleRoundResult` / `TokenUsage` telemetry. A new harness only needs to implement `dispatch_role`, `await_role`, `poll_role`, and `interrupt_role`.
3. **Deterministic Triage & Checkpointing (`parts/workspace_cli`)**: `bin/check_files` already produces compact diagnostics and structured Triage Summaries, and `bin/checkpoint` / `bin/revert` already snapshot and restore workspace state.

---

## 3. Understanding the "Goldfish" Failure Profile (`qwen-moe` on `omlx`)

Empirical runs and broader coding-agent research converge on four specific failure modes for small/sparse local models (such as Qwen 3.6 35B A3B MoE running 6-bit quantized on Apple Silicon via `omlx`):

1. **Observation Bloat & Context Rot ("Lost in the Middle")**:  
   In standard coding agents, environment observations (`cat` dumps, `pytest` tracebacks, `pyright` banners, repeated reads) account for ~80%+ of context tokens. Once context grows past ~12K–20K tokens, sparse MoE models lose global attention: they drop spec invariants, forget earlier `FEEDBACK:` lines, or undo working fixes when a downstream error appears.
2. **Edit-Format Fragility**:  
   - *Unified diffs* fail because small models miscalculate shifting `@@ -X,Y +A,B @@` line offsets.
   - *Search/replace blocks* fail on minor whitespace/indentation mismatches (`ERROR: search block not found`).
   - *Monolithic whole-file rewrites* hit output token ceilings (e.g., 8K tokens, as noted in [`scaffold_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/workspace/lib/scaffold_impl.py#L863)) and truncate trailing methods or silently drop imports.
3. **Conversational Halting & Retry Loops**:  
   When a linter or test fails, goldfish models either emit prose without a tool call (halting prematurely) or submit 5–10 trivial variations of the same broken edit without stepping back.
4. **The `omlx` / MLX Prefill Tax**:  
   On Apple Silicon unified memory, if a harness mutates anything early in the prompt (timestamps, step counters, dynamic tool lists, or rewritten history), `omlx` cannot reuse the KV prefix cache and must re-prefill tens of thousands of tokens on every step. Conversely, blindly appending 15 turns of raw errors balloons KV memory and degrades attention.

---

## 4. Core Design of the `goldfish` Harness

`goldfish` is **not** a chat agent. It is a **deterministic Python round driver** wrapping a minimal, KV-cache-aligned LLM step function.

### 4.1 Harness-Owned Lifecycle (Zero Lifecycle Tool Calls)

In `goldfish`, the model **never** executes `bash_run`, `bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, `bin/fail`, or `bin/checkpoint`. The Python harness drives the `bin/*` binaries directly via subprocesses inside `dispatch.workspace_dir`:

```
RoleDispatch (from SubagentCoordinator)
  │
  ▼
1. Harness runs `bin/get_work` in workspace_dir
  ├─ Auditor role & 0 ready targets (auto-submitted clean)?
  │    └─► Return RoleRoundResult(status="completed") immediately (0 LLM tokens!)
  │
  ▼
2. Build Static Prefix (KV-Cache Pinned, byte-identical across all steps for this target)
  │  [Role Persona + Condensed Rules + Tool Schemas + Read-Only Upstream Specs]
  │
  ▼
3. Step Loop (max_steps = 10, deterministic state machine)
  ├─► Construct Dynamic Tail:
  │     [Current Target File (line-numbered, fresh from disk)]
  │     + [Active FEEDBACK / CHANGE header]
  │     + [Compact Progress Ledger (1 line per prior step)]
  │     + [Latest `bin/check_files` / Triage Summary output]
  ├─► Call `omlx` OpenAI-compatible endpoint (`tool_choice="required"`)
  ├─► Execute single tool call:
  │     • `replace_lines` / `insert_lines` / `write_small_file`
  │     • `read_section` (bounded 150-line window into large read-only specs)
  │     • `escalate` (`blame` | `reject` | `fail`)
  ├─► Deterministic Post-Edit Gate:
  │     • Run `py_compile` / syntax check + `bin/check_files <target>`
  │     • If `bin/check_files` exits 0 (and not an auditor):
  │         └─► Harness runs `bin/submit <target> "<summary>"` automatically!
  │     • If `escalate` was called:
  │         └─► Harness runs `bin/blame` + `bin/submit` (or `bin/reject` / `bin/fail`).
  │     • Else update Progress Ledger, check cycle/regression guards, continue.
```

**Why this eliminates 50%+ of goldfish failures immediately:**
- Zero wasted steps on `bin/get_work`, `ls`, `cat`, or forgetting `bin/submit`.
- Zero shell-escaping bugs, zero `cd ..` escapes, zero `git` or `pytest` probe violations.
- **0-token auditor fast-path**: When `qa`, `spec_qa`, `coverage`, or `pretense_qa` passes `bin/get_work` cleanly, the harness never wakes up the GPU at all.

### 4.2 Fixed Working-Memory Context & Observation Masking

Research on small-model coding agents (e.g., *The Complexity Trap*) shows that **deterministic observation masking** outperforms LLM summarization: LLM summarizers smooth over compiler errors and cost extra tokens, whereas masking old observations keeps the model focused on the ground truth.

`goldfish` enforces a strict **two-part prompt layout**:

1. **Part 1 — Static Prefix (100% Byte-Identical Across Steps)**:
   - Minimal system prompt (~200–300 tokens, no conversational fluff).
   - 3–4 static tool schemas.
   - Read-only upstream specification files (`low/*.pyi`, `high/*.md`, `planning/*.md`) that fit within a configured prefix budget (e.g., 16K tokens). Files exceeding the budget are listed by path + line count and accessed via `read_section`.
   - **Invariant**: Zero timestamps, zero step numbers, zero mutable state in Part 1. On `omlx`, Part 1 is prefilled **once** per target and served from KV cache on every subsequent step.

2. **Part 2 — Ephemeral Working-Memory Tail (Rebuilt Fresh Every Step)**:
   Instead of an unbounded `messages` array that accumulates 10 stale copies of the file and 10 stale stack traces:
   - **Fresh Line-Numbered Target File**: Always read directly from disk at the start of the step, formatted as `  42 | def foo():`. The model never has to guess line numbers from 4 turns ago.
   - **Active `FEEDBACK:` / `# DIRTY:` Context**: Surfaced prominently right above the code.
   - **Compact Progress Ledger**: 1-line deterministic summary of each prior step (e.g., `Step 1: replace_lines(40..55) -> pyright: 2 errors (return type mismatch); Step 2: replace_lines(40..44) -> pytest: 1 failed (test_empty_pop)`).
   - **Latest Verification Output**: Only the *most recent* `bin/check_files` output, truncated deterministically to the first/most relevant failure block (e.g., max 1,500 tokens).

> **Note on Prefix-Cache vs. Stateless Tail**:  
> Keeping Part 1 static and sending `[Part 1 (cached)] + [Part 2 (fresh)]` as a 2-message request (`system` + `user`) means `omlx` gets a **70–85% KV prefix cache hit** on every step while the model's attention sees **zero stale observations** and **zero dead-end chat history**. (Optionally, `goldfish` can keep the last $K=1$ assistant/tool exchange if empirical benchmarks show `qwen-moe` benefits from seeing its immediate previous edit, flushing the tail whenever $K > 1$.)

### 4.3 Goldfish Reminders & Phase-Gated Progressive Discovery

The biggest missing capability in existing general-purpose harnesses (DSH and Antigravity) is **just-in-time (JIT) guidance**. Currently, Autofab must hand a worker an entire 300–500 line role guide (`guides/low_to_lib.md`, `guides/qa.md`, `guides/pretense.md`, etc.) at session start and hope the model reads it, retains the relevant constraint, and recalls it when a specific error occurs. Goldfish models cannot do this: front-loading an entire guide saturates attention, and by step 4 the model has forgotten the rules.

Because `goldfish` owns the step loop and inspects `bin/check_files` output directly, it replaces front-loaded guide dumps with two mechanisms injected into **Part 2 (the ephemeral dynamic tail)**:

1. **Phase-Gated Progressive Discovery**:  
   Role guides are segmented into concise, phase-indexed sections (or mapped per role/state). At each step, the harness determines the target's current phase and injects **only** the relevant slice:
   - *Phase 0 — Initial Authoring / Empty Starter*: Injects structure & authoring rules (e.g., `# Requirement:` citation syntax, incremental authoring, `@singleton_type` / protocol conventions).
   - *Phase 1 — Static / Type Repair (`pyright` / `low_lint` / `spec_lint` failing)*: Injects static typing & interface alignment rules (e.g., collaborator encapsulation, no `Any` / `type: ignore` escapes).
   - *Phase 2 — Behavioral / Test Failure (`pytest` failing)*: Injects failure-triage rules (or for auditors, double-blind blame formulation rules: cite only spec violations and line numbers in the blamed file).
   - *Phase 3 — Feedback / Coverage Resolution*: Injects `FEEDBACK:` handling (`submit` vs `reject`) or coverage-gap triage rules (e.g., checking for structurally unreachable code before blaming).

2. **Situational Goldfish Reminders (Diagnostic-Triggered JIT Rules)**:  
   When `bin/check_files` or workspace state matches a known failure pattern, the harness injects a **1–3 sentence reminder** directly beside the error in Part 2—and drops it as soon as the condition clears:
   - *Uncovered lines persist across 2 steps* $\to$ `"Reminder: Uncovered lines persisting across rounds often mean structurally unreachable branches in lib/*.py rather than missing tests—inspect the spec and blame lib/ if unreachable."`
   - *Target unmodified with active `FEEDBACK:`* $\to$ `"Reminder: If you agree with the feedback, edit the target; if you contest it without edits, call escalate(action='reject')."`
   - *`SyntaxError` or output truncation* $\to$ `"Reminder: Keep replace_lines edits under 150 lines; add methods incrementally."`
   - *Attempted monkeypatching / private attribute access detected by linter* $\to$ `"Reminder: Never monkeypatch live singletons or access private attributes on foreign collaborators; use @fake(Protocol) or public methods."`

Because these reminders live in Part 2 (the ephemeral tail) rather than Part 1 (the static prefix), **the `omlx` KV prefix cache on the specs stays 100% intact**, while the model's immediate attention window always contains the exact rule it needs *right now*.

### 4.4 Focused Micro-Task Decomposition (Breaking Up File-Owning Subagents)

In standard Autofab orchestration, a single subagent round owns an entire target file from start to finish: scaffolding, implementing every method or test case, resolving type/lint errors, fixing runtime failures, and addressing `FEEDBACK:`. For a goldfish model, holding all of those concerns in one continuous trajectory is the primary source of attention dilution and regression churn.

Because `SubagentCoordinator` only sees the outer `HarnessAdapter` boundary (`dispatch_role` / `await_role`), `goldfish` can **internally decompose a single `RoleDispatch` into focused, ephemeral micro-tasks**—sequentially dispatching fresh 1–3 step sub-invocations inside the same `workspace_dir` (respecting `concurrent_subagents = 1` on local GPUs):

1. **Task Type A — Skeleton / Structure Pass**:  
   Given `low/*.pyi` (or `planning/*.md`), emit only imports, class/protocol headers, and `...` / `NotImplementedError` method stubs, verified immediately with `ast.parse` and `pyright`.
2. **Task Type B — Per-Unit / Per-Contract Synthesis**:  
   Instead of writing 400 lines at once, the Python driver parses the AST/stub methods or `# Requirement:` slugs and spawns a focused micro-task for **one method or one requirement group at a time**, showing only the target's signature, its DbC docstring/contract, and the local line slice to replace.
3. **Task Type C — Isolated Error Fixer**:  
   When `bin/check_files` reports errors, the driver clusters diagnostics by symbol/location and spawns a dedicated micro-task with **only** that error message, a ±30-line window around the offending symbol, and the relevant spec contract. The model never sees unrelated methods or prior failed fix attempts for other functions.
4. **Task Type D — Feedback / Coverage Triage**:  
   When `FEEDBACK:` or an uncovered line span is present, a dedicated micro-task receives *only* that feedback/span and decides between a localized `replace_lines` fix or `escalate(blame/reject)`.

**Why micro-task decomposition pairs naturally with `omlx`:**
- **1–3 step horizon**: Each micro-task is tiny and self-contained, eliminating long-horizon drift, output token truncation, and "undoing working code" regressions.
- **Shared KV Prefix Cache**: Because every micro-task for the same target reuses the exact same **Part 1 Static Prefix** (role persona + tool schemas + read-only specs), `omlx` serves the heavy spec prefix from KV cache across micro-tasks while giving each micro-task a clean, unpolluted **Part 2** tail.
- **Zero Outer-DAG Complexity**: `SubagentCoordinator`, `autofab_roles.toml`, and `benchmarks/runs/` see a normal `RoleRoundResult`—all decomposition happens inside the `goldfish` harness.

> **Why Intra-File Micro-Tasks Beat Splitting Components**:  
> Sharding a system into many tiny independent `parts/*` components also shrinks per-target context, but at a steep **specification tax**: more `high/*.md`, `planning/*.md`, `scenarios/*.md`, and `low/*.pyi` files, more `_ext.md` / `GROUNDING:` boundaries, and more cross-component grounding churn. By keeping components cohesive at the specification level and decomposing *execution* inside the `goldfish` harness (per method, per `# Requirement:` slug, per error cluster), we get bounded 1–3 step working-memory tasks for `qwen-moe` **without** multiplying specification complexity or grounding issues.

### 4.5 Goldfish-Friendly ACI (3 Tools, Strict Line-Slice Editing)

`goldfish` exposes **at most 3 tools**, using OpenAI-compatible `tools` with `tool_choice="required"` (preventing prose-only halting):

1. **`replace_lines(start_line: int, end_line: int, new_code: str, summary: str)`**  
   - Replaces 1-indexed lines `[start_line, end_line]` in the active target file with `new_code` (supports insertion when `end_line < start_line` or deletion when `new_code == ""`).
   - Because the harness *just* rendered the fresh line-numbered file in Part 2 of the same step, `start_line` and `end_line` are exact—no whitespace-sensitive `SEARCH/REPLACE` blocks and no unified diff hunk offsets.
   - **Size Guard**: Rejects single calls where `new_code` exceeds a configurable line/token cap (e.g., 200 lines) unless the file is currently an empty starter template, enforcing incremental authoring without relying on prompt lectures.
   - **Syntax Pre-Gate**: For `.py` / `.pyi` files, runs `ast.parse` in-process *before* running `bin/check_files`. If `ast.parse` fails, the harness reverts the edit via `bin/revert` (or in-memory backup) and returns the exact 3-line `SyntaxError` without wasting a `bin/check_files` subprocess.
2. **`read_section(path: str, start_line: int, end_line: int)`**  
   - Reads a bounded window (max 150 lines) of a declared read-only file that was too large to inline in Part 1.
   - Prevents micro-read loops by rejecting identical `(path, start_line, end_line)` requests within the same round.
3. **`escalate(action: "blame" | "reject" | "fail", target_path: str, reason: str)`**  
   - Cleanly maps to `bin/blame <target_path> "<reason>"` + `bin/submit`, `bin/reject`, or `bin/fail`.
   - For auditor roles (`spec_qa`, `qa`, `coverage`, `pretense_qa`), `replace_lines` is omitted from the tool list entirely—only `read_section` and `escalate` are exposed.

### 4.6 Deterministic Death-Spiral & Regression Guards

To prevent the classic small-model failure modes observed in `parts/loop` and documented in coding-agent literature:

1. **Edit-Hash Cycle Breaker**:  
   The harness computes the sanitized `CODE_HASH` after every `replace_lines`. If the resulting file hash matches *any* previously visited hash in the current round (e.g., the model oscillates between State A and State B), the harness rejects the transition, reverts, and injects a hard directive into the Progress Ledger: *"Step N reverted: produced identical state to Step K. Choose a different fix or call `escalate`."*
2. **Monotonic Progress Checkpointing**:  
   After each `bin/check_files`, the harness parses a coarse error score `(pyright_errors, test_failures)`. Whenever a step achieves a strictly better score, it records a `bin/checkpoint`. If a subsequent step *increases* errors (e.g., breaking 5 previously passing tests), the Progress Ledger explicitly warns the model (`REGRESSION: errors increased 1 -> 6; consider reverting or fixing the new breakage`), and if two consecutive steps regress, the harness can auto-restore the best checkpoint.
3. **Hard Step & Token Ceilings**:  
   Default `max_steps = 10` per target (with `tool_choice="required"`). If exhausted without passing `bin/check_files`, the harness invokes `bin/fail <target> "goldfish step budget exhausted (10 steps)"` and returns a clean `RoleRoundResult`.

---

## 5. Integration Architecture with Autofab

`goldfish` is designed to drop cleanly into Autofab's existing `SubagentCoordinator` and `benchmarks` infrastructure with zero special-casing in the DAG engine:

1. **Package Placement**:  
   A new part `autofab/parts/goldfish/` (or an adapter module inside `autofab/parts/subagent/`) implementing `subagent_coordinator.HarnessAdapter` (`dispatch_role`, `await_role`, `poll_role`, `interrupt_role`) and registering `"goldfish"` in `HarnessRegistry` ([`subagent_harness.py`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/subagent/lib/subagent_harness.py)).
2. **Model Configuration ([`model_configs.toml`](file:///Users/seanmcdirmid/projects/cleanroom/model_configs.toml))**:  
   Supports `harness = "goldfish"` alongside `"dsh"` and `"antigravity"`, e.g.:
   ```toml
   [models.qwen-moe-goldfish]
   model = "qwen-moe"
   provider = "omlx"
   harness = "goldfish"
   tier = 1
   tier_label = "Local Engine (Goldfish)"
   rate_uncached_in = 0.0
   rate_cached_in = 0.0
   rate_out = 0.0
   timeout_seconds = 100.0
   run_timeout_seconds = 14400.0
   subagent_batch_size = 1
   concurrent_subagents = 1
   ```
3. **Telemetry Parity**:  
   Captures `usage.prompt_tokens`, `usage.prompt_tokens_details.cached_tokens`, and `usage.completion_tokens` from `omlx`'s OpenAI-compatible response into `subagent_coordinator.TokenUsage`, so `uv run autofab benchmark` produces apples-to-apples comparisons against `dsh`.
4. **Fused / Baseline Roles**:  
   For `pretense` or baseline roles where multiple files are writable in one workspace, `goldfish` iterates over the ready targets returned by `bin/get_work` (or accepts `target_path` on `replace_lines`), keeping the same static-prefix + fresh-file-tail discipline.

---

## 6. Evaluation Plan & Phased Rollout

Rather than committing to a full rewrite up front, we can validate `goldfish` empirically using Autofab's existing benchmark suite:

### Phase 1: Minimal Prototype (`--harness goldfish`)
- Implement `GoldfishHarnessAdapter` with `bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, `bin/fail` subprocess calls.
- Implement the 2-part prompt (`Static Prefix` + `Fresh Line-Numbered Tail`), `replace_lines` + `read_section` + `escalate`, `ast.parse` pre-gate, and 0-token auditor fast-path.
- Use `omlx` OpenAI-compatible `/v1/chat/completions` with `tool_choice="required"`.

### Phase 2: Cycle & Regression Guards
- Add `CODE_HASH` cycle detection and `(pyright_errors, test_failures)` progress checkpointing.
- Log per-step cache hit ratios (`cached_tokens / prompt_tokens`) and step counts to verify `omlx` prefix caching is actually firing.

### Phase 3: Head-to-Head Benchmark (`dsh` vs. `goldfish`)
Run `uv run autofab benchmark` comparing `qwen-moe` (`harness = "dsh"`) against `qwen-moe-goldfish` (`harness = "goldfish"`) on:
1. `ring_buffer` (~500 LOC baseline)
2. `lru_cache` (stateful edge cases)
3. `dag_engine_lite` (~1,000 LOC Tier 1 ceiling)

**Success Criteria**:
- Higher or equal pass rate on `dag_engine_lite` and `lru_cache` with `qwen-moe`.
- $\ge 30\%$ reduction in wall-clock time and total tokens per run (driven by 0-token auditor passes, eliminated lifecycle tool calls, and higher `omlx` KV prefix cache hit rates).
- Zero truncated-output crashes or micro-read death spirals.

If Phase 3 beats `dsh` on `qwen-moe`, `goldfish` becomes the default Tier 1 local harness in `model_configs.toml` while `dsh` and `antigravity` remain the production harnesses for Tier 2–4 models.
