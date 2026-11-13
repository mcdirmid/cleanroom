# Antigravity Subagent Architecture, Desktop IPC (`agentapi`), Lifecycle Hooks & Hermetic Isolation

> **Document Type:** Canonical Architectural Specification & System Guide  
> **Status:** Production / Implemented & Active Proposal  
> **Scope:** Google Antigravity Subagent Runtime, Zero-Execution Coordinator (`autofab_coordinator`), Role Workers (`autofab_worker`, `autofab_baseline_worker`), Desktop IPC (`agentapi`), Background Prompt Starvation Elimination, Lifecycle Hooks (`PreToolUse`), Role Workspace Rooting, and Transparent Command Rewriting (`overwrite`).

---

## 1. Executive Summary & Core Architectural Problem

Autofab enforces a strict **Cleanroom methodology**: every development role (`lib`, `test`, `qa`, `coverage`, `pretense`, etc.) executes in a completely isolated, ephemeral role workspace provisioned outside the canonical monorepo:
```
/Users/seanmcdirmid/projects/autofab_role_workspaces/<role>_<scope>/
```
In Google Antigravity environments, Autofab operates seamlessly across interactive pair programming, autonomous multi-agent coordination, and automated benchmarking flights. However, running autonomous subagents inside Google Antigravity requires bridging fundamental architectural gaps between the host IDE platform and Cleanroom's strict isolation invariants.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   ANTIGRAVITY EXECUTION MODEL                                    │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│   1. CONVERSATIONAL CHAT (Interactive Root User Session)                                         │
│      - Natural human-agent dialogue, architecture, git, code editing, testing                    │
│      - ZERO BOUNDARIES / ZERO POLICY RESTRICTIONS: Completely exempt from Autofab hooks           │
│                                                                                                  │
│   2. AUTOFAB COORDINATOR SUBAGENT (autofab_coordinator)                                          │
│      - Mission: Multi-agent DAG queue evaluation and worker dispatch/messaging                   │
│      - STRICTLY CONSTRAINED: Can ONLY launch/message subagents and run sanctioned queue CLIs     │
│      - ZERO CODE CUSTODY: No file authoring/editing, no git, no ad-hoc bash exploration          │
│                                                                                                  │
│   3. ROLE WORKER SUBAGENTS (autofab_worker, autofab_baseline_worker)                             │
│      - Hermetically rooted inside assigned ephemeral role workspace (<workspace_dir>)            │
│      - Auto-rooting wraps all commands with 'cd <workspace_dir> && (...) '                       │
│      - Strict prohibitions: no git, no unzip, no ad-hoc python/pytest probes, no host leaks     │
│                                                                                                  │
│                                      │                                                           │
│                                      ▼                                                           │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                          ANTIGRAVITY PreToolUse HOOK (gate.py)                           │   │
│   │                                                                                          │   │
│   │   1. Identify Agent Session:                                                             │   │
│   │      - If Conversational Chat (interactive root): ALLOW IMMEDIATELY                      │   │
│   │      - If Coordinator Subagent (autofab_coordinator):                                    │   │
│   │        • Prohibit all file modification tools (write_file, edit_file)                    │   │
│   │        • Whitelist run_command strictly to 'uv run autofab (work-queue|verify|...)'      │   │
│   │      - If Role Worker Subagent (active_workers.json or ws_pattern in prompt):            │   │
│   │        • Enforce Hermetic Root Invariant & workspace containment                         │   │
│   │                                                                                          │   │
│   │   2. Worker run_command Interception:                                                    │   │
│   │      • Prohibit 'git', 'unzip', and ad-hoc 'python'/'pytest' probe scripts               │   │
│   │      • Prohibit internal 'cd' (cd guides, cd bin, cd .., cd /)                           │   │
│   │      • Prohibit absolute path arguments referencing host cleanroom repo                  │   │
│   │      • Auto-wrap command via overwrite:                                                  │   │
│   │        "CommandLine": "cd <workspace_dir> && (<command>)"                                │   │
│   │                                                                                          │   │
│   │   3. Worker File Tools Interception (read_file, write_file, edit_file):                 │   │
│   │      • Relative path: resolve to "<workspace_dir>/<rel_path>"                            │   │
│   │      • Scratch path (/scratch/): DENY immediately                                        │   │
│   │      • Out-of-bounds absolute path: DENY immediately                                     │   │
│   │      • Path traversal (..): DENY if resolved path escapes <workspace_dir>                │   │
│   └──────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                                           │
│                                      ▼                                                           │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                       PHYSICAL ROLE WORKSPACE (100% CONTAINED)                           │   │
│   │   ~/projects/autofab_role_workspaces/<role>_<scope>/                                     │   │
│   │   ├── bin/ (get_work, check_files, submit, blame, fail, revert)                         │   │
│   │   ├── guides/ (role companion guide, e.g. pretense.md)                                   │   │
│   │   ├── AGENTS.md (role instructions & boundary rules)                                     │   │
│   │   └── <scope>/parts/<unit>/... (assigned target & dependency stubs)                      │   │
│   └──────────────────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### The Antigravity Impedance Mismatch
In Google Antigravity, subagents spawned via `invoke_subagent` inherit the host environment:
1. **Immutable Session Working Directory**: The IDE/CLI session is anchored to the repository where Antigravity was launched (`/Users/seanmcdirmid/projects/cleanroom`).
2. **Missing Workspace Parameter**: The `invoke_subagent` tool accepts `Workspace: "inherit" | "branch" | "share"`, designed exclusively for Git branches or worktrees of the *same parent repository*. It provides **no parameter** to set an external directory path as the subagent's working directory.
3. **Stateless Shell Sessions**: In Antigravity's shell execution model (`zsh`), every `run_command` invocation executes in a fresh subprocess. Running `cd <path>` in step $N$ does not persist to step $N+1$.

### The Resulting Failure Mode (The "Defensive Essay" Anti-Pattern)
To compensate for this limitation, earlier iterations injected a massive 300-word boilerplate lecture into every subagent prompt:
```
"You are an autonomous Autofab worker... Your assigned role workspace directory is '...'. Because shell working directory does not persist across tool calls, prefix all shell commands with 'cd ... && ' and use absolute paths under '...' for file operations..."
```
This defensive prompting caused catastrophic friction:
- **Cognitive Overload**: Weaker models (`gemini-flash`, `qwen-moe`) struggle to maintain dual-context spatial awareness (the host repo vs the role workspace).
- **Prompt Confusion & Hallucinations**: Models attempt to reverse-engineer paths, wander into the parent repository, or get derailed by platform suggestions (e.g. writing into platform `scratch/` folders).
- **Inconsistent Tool Usage**: Agents forget the `cd` prefix on subsequent turns, running `bin/get_work` in `cleanroom/` where the binary does not exist, triggering confusion loops.

---

## 2. Historical Post-Mortem: Option 2 FastMCP vs Option 4 Physical Isolation

The evolution of Antigravity subagent orchestration underwent a critical paradigm shift:

| Feature / Metric | Option 2: In-Tree FastMCP Subagents (Archived Post-Mortem) | Option 4: Production Sibling Workspaces & Lifecycle Hooks |
| :--- | :--- | :--- |
| **Execution Architecture** | Subagents inside main repo communicating via FastMCP tool server | Physical sibling workspaces outside repo + Zero-Execution Coordinator |
| **Isolation Mechanism** | Software prompt rules & tool wrappers | Physical OS filesystem (`chmod 444`) + PreToolUse hook auto-rooting |
| **Double-Blind Safety** | Repeatedly violated (agents peeked across directories) | 100% hermetic (host paths denied, relative paths auto-rooted) |
| **Token Cost / Run** | **$30–$50 per run** (Catastrophic token burn, prompt bloat) | **$0.15–$0.75 per run** (Scoped worker contexts, concise prompts) |
| **Reliability** | Severe socket contention, process lockups, rate-limit bursts | Deterministic completion, clean round-based handoffs |
| **Status** | **Failed & Permanently Archived** | **Production & Active** |

### Why FastMCP Subagents Failed
1. **Token Cost Explosion**: In Option 2, the subagent coordinator and workers shared complex in-tree tool schemas over FastMCP, incurring massive context inflation ($30–$50 per benchmark run).
2. **Instruction Degradation & Boundary Erosion**: Asking LLMs to police their own boundaries via prompt directives inevitably failed under multi-turn pressure: models inspected other roles' files, created conflicting git states, or attempted to fix tests by modifying library code.
3. **The Option 4 Triumph**: Decoupling the coordinator into a Zero-Execution DAG supervisor, isolating role workers into external sibling workspaces with POSIX permission masks, and enforcing boundary constraints via deterministic `PreToolUse` lifecycle hooks completely eliminated these pathologies.

---

## 3. Core Vision: The Hermetic Root Invariant

Instead of relying on fragile prompt engineering to beg the model to navigate directories, **the Antigravity Lifecycle Hook System (`PreToolUse`) enforces a strict, physical Root Invariant**:

> **The Hermetic Root Invariant**:
> For any Autofab role worker subagent, its assigned role workspace directory (`<workspace_dir>`) is its **sole, immutable universe**.
> 1. Every shell command (`run_command`) is automatically anchored to execute with working directory `<workspace_dir>`.
> 2. Direct directory navigation (`cd`) to external directories or subdirectories is strictly prohibited.
> 3. All file operations (`read_file`, `write_file`, `edit_file`) are strictly scoped within `<workspace_dir>`. Relative paths are automatically resolved against `<workspace_dir>`, and out-of-bounds absolute paths are hard-denied.

---

## 4. Multi-Agent Coordinator & Desktop IPC (`agentapi`)

### 4.1 The Zero-Execution Coordinator (`autofab_coordinator`)
The Autofab coordinator subagent (`autofab_coordinator`) drives the dependency DAG state machine without authoring or editing production code:
- **Zero Code Custody**: The coordinator never reads source code, writes files, or executes git commands. Its token budget is spent entirely on topological wave clustering and role worker dispatch.
- **Worker Dispatch**: Spawns workers via `invoke_subagent`:
  ```python
  invoke_subagent(
      TypeName="autofab_worker",
      Role=f"Autofab {role_name} Worker",
      Prompt=streamlined_worker_prompt
  )
  ```
- **Inter-Agent Messaging**: Dispatches updates, blame critique packets, and feedback notifications via `send_message(Recipient=worker_conv_id, Message=...)`.
- **Reactive Wakeup**: The coordinator does not poll in loops. Antigravity automatically wakes the coordinator when a worker subagent concludes its round or delivers a completion message.

### 4.2 Eliminating Background Prompt Starvation via Native Desktop IPC (`agentapi`)
In the Google Antigravity desktop IDE, commands that run longer than 10 seconds (such as `uv run autofab clean`, `benchmark`, or cross-model evaluations) are automatically converted into background support tasks.
- **The Starvation Problem**: When backgrounded, stdout is redirected to task logs (`.system_generated/tasks/task-X.log`). The active chat model never sees the completion output or the target scope in its prompt context, risking execution stall.
- **Dynamic Desktop Detection**: Autofab detects the Antigravity desktop IDE environment via:
  ```python
  is_antigravity = os.environ.get("ANTIGRAVITY_AGENT") == "1"
  ```
  It resolves the bundled `agentapi` executable from `$ANTIGRAVITY_AGENTAPI_EXE`, `PATH`, or `~/.gemini/antigravity/bin/agentapi`.
- **Reactive Wakeup Protocol (`agentapi send-message`)**:
  Autofab extracts `ANTIGRAVITY_CONVERSATION_ID` from the environment and executes:
  ```bash
  agentapi send-message --title "Autofab Coordinator Directive" \
    "$ANTIGRAVITY_CONVERSATION_ID" \
    "Clean all dirty nodes in <scope> using autofab_coordinator"
  ```
  This injects a high-priority reactive wakeup message directly into the active conversation, prompting the root model to invoke `autofab_coordinator` immediately without manual polling.

### 4.3 Headless Tab Dispatch (`agentapi new-conversation`)
For large-scale unattended benchmarking or continuous integration runs, Autofab supports dedicated tab dispatch via `--antigravity-dispatch=new-conversation`:
```bash
agentapi new-conversation --title="Autofab Coordinator: <scope>" -- \
  "Clean all dirty nodes in <scope> using autofab_coordinator"
```
This provisions an isolated conversation tab in the Antigravity desktop sidebar, keeping benchmark coordination separate from the user's interactive chat workspace.

### 4.4 The Autonomous Antigravity Coordination Directive
When a user or script triggers DAG convergence (e.g. `uv run autofab clean <target>` or `autofab orchestrate`), the tool emits the canonical coordination directive:
```
AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE:
Immediately invoke the coordinator subagent to clean the scope:
invoke_subagent(
    TypeName="autofab_coordinator",
    Role="Autofab Coordinator",
    Prompt="Clean all dirty nodes in <scope> using autofab_coordinator"
)
```

---

## 5. Detailed Component Architecture & Lifecycle Hook (`gate.py`)

### 5.1 Session Identification & Active Worker Registry

To enforce clean isolation without fragile global interceptors, `gate.py` classifies each tool call into one of three execution tiers:

1. **Conversational Chat (Root User Session)**:
   - Identified when the conversation is not registered as an Autofab worker and its initial context does not match coordinator or worker subagent dispatch signatures.
   - **Hook Action**: Immediately `allow()` without inspecting commands, file paths, or arguments. The developer and primary chat assistant are completely unbound.
2. **Coordinator Subagent (`autofab_coordinator`)**:
   - Identified via `conversationId` registration or prompt signature matching `Zero-Execution Autofab Coordinator` / `autofab_coordinator`.
   - **Hook Action**: Strictly constrained. Denies all file modification tools (`write_file`, `edit_file`). Constrains `run_command` strictly to sanctioned `uv run autofab` subcommands (`work-queue`, `verify-fused`, `harvest-fused`, `decommission`). All other commands (including `git`, `cat`, exploratory probes) are hard-denied.
3. **Role Worker Subagents (`autofab_worker`, `autofab_baseline_worker`)**:
   - Identified via `active_workers.json` lookup or fallback extraction of `workspace_dir` from the subagent prompt / `lastUserInput`.
   - **Hook Action**: Enforces the Hermetic Root Invariant (auto-rooting, relative path resolution, hard prohibition on `git`, `unzip`, probe scripts, internal `cd`, and workspace escapes).

### 5.2 Coordinator Constraints & Zero-Code Custody Enforcement

The `autofab_coordinator` subagent's sole purpose is driving the DAG state machine:
1. **Subagent Orchestration Tools**: Fully enabled (`invoke_subagent`, `send_message`, `manage_subagents`, `define_subagent`).
2. **Command Whitelist**: `run_command` is strictly restricted to matching:
   ```regex
   ^\s*uv\s+run\s+autofab\s+(?:work-queue|verify-fused|harvest-fused|decommission)\b
   ```
   Any other shell invocation (e.g. `git`, `cat`, `python`, `find`, `pytest`) is rejected with:
   > *"STRICT POLICY VIOLATION: The Autofab Coordinator subagent is strictly constrained to orchestrating subagents and may only execute 'uv run autofab' queue/lifecycle commands."*
3. **Zero File Custody**: Any call to `write_file`, `edit_file`, or content replacement tools is rejected with:
   > *"STRICT POLICY VIOLATION: The Autofab Coordinator subagent has zero code custody and cannot author or edit files."*

### 5.3 Worker `run_command` Gating, `cd` Prohibition & Auto-Rooting

When a `run_command` tool call is intercepted by `gate.py`:
1. **Worker Identification & Early Exemption**:
   - Look up `data["conversationId"]` in `active_workers.json` (or fallback via `lastUserInput`).
   - If not a worker subagent (`ws_dir is None`), allow execution immediately.
2. **Prohibit Git & Unzip for Worker Subagents**:
   - Direct `git` commands and inspection of `.git/` directories are prohibited to prevent lock contention, dirty working trees, and host monorepo confusion.
   - Unzipping runner binaries or inspecting internal tool archives is hard-denied.
3. **Prohibit Inline Testing & Probe Scripts**:
   - Role workers are strictly prohibited from executing ad-hoc Python probes (`python -c`), test runners (`pytest`), or exploratory scripts. Target verification relies exclusively on `bin/check_files <target>`.
4. **Prohibit Internal `cd` Navigation**:
   - In Cleanroom workspaces, all binaries (`bin/get_work`, `bin/check_files`, `bin/submit`, etc.) are designed to execute with `cwd == <workspace_dir>`.
   - Running `cd guides`, `cd bin`, `cd parts`, `cd ..`, or `cd /` is prohibited:
     ```python
     if re.search(r"\bcd\b", cmd) and not is_whitelisted_workspace_root(cmd, ws_dir):
         return {"decision": "deny", "reason": "STRICT BOUNDARY VIOLATION: Subagents are permanently rooted in their workspace directory..."}
     ```
5. **Prohibit Host Contamination in Arguments**:
   - Command strings containing absolute path references to the host repository (e.g. `/projects/cleanroom/`) are hard-denied.
6. **Transparent Auto-Rooting via `overwrite`**:
   - If the command does not already begin with `cd <workspace_dir> && `:
     ```python
     new_cmd = f"cd {workspace_dir} && ({original_cmd})"
     return {
         "decision": "allow",
         "overwrite": {
             "CommandLine": new_cmd
         }
     }
     ```
   - When Antigravity executes the tool, it executes inside `<workspace_dir>`, anchoring the subagent transparently to its role workspace root.

### 5.4 File Tools Interception (`read_file`, `write_file`, `edit_file`)

When file manipulation tools are called by a registered worker:
1. **Extract Target Path**: Extract `Path` from arguments.
2. **Prohibit Scratch Directories**:
   - Paths matching `/scratch/` or ending in `/scratch` are hard-denied:
     > *"STRICT POLICY VIOLATION: Authoring files in scratch/ directories is strictly prohibited. Author assigned target files directly in place within your workspace."*
3. **Relative Path Auto-Rooting**:
   - Relative paths are automatically resolved: `abs_path = os.path.normpath(os.path.join(workspace_dir, path))`.
   - If `abs_path.startswith(workspace_dir + os.sep)`, overwrite `Path` with `abs_path` and allow.
   - If path traversal (`../../...`) escapes `<workspace_dir>`, deny with boundary violation.
4. **Absolute Path Boundary Enforcement**:
   - Absolute paths are canonicalized with `os.path.realpath(os.path.normpath(path))`.
   - If the canonical path resides within `<workspace_dir>`, allow as-is.
   - If the canonical path points outside `<workspace_dir>` (e.g. pointing to `cleanroom/`), deny immediately.

### 5.5 Workspace-Local Plugin & Lifecycle Hook Architecture

To prevent global hook pollution across unrelated projects on the developer machine:
1. **Workspace-Local Installation**:
   All Antigravity plugins, agent definitions, and lifecycle hooks live strictly inside the target repository's `.agents/` customization root:
   ```text
   <workspace_root>/.agents/
   ├── plugins.json                  # Manifest enabling local plugins
   ├── plugins/
   │   └── autofab/
   │       ├── plugin.json           # Plugin descriptor
   │       ├── hooks.json            # Plugin PreToolUse lifecycle gate
   │       ├── hooks/
   │       │   └── gate.py           # Hermetic root boundary enforcement script
   │       ├── rules/
   │       │   └── AGENTS.md         # Workspace boundary & role rules
   │       └── agents/
   │           ├── autofab_coordinator/agent.md
   │           ├── autofab_worker/agent.md
   │           └── autofab_baseline_worker/agent.md
   ├── hooks.json                    # Workspace-level fallback hook entry
   └── agents/                       # Workspace-level standalone agent fallbacks
   ```
2. **Zero Global Hook Pollution**:
   The global customization directory (`~/.gemini/config/plugins/autofab/`) is completely free of lifecycle hooks. Antigravity chat sessions in other repositories never execute `gate.py`.
3. **Just-In-Time & Explicit Provisioning**:
   - Explicit CLI: `uv run autofab install-antigravity-plugin` provisions or refreshes `.agents/plugins/autofab`.
   - Just-in-Time: Running `uv run autofab clean`, `benchmark`, or `orchestrate` targeting an Antigravity model profile automatically ensures `.agents/plugins/autofab` is provisioned before emitting directives.

---

## 6. Subagent Concurrency & Hardware Resource Policy

### Strict Prohibition of `concurrent_subagents` on Antigravity
Autofab provides a `concurrent_subagents` configuration parameter to bound local GPU memory contention on single-GPU hardware (e.g. Tier 1 local offline models under `dsh` or `omlx`).

> [!IMPORTANT]
> **Antigravity Concurrency Invariant**:
> - `concurrent_subagents` is **strictly disallowed for models using the `antigravity` harness**.
> - Antigravity manages subagents through interactive desktop sessions and cloud APIs (e.g. Gemini 3.8 Flash, Gemini 4 Argon) that scale parallel subagent waves horizontally.
> - Attempting to configure `concurrent_subagents` on a model configured with the `antigravity` harness raises a configuration validation error.

---

## 7. Complete Edge Case & Hazard Analysis

| Hazard / Edge Case | Risk Level | Failure Mechanism | Deterministic Hook Mitigation |
| :--- | :--- | :--- | :--- |
| **Subdirectory `cd` (`cd guides`)** | HIGH | Agent runs `cd guides && cat spec.md`. Subshell changes directory, breaking subsequent commands. | Match `\bcd\s+` across shell operators. Hard-deny any `cd` other than `cd <workspace_dir>`. |
| **Path Traversal (`..`)** | HIGH | Agent passes `read_file("../../cleanroom/parts/...")` or `../other_ws/`. | Compute `os.path.realpath(os.path.normpath(...))`. Verify `resolved.startswith(workspace_dir + os.sep)`. Hard-deny escapes. |
| **Absolute Path Redundancy** | MEDIUM | Agent passes full path `/Users/.../ws/guides/spec.md`. Blindly prefixing `ws` yields `/Users/.../ws/Users/.../ws/...`. | Check `os.path.isabs(path)`. If absolute and inside `<ws>`, allow as-is without re-prefixing. |
| **Host Contamination in CLI** | HIGH | Agent runs `cat /Users/.../cleanroom/parts/foo/lib/foo.py` or `python3 /cleanroom/...`. | Regex-scan CLI arguments for canonical host repo paths (`/cleanroom/`). Hard-deny external path arguments. |
| **Dispatch Race Condition** | MEDIUM | Worker executes tool 1 before coordinator finishes writing `active_workers.json`. | Parse `workspace_dir` from hook payload's `lastUserInput` and self-register on the fly. |
| **Coordinator Interference** | CRITICAL | Hook accidentally constrains coordinator or interactive session to an isolated role workspace. | Coordinator / interactive `conversationId` is strictly excluded from `active_workers.json`. Non-workers remain unconstrained in `cleanroom/`. |
| **Worker vs Global Rule Conflation** | CRITICAL | Placing role worker constraints (`git`, `unzip`, ad-hoc probe scripts) in global hook scope blocks developer workflows. | Gated strictly behind `ws_dir is not None`. All non-worker sessions (root chat, other repos) immediately `allow()`. |
| **Pre-existing `cd <ws>` Prefix** | LOW | Prompt or legacy script already includes `cd <ws> &&`. Prepending creates nested `cd <ws> && cd <ws> && ...`. | Strip or recognize matching prefix before applying auto-rooting wrapper. |
| **Symlink Escapes** | MEDIUM | Workspace contains symlinks pointing back to canonical monorepo. | Apply `os.path.realpath` boundary checks against canonical root targets. |

---

## 8. Decision Matrix

### 8.1 Conversational Chat (Interactive Root Session)
The conversational chat represents direct developer interaction and is **completely unconstrained**:

| Tool Call | Path / Command Form | Hook Decision | Hook Action / Overwrite |
| :--- | :--- | :--- | :--- |
| `run_command` | `git status`, `git commit`, `git push` | **ALLOW** | Execute normally in host repository. |
| `run_command` | `bin/test`, `uv run ...`, `pytest` | **ALLOW** | Execute normally in host repository. |
| `read_file` / `edit_file` / `write_file` | Any path across monorepo / filesystem | **ALLOW** | Execute normally in host repository. |
| Any Tool | Any invocation | **ALLOW** | Completely exempt from Autofab lifecycle gates. |

### 8.2 Coordinator Subagent (`autofab_coordinator`)
The coordinator is **strictly constrained to DAG orchestration** and has zero code custody:

| Tool Call | Path / Command Form | Hook Decision | Hook Action / Overwrite |
| :--- | :--- | :--- | :--- |
| `invoke_subagent` / `send_message` | Any subagent coordination | **ALLOW** | Normal multi-agent orchestration. |
| `manage_subagents` / `define_subagent`| Any lifecycle management | **ALLOW** | Normal subagent lifecycle control. |
| `run_command` | `uv run autofab work-queue ...` | **ALLOW** | Sanctioned DAG queue evaluation. |
| `run_command` | `uv run autofab verify-fused ...` | **ALLOW** | Sanctioned fused verification. |
| `run_command` | `uv run autofab harvest-fused ...` | **ALLOW** | Sanctioned atomic target harvest. |
| `run_command` | `uv run autofab decommission ...` | **ALLOW** | Sanctioned workspace decommission. |
| `run_command` | `git ...`, `cat ...`, `find ...`, ad-hoc | **DENY** | Error: Coordinator is restricted to `autofab` orchestration CLIs. |
| `write_file` / `edit_file` | Any path | **DENY** | Error: Coordinator has zero code custody. |

### 8.3 Role Worker Subagents (`ws_dir is set`)
Role workers are **hermetically rooted inside `<workspace_dir>`**:

| Tool Call | Path / Command Form | Hook Decision | Hook Action / Overwrite |
| :--- | :--- | :--- | :--- |
| `run_command` | `bin/get_work` (no `cd`) | **ALLOW** | Overwrite: `cd <ws> && (bin/get_work)` |
| `run_command` | `cd guides && cat spec.md` | **DENY** | Error: Direct `cd` into subdirectories is strictly prohibited. |
| `run_command` | `git status` / `git log` | **DENY** | Error: Direct `git` operations prohibited; use workspace binaries. |
| `run_command` | `unzip bin/check_files` | **DENY** | Error: Unzipping runner binaries prohibited. |
| `run_command` | `python -c "import foo"` / `pytest` | **DENY** | Error: Role workers are prohibited from running ad-hoc probes/tests. |
| `run_command` | `cat /path/to/cleanroom/...` | **DENY** | Error: Host repository contamination prohibited. |
| `read_file` | `guides/pretense.md` | **ALLOW** | Overwrite: `{"Path": "<ws>/guides/pretense.md"}` |
| `read_file` | `../../cleanroom/foo.py` | **DENY** | Error: Path traversal outside workspace prohibited. |
| `read_file` | `<ws>/guides/pretense.md` | **ALLOW** | Allow as-is (already inside workspace). |
| `read_file` | `/Users/.../cleanroom/foo.py` | **DENY** | Error: Reading files outside workspace prohibited. |
| `write_file` | `.../scratch/temp.py` | **DENY** | Error: Scratch file authoring prohibited. |
| `edit_file` | `parts/.../lib/foo.py` | **ALLOW** | Overwrite: `{"Path": "<ws>/parts/.../lib/foo.py"}` |

---

## 9. Radically Simplified Subagent Prompting

With the physical boundary enforced by `gate.py`, the bloated 300-word prompt anti-pattern is completely eliminated.

### The Canonical 5-Line Hermetic Worker Prompt:
```
You are an autonomous Autofab '<role>' worker.
Your assigned workspace is '<workspace_dir>'. All commands and file paths execute strictly relative to your workspace root.
1. Run 'bin/get_work' to acquire pending targets.
2. Read companion guides in 'guides/' and author changes directly in place.
3. Verify with 'bin/check_files <target>'.
4. Submit with 'bin/submit <target> "<summary>"' (or 'bin/blame', or 'bin/fail' on impasse).
All detailed rules and contracts are defined in your workspace AGENTS.md.
```

---

## 10. Monorepo Part Structure & Telemetry

### Monorepo Components
- **`autofab/parts/antigravity/`**:
  - `antigravity_coordinator_impl.py`: Coordinator lifecycle, queue management, and handoff protocols.
  - `antigravity_harness_impl.py`: Subagent process launcher, directive emission, and desktop IPC (`agentapi`) integration.
  - `antigravity_asm.py`: Assembly bindings linking `antigravity` into the top-level systems harness.
- **`.agents/plugins/autofab/`**:
  - `plugin.json`: Workspace plugin manifest.
  - `hooks.json` & `hooks/gate.py`: PreToolUse hook intercepting tool calls for hermetic rooting.
  - `rules/AGENTS.md`: Workspace boundary invariants and tool constraints.
  - `agents/`: Markdown subagent specifications for `autofab_coordinator`, `autofab_worker`, and `autofab_baseline_worker`.

### Empirical Benchmark Telemetry
Live benchmark flights using the Antigravity subagent harness demonstrate high convergence and zero defect escape:
- **`gemini-3.8-flash` on `ring_buffer` (Standard)**: PASS (16P / 0F, 0 pyright errors, $0.1382).
- **`gemini-3.8-flash` on `task_queue` (Pretense Baseline)**: PASS (57P / 0F, 0 errors, 266.4s, $0.1972).
- **`gemini-3.8-flash` on `semver_solver` (Combined Net)**: PASS (60P / 0F, 0 errors, 1135.0s, $0.7487).
