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
   - Awaits completion from the Coordinator.
   - Runs `python3 update_with_ai/support/lib/antigravity_token_stats.py --coordinator <coordinator_id> --format markdown` to extract prompt-cache hit rates and dollar cost savings.
   - Presents the final convergence summary along with the Token & Cost Telemetry table to the user.

2. **Tier 2: Cleanroom Coordinator (`cleanroom_coordinator`)**:
   - Manages the FastMCP server and queries `cleanroom_mcp_client.py next-batch` via the running MCP server (preserving `batch_size` configuration).
   - Manages an active **10-Minute Warm Worker Pool**: retains idle role workers for up to 10 minutes after batch completion. If a subsequent wave targets that same `(role, unit)` within 10 minutes (due to QA contract blame or change propagation), the Coordinator revives the existing worker subagent via `send_message` rather than spawning a cold worker, preserving warm KV cache and context.
   - When the 10-minute TTL expires without activity, or upon full DAG convergence (`is_complete: true`), kills warm workers via `manage_subagents(kill)` and deregisters their sessions.
   - Structurally constrained: has NO file editing tools (`replace_file_content` and `write_to_file` are omitted).

3. **Tier 3: Role Workers (`cleanroom_role_worker`)**:
   - Executes for a specific role batch (`lib`, `test`, `qa`, etc.).
   - Inspects grounding specs in large contiguous blocks (avoiding 50-line micro-slicing), applies edits via `replace_file_content` or `write_to_file`.
   - Verifies and submits via `python3 update_with_ai/support/lib/cleanroom_mcp_client.py`.
   - Concludes turn immediately upon batch submission (does not call `get-work` a second time). If revived within 10 minutes, calls `get-work` to receive fresh feedback and applies targeted fixes in warm context.

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
                   f"Maintain a 10-minute warm worker pool: when a worker finishes, retain it idle. If a subsequent wave targets the same (role, unit) within 10 minutes (via blame or changes), revive the subagent via send_message to call get-work rather than spawning a new subagent.\n"
                   f"Ensure role workers macro-batch files and avoid micro-slicing.\n"
                   f"When the subgraph is clean, terminate all workers, deregister sessions, shut down the server, extract run token telemetry with antigravity_token_stats.py, and send a completion report back to the main chat."
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
     python3 update_with_ai/support/lib/antigravity_token_stats.py --coordinator <coordinator_id> --format markdown
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
