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

### Step 2.2: Dispatch Worker (Warm Revival or Clean Spawn)
The coordinator maintains a warm worker pool indexed by role:
`warm_workers: dict[str, dict(conv_id: str, session_id: str, role: str, units: set[str], completed_at: float)]`.

For an incoming batch with `ready_role` and `incoming_units = set(item["unit"] for item in batch)`:
1. **Check Warm Pool**: If `ready_role` in `warm_workers`:
   - Compute `overlap = warm_workers[ready_role]["units"].intersection(incoming_units)`.
   - If `len(overlap) > 0` and within 600s:
     **REVIVE WARM WORKER**: Send `send_message` with task details and updated batch. Augment `units.update(incoming_units)`.
   - Else (`len(overlap) == 0` or expired):
     **ZERO OVERLAP ENFORCEMENT**: Deregister old session (`cleanroom_mcp_client.py --session <id> deregister`), terminate old subagent (`manage_subagents(kill)`), and delete from `warm_workers`. Proceed to spawn a fresh worker.
2. **Spawn Fresh Worker**: If no matching warm worker:
   - Generate unique session ID `s_<worker_seq>`.
   - Formulate role worker prompt and call `invoke_subagent`.

### Step 2.3: Worker Completion & Size Check
Upon receiving the worker's completion report (`status: complete`):
1. Silently check worker context token size:
   ```bash
   python3 update_with_ai/support/lib/antigravity_token_stats.py --conv-id <worker_conv_id> --check-cap 100000
   ```
   - If output is `EXCEEDED_CAP`: Context has exceeded 100k tokens. Terminate the worker (`manage_subagents(kill)`), deregister its session (`cleanroom_mcp_client.py --session <id> deregister`), and do not retain in `warm_workers`.
   - Else (silent exit 0): Record/update `warm_workers[ready_role] = {conv_id, session_id, role, units: incoming_units, completed_at: now}`.

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
