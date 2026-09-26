# antigravity_sandbox_gate_impl implementation component

imports: antigravity_run_logger
implements: antigravity_sandbox_gate

## Assumptions and Requirements

### Requirements

1. Processing hook input parses the incoming JSON payload into conversation identifier, tool name, and arguments.
2. When the tool is `invoke_subagent` spawning a role worker, the gate verifies that the caller is a coordinator subagent, denying unauthorized spawns.
3. When the caller is a role worker executing `run_command`, the gate validates the command line against a strict whitelist.
4. When the caller is a role worker invoking file tools (`view_file`, `replace_file_content`, `write_to_file`), the gate verifies that the Model Context Protocol server is active and queries its HTTP validation route.
5. When the caller is a coordinator executing `run_command`, the gate validates the command line against a strict coordinator whitelist, denying arbitrary commands, troubleshooting utilities, and file modifications.
6. Other callers bypass command and file gating.
7. Commands containing shell metacharacters or chaining operators are denied.
8. Commands executing unauthorized scripts or missing python binaries are denied.
9. Commands executing whitelisted subcommands (`register`, `deregister`, `get-work`, `check-files`, `check-file`, `submit`, `blame`, `fail`) are allowed.
10. Commands executing whitelisted coordinator subcommands are allowed.
11. Verifying coordinator and role worker callers searches subagent descriptor manifests in conversation directories to resolve the caller's type name.
12. Managing worker sessions records active worker identifiers alongside their assigned session identifiers in an atomic session state file in the workspace root.

## Grounding Facts

### Knowledge Needed

- Tool call payload fields.
- Role worker and coordinator command whitelists.
- Shell metacharacters and chaining operator patterns.
- Subagent descriptor manifests in conversation directories.
- Worker session state file path in workspace root.
- Server validation endpoint.

### Actions Needed

- Parse hook JSON payload.
- Inspect subagent descriptor manifests to resolve caller type.
- Validate command line tokens against whitelists and metacharacter filters.
- Query MCP server validation route for file tools.
- Read and update worker session state file in workspace root.
