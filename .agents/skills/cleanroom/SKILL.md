---
name: cleanroom
description: >-
  Cleans and coordinates Cleanroom software construction workflows across specification, implementation,
  and test roles. Use this skill when the user asks to '/cleanroom clean', '/cleanroom change',
  or to run Cleanroom role subagents to update or verify DAG nodes.
---

# Cleanroom Orchestration Skill

This skill orchestrates Cleanroom software construction workflows using a **Hierarchical Coordinator-Worker Architecture (Option A)**. In Cleanroom, nodes in the DAG transition from `dirty` to `clean` through specification, implementation, test, and verification.

---

## Strict Three-Tier Architecture

To completely eliminate Main Chat context contamination and role drift:

1. **Tier 1: Main Chat (User Interface & Supervisor)**:
   - Receives `/cleanroom clean` or `/cleanroom change` from the user.
   - Spawns the **Cleanroom Coordinator** subagent (`cleanroom_coordinator`) via `invoke_subagent`.
   - Never runs internal wave loops, never calls `antigravity_mcp_client`, and never edits code files.
   - Awaits completion from the Coordinator.
   - Runs `python3 -m update_with_ai.parts.antigravity.lib.antigravity_telemetry_impl --format markdown` to extract prompt-cache hit rates and dollar cost savings.
   - Presents the final convergence summary along with the Token & Cost Telemetry table to the user.

2. **Tier 2: Cleanroom Coordinator (`cleanroom_coordinator`)**:
   - Executes deterministically via `python3 -m update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl step "<target>"`.
   - Manages a **Tiered Warm Worker Pool with Unit Overlap & Idle Pruning**:
     - Worker $< 5$ minutes old: reusable if context $< 200\text{k}$ tokens.
     - Worker $5$–$10$ minutes old: reusable if context $< 100\text{k}$ tokens.
     - Pruned if idle $> 10$ minutes, or $> 100\text{k}$ tokens and idle $> 5$ minutes.
     - Multiple workers per role can exist concurrently; non-overlapping workers are preserved warm rather than killed immediately.
     - Large batches ($> 10$ units) are partitioned into parallel workers.
   - Upon full DAG convergence (`is_complete: true`), kills all workers, deregisters sessions, and shuts down the MCP server.
   - Structurally constrained: has NO file editing tools.

3. **Tier 3: Role Workers (`cleanroom_role_worker`)**:
   - Executes for a specific role batch (`lib`, `test`, `qa`, etc.).
   - Inspects grounding specs in large contiguous blocks (avoiding 50-line micro-slicing), applies edits via `replace_file_content` or `write_to_file`.
   - Verifies and submits via `python3 -m update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl`.
   - Concludes turn immediately upon batch submission (does not call `get-work` a second time). If revived within retention limits for overlapping units, calls `get-work` to receive fresh feedback and applies targeted fixes in warm context.

---

## Commands & Workflows

### 1. `/cleanroom clean <target>` or `/cleanroom clean <role-address> <unit-address>`

Cleans a target node and all its transitive dependencies until verified clean.

#### Supported Syntaxes:
- **Shortcut Form**: `/cleanroom clean //testing/parts/sandbox:sandbox_asm_qa`
- **Two-Argument Form**: `/cleanroom clean //update_python_with_ai:qa //testing/parts/sandbox:sandbox_asm`

#### Main Chat Execution Procedure:
1. **Launch Coordinator Subagent**:
   Call `invoke_subagent`:
   ```python
   invoke_subagent(
       Subagents=[
           {
               "TypeName": "cleanroom_coordinator",
               "Role": "Cleanroom Coordinator",
               "Model": "flash",
               "Prompt": (
                   f"Orchestrate cleanroom convergence for target '{target}'.\n"
                   f"Execute the deterministic engine loop:\n"
                   f"1. Run 'python3 -m update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl step \"{target}\" --reset'\n"
                   f"2. Execute returned kill, spawns, and revives actions.\n"
                   f"3. Register newly spawned workers with 'register-spawned'.\n"
                   f"4. Sleep (call zero tools) until awakened by an incoming worker message, then repeat step 1 (without --reset) until complete.\n"
                   f"5. Output final telemetry and report completion."
               )
           }
       ]
   )
   ```
2. **Await Completion**:
   Stop calling tools and await the completion message from the coordinator subagent.
3. **Extract Telemetry & Teardown Coordinator**:
   - Extract prompt-cache hit rates and dollar cost metrics:
     ```bash
     python3 -m update_with_ai.parts.antigravity.lib.antigravity_telemetry_impl --format markdown
     ```
   - Terminate the coordinator subagent: `manage_subagents(Action="kill", ConversationIds=[coordinator_id])`.
   - Present the final completion report to the user, including the full Token & Cost Telemetry table.

---

### 2. `/cleanroom change <target> "<message>"`

Injects an intentional change into a DAG node, marking it and all its downstream dependents dirty.

**Execution**:
```bash
python3 update_with_ai/support/lib/cleanroom_dag_cli.py inject-change <target> "<message>"
```
Once injected, proceed with `/cleanroom clean <target>` via the Coordinator subagent.
