---
name: cleanroom
description: Autonomous Cleanroom role workspace coordinator, work queue inspector, and subagent fleet manager.
whenToUse: Use when the user types /cleanroom, asks to orchestrate, or asks to run cleanroom roles for a scope.
---

# Cleanroom Autonomous Coordinator

When the user invokes `/cleanroom [scope] [target_role]` (e.g., `/cleanroom staging qa` or `orchestrate staging`):
**You are the Master Coordinator.** Immediately and autonomously execute the Cleanroom DAG using DSH native subagents:

## Autonomous Execution Loop

1. **Inspect Ready Roles in the DAG**:
   Run:
   ```bash
   bin/cleanroom work-queue <dir_scope> [target_role] --json
   ```
   Check which roles currently have ready targets. If all roles in scope are clean, report convergence to the user and stop.

2. **Commission Workspace**:
   For the first ready role, commission its workspace:
   ```bash
   bin/cleanroom commission <role> <dir_scope>
   ```
   This prepares the role workspace at `../role_workspaces/<ws>_<role>_<scope>/` with its internal tools (`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, `bin/fail`).

3. **Dispatch Role Subagent**:
   Call the DSH native `subagent` tool:
   - `description`: `[<ROLE>] <scope> worker`
   - `prompt`:
     ```text
     You are the <role> worker for scope <scope>.
     Your assigned workspace is: /Users/seanmcdirmid/projects/role_workspaces/cleanroom_<role>_<scope>
     1. Change directory to your workspace.
     2. Run `bin/get_work` to view the pending tasks and contract guidelines.
     3. DO NOT EDIT METADATA. Never touch metadata headers. Only edit code or specifications.
     4. Run `bin/check_files` to ensure all checks pass.
     5. Run `bin/submit` to submit your work, or `bin/blame` if upstream defects are discovered.
     ```

4. **Iterate Until Clean Convergence**:
   When the child subagent finishes, re-run `bin/cleanroom work-queue <dir_scope> [target_role] --json`.
   Repeat steps 2–3 for subsequent ready roles until all roles in scope are clean.
   Once clean, report: `Cleanroom orchestration for <scope> converged successfully!`

---

## Alternative Options

- If the user explicitly asks to run via the automated CLI script instead of subagents, run:
  ```bash
  bin/cleanroom orchestrate <dir_scope> [target_role] --harness dsh
  ```
- To run tests: `bin/test`
