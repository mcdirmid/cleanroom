# Cleanroom Role Worker Protocol

This document defines the operational rules and boundaries for ephemeral `cleanroom_role_worker` subagents.

## 1. Lifecycle Sequence
1. **Register**:
   ```bash
   python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session <session_id> register --role "<role>" --unit "<unit>"
   ```
2. **Retrieve Work**:
   ```bash
   python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session <session_id> get-work
   ```
3. **Execute Assigned Files**:
   - Inspect companion grounding specifications (`grounding/*.pyi`) and role guide (`update_python_with_ai/guides/*.md`).
   - Edit implementations or tests using `replace_file_content` or `write_to_file`. **You may edit files in any order (or all at once)** to maximize token efficiency.
   - Run verification checks across all files:
     ```bash
     python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session <session_id> check-files
     ```
   - Submit each verified target **in topological dependency order** (dependencies before dependents):
     ```bash
     python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session <session_id> submit --target <path> --change-summary "<summary>"
     ```
   - If contract failures originate in an upstream dependency, attribute blame:
     ```bash
     python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session <session_id> blame --target <path> --blame-target <dep_path> --explanation "<reason>"
     ```
4. **Complete Turn**:
   - Send concise completion report to the coordinator via `send_message`.
   - Terminate turn immediately.

---

## 2. Strict Boundary Rules

### A. Fail-Fast Rule on Server Errors
- If `get-work` returns `"No dirty nodes are ready for cleaning"`, `"Open session targets remain"`, or any error message:
  **DO NOT** attempt to debug the server, inspect process lists, or search framework internals.
  Immediately report the message to the coordinator and terminate your turn.

### B. Forbidden Documents & Files
- **NEVER read architectural or design docs** (`design-docs/*.md`).
- **NEVER search or read framework internal code** (`update_with_ai/parts/systems/...`, `update_with_ai/parts/mcp/...`, `update_with_ai/parts/dag/...`, `update_with_ai/parts/sandbox/...`).
- **Permitted File Access Only**:
  1. Target file(s) assigned in `get-work`.
  2. Companion grounding specifications (`grounding/*.pyi`).
  3. Role guide referenced by `get-work` (e.g. `update_python_with_ai/guides/grounding_to_lib.md`).
