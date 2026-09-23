# Antigravity Cleanroom Architecture & Coordinator Design

## 1. System Overview

Cleanroom coordinates multi-agent DAG convergence across specification, implementation, test, and verification roles. The system is architected around a strict separation of concerns between **deterministic Python code** (which owns all scheduling, state, and graph transitions) and a **zero-agency Coordinator Subagent** (which acts solely as a host adapter in the Antigravity environment).

```
   ┌────────────────────────────────────────────────────────┐
   │                  Main Chat / User                      │
   └──────────────────────────┬─────────────────────────────┘
                              │ invoke_subagent
                              ▼
   ┌────────────────────────────────────────────────────────┐
   │       Cleanroom Coordinator Subagent (Zero-Agency)      │
   │   - Pure Antigravity adapter; no scheduling logic      │
   │   - Calls Python step command, executes returned plan  │
   │   - Sleeps until awakened by worker messages           │
   └───────────▲─────────────────────────────┬──────────────┘
               │ wakeup message              │ invoke_subagent / send_message
               │ (status: complete/failed)   │
   ┌───────────┴─────────────────────────────▼──────────────┐
   │            Role Workers (cleanroom_role_worker)        │
   │   - Inspect grounding specs (.pyi) and role guides     │
   │   - Edit files via replace_file_content / write_to_file│
   │   - Run check-files, then call submit or fail          │
   └──────────────────────────┬─────────────────────────────┘
                              │
                              ▼ submit / fail
   ┌────────────────────────────────────────────────────────┐
   │        Cleanroom DAG Engine & FastMCP Server           │
   │   - Direct mutation of DAG node states (clean/dirty)   │
   │   - Tracks worker states (busy vs idle) & failure counts│
   │   - Deterministic topological wave scheduling          │
   └────────────────────────────────────────────────────────┘
```

---

## 2. Core Architectural Principles

### A. Zero Coordinator Agency
- The `cleanroom_coordinator` subagent has **no agency, no heuristics, no scheduling logic, and no troubleshooting capabilities**.
- It is purely a **dumb host bridge** connecting Antigravity's host environment (which manages subagent lifecycles and messaging) to the deterministic Cleanroom Python engine.
- It only performs actions that Python running in an Antigravity shell subprocess cannot do directly:
  1. Receive asynchronous wakeup messages from Antigravity subagents.
  2. Invoke host primitives (`invoke_subagent`, `send_message`, `manage_subagents(kill)`).
  3. Relay host-assigned conversation IDs back to Python (`register-spawned`).
- The Coordinator Subagent is structurally prohibited from editing files and cannot run arbitrary shell inspection commands (enforced by `AntigravitySandboxGate`).

### B. Workers Directly Mutate DAG & Engine State
- The role worker (`cleanroom_role_worker`) is the only entity that performs work on files.
- When verification passes and the worker commits changes via `submit`:
  - The Cleanroom FastMCP server records the target unit as clean.
  - The worker's session status directly transitions from `busy` to `idle` in the engine state.
- When an unresolvable error occurs and the worker invokes `fail`:
  - The worker's session status transitions from `busy` to `idle`.
  - The engine increments the failure count for that unit (aborting convergence if retries exceed 1).
- Once idle, the worker sends a single 1-line wakeup message (`status: complete` or `status: failed: <reason>`) to the coordinator subagent and concludes its turn.

### C. Deterministic Python Engine (Single Source of Truth)
- The Python coordinator engine (`antigravity_coordinator_impl`) computes the entire DAG convergence plan deterministically:
  - **In-flight Tracking (`busy` vs `idle`)**: Any worker currently running a batch is `busy`. A `busy` worker is **never** revived and **never** assigned additional work.
  - **Warm Pool Scheduling**: When a worker becomes `idle`, if its assigned units overlap with newly ready units in the DAG and it meets the TTL / token retention limits, Python marks it to be revived.
  - **Pruning & Garbage Collection**: Workers that exceed context token caps ($> 100\text{k}$) or idle thresholds ($> 10$ minutes) are flagged for termination (`kill`).
  - **Convergence Resolution**: When no dirty nodes remain, Python issues `is_complete: true`, instructs the coordinator to kill all remaining workers, and shuts down the server.

---

## 3. The Coordinator Interaction Protocol

The coordinator subagent runs a strictly reactive, passive loop:

```
[Wakeup] (Initial invocation OR incoming worker message)
   │
   ▼
[Step 1] Execute Engine Step
   Command: python3 -m update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl step "<target>"
   │
   ▼
[Step 2] Parse JSON Action Plan
   Plan schema: { is_complete: bool, kill: [...], spawns: [...], revives: [...], summary: str }
   │
   ├─► If summary indicates DAG aborted: Report error to user and STOP.
   │
   ├─► If is_complete == true:
   │      Run telemetry: python3 -m update_with_ai.parts.antigravity.lib.antigravity_telemetry_impl --format markdown
   │      Report completion to user and STOP.
   │
   └─► If active work remains:
          1. Execute kills: manage_subagents(Action="kill", ConversationIds=kill_list)
          2. Execute spawns: invoke_subagent(Subagents=spawns_list)
             - For each new conversation ID:
               python3 -m update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl register-spawned --mapping <conv_id> <session_id>
          3. Execute revives: send_message(Recipient=r, Message=m)
   │
   ▼
[Step 3] Sleep / Yield
   Coordinator calls NO MORE TOOLS and immediately concludes its turn.
   Antigravity resumes the coordinator ONLY when a worker sends an incoming message.
```

---

## 4. Role Worker Protocol

1. **Register**: Bind session, role, and unit via `antigravity_mcp_client_impl register`.
2. **Get Work**: Retrieve instructions and feedback via `antigravity_mcp_client_impl get-work`.
3. **Execute**: Read specs, edit files, verify via `antigravity_mcp_client_impl check-files`.
4. **Complete or Fail**:
   - If verification succeeds:
     - Run `antigravity_mcp_client_impl submit --target <path> --change-summary "<summary>"`.
     - Send `status: complete` to coordinator via `send_message`.
     - End turn immediately (do NOT call `get-work` again).
   - If verification fails and cannot be fixed:
     - Run `antigravity_mcp_client_impl fail --explanation "<reason>"`.
     - Send `status: failed: <reason>` to coordinator via `send_message`.
     - End turn immediately.

---

## 5. Invariants & Safety Enforcements

1. **Zero Hallucination / No `--completed-worker` Relay**:
   The coordinator agent never tells the engine whether a worker is complete. The worker reports its own status directly when calling `submit` or `fail`.
2. **Zero Live-Troubleshooting**:
   The coordinator agent has no file editing tools and cannot run bash inspection commands. If the engine reports an error, it stops immediately.
3. **Single-Retry Circuit Breaker**:
   If any unit fails twice, convergence is aborted immediately and all workers are killed.
4. **Clean State on Fresh Run**:
   Starting a new target run resets stale worker pool mappings so dead sessions never pollute new executions.
