# Cleanroom Coordinator Runbook

This document is the operational procedure for the Cleanroom Coordinator (`cleanroom_orchestrator`).

## 1. FastMCP Server Liveness
Check if `.mcp.active` exists. If absent, launch the server in the background:
```bash
python3 update_with_ai/parts/systems/lib/cleanroom_mcp_runner_impl.py --transport sse --port 8765 --batch-size 10
```

## 2. Topological Wave Dispatch Loop
Repeat the following loop until `is_complete: true`:

### Step 2.1: Query Next Batch
```bash
python3 update_with_ai/support/lib/cleanroom_dag_cli.py next-batch <target> [--batch-size <N>]
```
- If `"is_complete": true`: Exit loop and proceed to **3. Teardown**.
- If `"batch"` is non-empty: Record `ready_role` and the batch units.
- **Batch Sizing**: Default is inherited from the server (e.g. 10). For single-target / small-model mode, use `--batch-size 1`.

### Step 2.2: Spawn Ephemeral Role Worker
Generate a unique session ID for the worker (e.g. `s_<uuid_short>` or `s_<counter>`) to guarantee session isolation and avoid stale session state.

Call `invoke_subagent`:
```json
{
  "TypeName": "cleanroom_role_worker",
  "Role": "<ready_role_name> Worker",
  "Prompt": "You are the Cleanroom role worker for role '<ready_role>' at unit '<root_unit>'.\nYour assigned session ID is '<session_id>'.\nYour assigned batch is: <batch_units>.\n\nExecution procedure:\n1. Register session:\n   python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session <session_id> register --role \"<ready_role>\" --unit \"<root_unit>\"\n2. Retrieve task prompt:\n   python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session <session_id> get-work\n   - If get-work returns 'No dirty nodes are ready for cleaning' or an error, report it and end turn immediately.\n3. Execute assigned files in batch:\n   - Inspect grounding specs (.pyi) and role guide (.md).\n   - Apply edits via replace_file_content or write_to_file across all files in cohesive passes.\n   - Verify:\n     python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session <session_id> check-files\n   - Submit verified targets in topological dependency order (dependencies first):\n     python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session <session_id> submit --target <path> --change-summary \"<summary>\"\n   - Blame upstream defect if contracts fail:\n     python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session <session_id> blame --target <path> --blame-target <dep> --explanation \"<reason>\"\n4. When batch is complete:\n   Send 1-line completion report to coordinator via send_message ('status: complete') and finish turn immediately."
}
```

### Step 2.3: Teardown Worker & Deregister Session
Upon receiving the worker's completion report:
1. Deregister the worker's session from the server:
   ```bash
   python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session <session_id> deregister
   ```
2. Kill the ephemeral worker to free context:
   ```python
   manage_subagents(Action="kill", ConversationIds=[worker_conv_id])
   ```

## 3. Teardown & Final Convergence Report
1. Verify final status:
   ```bash
   python3 update_with_ai/support/lib/cleanroom_dag_cli.py status <target>
   ```
2. Shut down the FastMCP server:
   ```bash
   python3 update_with_ai/support/lib/cleanroom_mcp_client.py shutdown
   ```
3. Report final convergence summary to parent agent.
