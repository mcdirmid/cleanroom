# Antigravity Subagent Workspace Rooting, Lifecycle Hooks & Hermetic Isolation

> **Document Type:** Canonical Architectural Specification & System Guide  
> **Status:** Proposal & Comprehensive Design Specification  
> **Scope:** Google Antigravity Subagent Runtime, Lifecycle Hooks (`PreToolUse`), Role Workspace Rooting, Transparent Command Rewriting (`overwrite`), Path Boundary Enforcement, and Worker Prompt Simplification.

---

## 1. Executive Summary & Core Architectural Problem

Autofab enforces a strict **Cleanroom methodology**: every development role (`lib`, `test`, `qa`, `coverage`, `pretense`, etc.) executes in a completely isolated, ephemeral role workspace provisioned outside the canonical monorepo:
```
/Users/seanmcdirmid/projects/autofab_role_workspaces/<role>_<scope>/
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
This defensive prompting causes catastrophic friction:
- **Cognitive Overload**: Weaker models (`gemini-flash`, `qwen-moe`) struggle to maintain dual-context spatial awareness (the host repo vs the role workspace).
- **Prompt Confusion & Hallucinations**: Models attempt to reverse-engineer paths, wander into the parent repository, or get derailed by platform suggestions (e.g. writing into platform `scratch/` folders).
- **Inconsistent Tool Usage**: Agents forget the `cd` prefix on subsequent turns, running `bin/get_work` in `cleanroom/` where the binary does not exist, triggering confusion loops.

---

## 2. Core Vision: The Hermetic Root Invariant

Instead of relying on fragile prompt engineering to beg the model to navigate directories, **the Antigravity Lifecycle Hook System (`PreToolUse`) enforces a strict, physical Root Invariant**:

> **The Hermetic Root Invariant**:
> For any Autofab role worker subagent, its assigned role workspace directory (`<workspace_dir>`) is its **sole, immutable universe**.
> 1. Every shell command (`run_command`) is automatically anchored to execute with working directory `<workspace_dir>`.
> 2. Direct directory navigation (`cd`) to external directories or subdirectories is strictly prohibited.
> 3. All file operations (`read_file`, `write_file`, `edit_file`) are strictly scoped within `<workspace_dir>`. Relative paths are automatically resolved against `<workspace_dir>`, and out-of-bounds absolute paths are hard-denied.

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
│      - STRICTLY CONSTRAINED: Can ONLY launch/message subagents and run sanctioned queue CLIs    │
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

---

## 3. Detailed Component Architecture

### 3.1 Session Identification & Active Worker Registry

To enforce this three-tier model without fragile global interceptors, `gate.py` classifies each tool call into one of three execution contexts:

1. **Conversational Chat (Root User Session)**:
   - Identified when the conversation has not been registered as an Autofab worker and its initial context does not match coordinator or worker subagent dispatch signatures.
   - **Hook Action**: Immediately `allow()` without inspecting commands, file paths, or arguments. The developer and their primary chat assistant are completely unbound.
2. **Coordinator Subagent (`autofab_coordinator`)**:
   - Identified via `conversationId` registration or prompt signature matching `Zero-Execution Autofab Coordinator` / `autofab_coordinator`.
   - **Hook Action**: Strictly constrained. Denies all file modification tools (`write_file`, `edit_file`, etc.). Constrains `run_command` exclusively to sanctioned `uv run autofab` subcommands (`work-queue`, `verify-fused`, `harvest-fused`, `decommission`). All other commands (including `git`, `cat`, exploratory probes) are hard-denied.
3. **Role Worker Subagents (`autofab_worker`, etc.)**:
   - Identified via `active_workers.json` lookup or fallback extraction of `workspace_dir` from the subagent prompt / `lastUserInput`.
   - **Hook Action**: Enforces the Hermetic Root Invariant (auto-rooting, relative path resolution, hard prohibition on `git`, `unzip`, probe scripts, internal `cd`, and workspace escapes).

### 3.2 Coordinator Constraints & Enforced Zero-Code Custody

The `autofab_coordinator` subagent's sole purpose is driving the DAG state machine. To guarantee that the coordinator does not hijack worker responsibilities:

1. **Subagent Orchestration Tools**: Fully enabled (`invoke_subagent`, `send_message`, `manage_subagents`, `define_subagent`).
2. **Command Whitelist**: `run_command` is strictly restricted to matching:
   ```regex
   ^\s*uv\s+run\s+autofab\s+(?:work-queue|verify-fused|harvest-fused|decommission)\b
   ```
   Any other shell invocation (e.g. `git`, `cat`, `python`, `find`, `pytest`) is rejected with:
   > *"STRICT POLICY VIOLATION: The Autofab Coordinator subagent is strictly constrained to orchestrating subagents and may only execute 'uv run autofab' queue/lifecycle commands."*
3. **Zero File Custody**: Any call to `write_file`, `edit_file`, or content replacement tools is rejected with:
   > *"STRICT POLICY VIOLATION: The Autofab Coordinator subagent has zero code custody and cannot author or edit files."*

### 3.3 Worker `run_command` Gating, `cd` Prohibition & Auto-Rooting

When a `run_command` tool call is intercepted by `gate.py`:

1. **Worker Identification & Early Exemption**:
   - Look up `data["conversationId"]` in `active_workers.json` (or fallback via `lastUserInput`).
   - **If not a worker subagent (`ws_dir is None`)**: Immediately allow execution. Interactive parent sessions and DAG coordinators remain unconstrained in the canonical repository (`cleanroom/`), retaining full capability to perform standard Git workflows (`git status`, `git add`, `git commit`, `git push`), build scripts, and general tooling.
2. **Prohibit Git & Unzip for Worker Subagents**:
   - Direct `git` commands and inspection of `.git/` directories are prohibited for role workers to prevent lock contention, dirty working trees, untracked collisions, and confusion between isolated role workspaces and the host repository.
   - Unzipping runner binaries or inspecting internal tool archives is prohibited.
3. **Prohibit Inline Testing & Probe Scripts for Worker Subagents**:
   - Role workers are strictly prohibited from executing ad-hoc Python probes, inline scripts (`python -c`), test runners (`pytest`), or typecheckers directly. Target verification relies exclusively on `bin/check_files <target>`.
4. **Prohibit Internal `cd` Navigation**:
   - In Cleanroom workspaces, all binaries (`bin/get_work`, `bin/check_files`, `bin/submit`, etc.) and paths are strictly designed to execute with `cwd == <workspace_dir>`.
   - An agent should **never** run `cd guides`, `cd bin`, `cd parts`, `cd ..`, or `cd /`. Doing so causes relative path breakage across compound commands.
   - **Enforcement Rule**: If the command contains `\bcd\b` (word boundary check) and the target is anything other than `<workspace_dir>`:
     - **Decision: `deny`**
     - **Reason**: 
       > *"STRICT BOUNDARY VIOLATION: Subagents are permanently rooted in their workspace directory ('<workspace_dir>'). Changing directories (cd) into subdirectories (e.g. guides/) or external paths is strictly prohibited. Run all tools (bin/get_work, bin/check_files, bin/submit) directly from the workspace root."*
5. **Prohibit Host Contamination in Arguments**:
   - If the command string contains absolute path references to the host repository (e.g. `/projects/cleanroom/`):
     - **Decision: `deny`**
     - **Reason**:
       > *"STRICT BOUNDARY VIOLATION: Referencing host repository paths outside your role workspace is strictly prohibited. Operate strictly within '<workspace_dir>'."*
6. **Transparent Auto-Rooting via `overwrite`**:
   - If the command does *not* already begin with `cd <workspace_dir> && `:
     ```python
     new_cmd = f"cd {workspace_dir} && ({original_cmd})"
     return {
         "decision": "allow",
         "overwrite": {
             "CommandLine": new_cmd
         }
     }
     ```
   - When Antigravity executes the tool, it executes inside `<workspace_dir>`, and Antigravity informs the agent that the command was anchored to its workspace root.

### 3.3 File Tools Interception (`read_file`, `write_file`, `edit_file`)

When `read_file`, `write_file`, or `edit_file` is called by a registered worker:

1. **Extract Target Path**: Extract `Path` from `args`.
2. **Prohibit Scratch Directories**:
   - If `"/scratch/"` in `path` or `path.endswith("/scratch")`:
     - **Decision: `deny`**
     - **Reason**: *"STRICT POLICY VIOLATION: Authoring files in scratch/ directories is strictly prohibited. Author assigned target files directly in place within your workspace."*
3. **Relative Path Auto-Rooting**:
   - If `not os.path.isabs(path)`:
     - Automatically resolve: `abs_path = os.path.normpath(os.path.join(workspace_dir, path))`
     - Check: Does `abs_path.startswith(workspace_dir + os.sep)`?
       - If YES:
         - **Decision: `allow`**
         - **Overwrite**: `{"Path": abs_path}`
       - If NO (path traversal via `../../...` escaped the workspace):
         - **Decision: `deny`**
         - **Reason**: f"STRICT BOUNDARY VIOLATION: Path traversal '{path}' escapes assigned workspace."
4. **Absolute Path Boundary Enforcement**:
   - If `os.path.isabs(path)`:
     - Canonicalize with `os.path.realpath(os.path.normpath(path))`.
     - Check: Does `canonical_path.startswith(canonical_workspace_dir)`?
       - **YES**: Allow as-is.
       - **NO**: 
         - **Decision: `deny`**
         - **Reason**: 
           > *"STRICT BOUNDARY VIOLATION: Access to path '{path}' is strictly prohibited. You are confined exclusively to your assigned role workspace: '{workspace_dir}'."*

---

## 4. Complete Edge Case & Hazard Analysis

| Hazard / Edge Case | Risk Level | Failure Mechanism | Deterministic Hook Mitigation |
| :--- | :--- | :--- | :--- |
| **Subdirectory `cd` (`cd guides`)** | HIGH | Agent runs `cd guides && cat spec.md`. Subshell changes working directory, breaking subsequent commands. | Match `\bcd\s+` across shell operators. Hard-deny any `cd` other than `cd <workspace_dir>`. |
| **Path Traversal (`..`)** | HIGH | Agent passes `read_file("../../cleanroom/parts/...")` or `../other_ws/`. | Compute `os.path.realpath(os.path.normpath(...))`. Verify `resolved.startswith(workspace_dir + os.sep)`. Hard-deny escapes. |
| **Absolute Path Redundancy** | MEDIUM | Agent passes full path `/Users/.../ws/guides/spec.md`. Blindly prefixing `ws` yields `/Users/.../ws/Users/.../ws/...`. | Check `os.path.isabs(path)`. If absolute and inside `<ws>`, allow as-is without re-prefixing. |
| **Host Contamination in CLI** | HIGH | Agent runs `cat /Users/.../cleanroom/parts/foo/lib/foo.py` or `python3 /cleanroom/...`. | Regex-scan CLI arguments for canonical host repo paths (`/cleanroom/`). Hard-deny external path arguments. |
| **Dispatch Race Condition** | MEDIUM | Worker executes tool 1 before coordinator finishes writing `active_workers.json`. | Parse `workspace_dir` from hook payload's `lastUserInput` and self-register on the fly. |
| **Coordinator Interference** | CRITICAL | Hook accidentally constrains the coordinator or interactive session to an isolated role workspace. | Coordinator / interactive `conversationId` is strictly excluded from `active_workers.json`. Non-workers remain unconstrained in `cleanroom/`. |
| **Worker vs Global Rule Conflation** | CRITICAL | Placing role worker constraints (`git`, `unzip`, ad-hoc probe scripts) in global hook scope blocks developer workflows. | Gated strictly behind `ws_dir is not None`. Only universal filesystem rules (e.g. `/scratch/` prohibition) run globally. |
| **Pre-existing `cd <ws>` Prefix** | LOW | Prompt or legacy script already includes `cd <ws> &&`. Prepending creates nested `cd <ws> && cd <ws> && ...`. | Strip or recognize matching prefix before applying auto-rooting wrapper. |
| **Symlink Escapes** | MEDIUM | Workspace contains symlinks pointing back to canonical monorepo. | Apply `os.path.realpath` boundary checks against canonical root targets. |

---

## 5. Decision Matrix

### 5.1 Conversational Chat (Interactive Root Session)

The conversational chat represents direct developer interaction and is **completely unconstrained**:

| Tool Call | Path / Command Form | Hook Decision | Hook Action / Overwrite |
| :--- | :--- | :--- | :--- |
| `run_command` | `git status`, `git commit`, `git push` | **ALLOW** | Execute normally in host repository. |
| `run_command` | `bin/test`, `uv run ...`, `pytest` | **ALLOW** | Execute normally in host repository. |
| `read_file` / `edit_file` / `write_file` | Any path across monorepo / filesystem | **ALLOW** | Execute normally in host repository. |
| Any Tool | Any invocation | **ALLOW** | Completely exempt from Autofab lifecycle gates. |

### 5.2 Coordinator Subagent (`autofab_coordinator`)

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

### 5.3 Role Worker Subagents (`ws_dir is set`)

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

## 6. Radically Simplified Subagent Prompting

With the physical boundary enforced by `gate.py`, the bloated 300-word prompt anti-pattern is completely eliminated.

### The New Hermetic Prompt:
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

## 7. Phased Implementation Roadmap (Deferred until Explicit Approval)

1. **Phase 1: Worker Registry & Auto-Discovery (`active_workers.json`)**
   - Implement coordinator registration in `subagent_coordinator_impl.py` and `autofab_role_tool.py`.
   - Add prompt-based fallback extraction in `gate.py` from `lastUserInput`.
2. **Phase 2: Hook Upgrade (`gate.py` & `hooks.json`)**
   - Implement `cd` prohibition and `cd <ws> && (<cmd>)` auto-rooting.
   - Implement relative path resolution and boundary checks for `read_file`, `write_file`, and `edit_file`.
   - Update `hooks.json` matcher to `run_command|read_file|write_file|edit_file`.
3. **Phase 3: Prompt Streamlining**
   - Update coordinator prompt templates in `autofab_role_tool.py` to the concise 5-line Hermetic Prompt.
4. **Phase 4: Comprehensive Test Suite**
   - Unit tests covering all rows in the Decision Matrix.
   - Verification across multiple models (`gemini-flash`, `deepseek-flash`, `qwen-moe`).
