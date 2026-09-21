---
name: cleanroom
description: >-
  Cleans and coordinates Cleanroom software construction workflows across specification, implementation,
  and test roles. Use this skill when the user asks to '/cleanroom clean', '/cleanroom change',
  or to run Cleanroom role subagents to update or verify DAG nodes.
---

# Cleanroom Orchestration Skill

This skill orchestrates Cleanroom software construction workflows directly from the Main Chat as Coordinator. In Cleanroom, nodes in the DAG transition from `dirty` to `clean` through specification, implementation, test, and verification. The skill resolves role dependencies, manages the Cleanroom FastMCP server, launches role subagent fleets with staged idling, and coordinates DAG convergence until all nodes in the target subgraph are clean.

---

## Commands & Workflows

### 1. `/cleanroom clean <target>` or `/cleanroom clean <role-address> <unit-address>`

Cleans a target node and all its transitive dependencies until verified clean.

#### Supported Syntaxes:

**A. Shortcut Form (`define_node` target)**:
Specify a single `define_node` target shortcut. The tool automatically decomposes the target into its constituent unit and role:
```
/cleanroom clean //testing/parts/sandbox:sandbox_asm_qa
```
*(Automatically resolves to unit `//testing/parts/sandbox:sandbox_asm` and role `//update_python_with_ai:qa`).*

**B. Canonical Two-Argument Form**:
Specify the role address and unit address explicitly:
```
/cleanroom clean //update_python_with_ai:qa //testing/parts/sandbox:sandbox_asm
```
*(Accepts convenience labels such as `qa`, `:qa`, or full Bazel target `//update_python_with_ai:qa`).*

#### Step-by-Step Procedure:

1. **Verify or Launch the FastMCP Server**:
   - Check if `.mcp.active` exists and the process is alive:
     ```bash
     [ -f .mcp.active ] && kill -0 $(jq -r .pid .mcp.active 2>/dev/null) 2>/dev/null || echo "DEAD"
     ```
   - If missing or dead, launch the server in the background with batch size 10:
     ```bash
     python3 update_with_ai/parts/systems/lib/cleanroom_mcp_runner_impl.py --transport sse --port 8765 --batch-size 10
     ```
   - Verify `.mcp.active` is created.

2. **Resolve Role Dependencies**:
   - Run the DAG resolution CLI (accepts either the single shortcut target or two arguments):
     ```bash
     python3 update_with_ai/support/lib/cleanroom_dag_cli.py resolve-roles <target-or-pair>
     ```
   - Example output for `//testing/parts/sandbox:sandbox_asm_qa`:
     `roles: ["//update_python_with_ai:high", "//update_python_with_ai:low", "//update_python_with_ai:lib", "//update_python_with_ai:test", "//update_python_with_ai:qa"]`.

3. **Launch the Role Subagent Fleet**:
   - Call `invoke_subagent` concurrently for all discovered roles, passing role-scoped session identifiers:
     ```python
     invoke_subagent(
         Subagents=[
             {
                 "TypeName": "cleanroom_role_worker",
                 "Role": f"{role_name.title()} Worker",
                 "Prompt": (
                     f"You are the Cleanroom role worker for role '{role_addr}' at unit '{unit_addr}'.\n"
                     f"1. Register your session:\n"
                     f"   python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session {role_name} register --role \"{role_addr}\" --unit \"{unit_addr}\"\n"
                     f"2. Work loop:\n"
                     f"   Call: python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session {role_name} get-work\n"
                     f"   - If output says 'No dirty nodes are ready for cleaning' or status is IDLE:\n"
                     f"     Output 'Standing by for upstream tasks.' and finish your turn.\n"
                     f"   - If work is assigned:\n"
                     f"     Inspect files using view_file, apply edits using replace_file_content or write_to_file.\n"
                     f"     Verify edits using: python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session {role_name} check-file --file <file>\n"
                     f"     When verified, call: python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session {role_name} submit\n"
                     f"     Repeat step 2 (get-work) until no dirty nodes are ready.\n"
                     f"3. When no work remains:\n"
                     f"   Output a concise completion summary and finish your turn."
                 )
             }
             for role_addr in discovered_roles
         ]
     )
     ```

4. **Staged Idling & Cascading Convergence**:
   - Roles with dirty nodes ready for work execute immediately.
   - Downstream roles receive `status: "IDLE"` from `get_work()`, output `"Standing by for upstream tasks."`, and drop into a zero-token idle state.
   - Subagents only idle during the run while upstream/peer subagents are actively performing work.
   - When an active worker completes and calls `submit()`, the node transitions to clean, unlocking dependent downstream tasks.
   - Antigravity automatically resumes the Main Chat upon worker turn completion.
   - When new work is unlocked for standing-by workers, message them to resume:
     ```python
     send_message(Recipient=worker_conv_id, Message="New upstream tasks submitted. Please call get_work().")
     ```

5. **Completion & Server Teardown**:
   - Check completion status:
     ```bash
     python3 update_with_ai/support/lib/cleanroom_dag_cli.py status <target-or-pair>
     ```
   - When all nodes are clean (`is_complete: true` and `dirty_nodes: []`):
     1. Terminate all worker subagents:
        ```python
        manage_subagents(Action="kill", ConversationIds=active_worker_ids)
        ```
     2. Shut down the FastMCP server:
        ```bash
        python3 update_with_ai/support/lib/cleanroom_mcp_client.py shutdown
        ```
     3. Remove `.mcp.active` if lingering.
     4. Summarize completed nodes for the user.

---

### 2. `/cleanroom change <target> "<message>"` or `/cleanroom change <unit-address> <role-address> "<message>"`

Injects an intentional change into a DAG node, marking it and all its downstream dependents dirty.

**Examples**:
```
/cleanroom change //testing/parts/sandbox:sandbox_asm_high "Add new parameter to configuration"
# or
/cleanroom change //testing/parts/sandbox:sandbox_asm //update_python_with_ai:high "Add new parameter to configuration"
```

#### Procedure:
1. Run the change injection command:
   ```bash
   python3 update_with_ai/support/lib/cleanroom_dag_cli.py inject-change <target-or-pair> "<message>"
   ```
2. Confirm the change is recorded and the target node is dirty.
3. Prompt or automatically run `/cleanroom clean` to converge the affected subgraph.

---

### 3. `/cleanroom status <target>` or `/cleanroom status <role-address> <unit-address>`

Reports the active server status, registered subagent fleet, and DAG subgraph cleanliness.

#### Procedure:
1. Check `.mcp.active` content and server process status.
2. Query `cleanroom_dag_cli.py status <target-or-pair>`.
3. Report which nodes are currently clean vs dirty.
