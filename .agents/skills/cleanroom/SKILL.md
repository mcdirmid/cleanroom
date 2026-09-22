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
   - Never runs internal wave loops, never calls `cleanroom_mcp_client.py`, and never edits code files.
   - Awaits completion from the Coordinator and presents the final convergence summary to the user.

2. **Tier 2: Cleanroom Coordinator (`cleanroom_coordinator`)**:
   - Manages the FastMCP server and queries `cleanroom_mcp_client.py next-batch` via the running MCP server (preserving `batch_size` configuration).
   - Spawns ephemeral **Role Workers** (`cleanroom_role_worker`) for each wave batch.
   - Kills completed workers via `manage_subagents(kill)` to discard intermediate transcripts.
   - Repeats until `is_complete: true`, shuts down the server, and reports to the Main Chat.
   - Structurally constrained: has NO file editing tools (`replace_file_content` and `write_to_file` are omitted).

3. **Tier 3: Ephemeral Role Workers (`cleanroom_role_worker`)**:
   - Spawns with fresh 0-token baseline transcripts for a specific role batch (`lib`, `test`, `qa`, etc.).
   - Inspects grounding specs, applies edits via `replace_file_content` or `write_to_file`.
   - Verifies and submits via `python3 update_with_ai/support/lib/cleanroom_mcp_client.py`.
   - Concludes turn immediately upon batch submission. Context is discarded on termination.

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
               "Prompt": (
                   f"Orchestrate cleanroom convergence for target '{target}'.\n"
                   f"Run the topological wave loop using cleanroom_mcp_client.py next-batch (via the running FastMCP server) until is_complete: true.\n"
                   f"Spawn ephemeral cleanroom_role_worker subagents for each wave batch and kill them upon completion.\n"
                   f"Ensure role workers (especially lib) macro-batch and process all assigned files in each batch together, not one file at a time.\n"
                   f"When the subgraph is clean, shut down the server and send a completion report back to the main chat."
               )
           }
       ]
   )
   ```
2. **Await Completion**:
   Stop calling tools and await the completion message from the coordinator subagent.
3. **Teardown Coordinator & Report**:
   - Terminate the coordinator subagent: `manage_subagents(Action="kill", ConversationIds=[coordinator_id])`.
   - Present the final completion report to the user.

---

### 2. `/cleanroom change <target> "<message>"`

Injects an intentional change into a DAG node, marking it and all its downstream dependents dirty.

**Execution**:
```bash
python3 update_with_ai/support/lib/cleanroom_dag_cli.py inject-change <target> "<message>"
```
Once injected, proceed with `/cleanroom clean <target>` via the Coordinator subagent.
