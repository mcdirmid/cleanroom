# antigravity_sandbox_gate_impl implementation component

imports: antigravity_run_logger
implements: antigravity_sandbox_gate

## Purpose

The antigravity_sandbox_gate_impl implementation component realizes pre-tool gating enforcement to confine Antigravity subagent operations to authorized actions and boundaries.

Securing multi-agent Cleanroom execution against sandbox escapes requires intercepting tool requests, checking worker identity against subagent manifests, whitelisting Python client subcommands, and querying the FastMCP HTTP gate for file edits. The antigravity_sandbox_gate_impl implementation component enforces strict caller isolation, updates session mappings, and blocks unauthorized actions.

**Out of scope:** The antigravity_sandbox_gate_impl implementation component does not parse AST grammar, compute DAG topological batches, or execute compiler builds; these are handled by other components.

## Types and Behavior

The antigravity sandbox gate operates as a system service intercepting and evaluating PreToolUse events.

Processing hook input parses the incoming JSON payload into conversation identifier, tool name, and arguments. When the tool is `invoke_subagent` spawning a role worker, the gate verifies that the caller is a coordinator subagent, denying unauthorized spawns. When the caller is a role worker executing `run_command`, the gate validates the command line against a strict whitelist. When the caller is a role worker invoking file tools (`view_file`, `replace_file_content`, `write_to_file`), the gate verifies that the Model Context Protocol server is active and queries its HTTP validation route. When the caller is a coordinator executing `run_command`, the gate validates the command line against a strict coordinator whitelist, denying arbitrary commands, troubleshooting utilities, and file modifications. Other callers bypass command and file gating.

Validating a worker command line ensures the command begins with a valid Python binary executing the client script with an authorized subcommand:

- Commands containing shell metacharacters or chaining operators are denied.

- Commands executing unauthorized scripts or missing python binaries are denied.

- Commands executing whitelisted subcommands (`register`, `deregister`, `get-work`, `check-files`, `check-file`, `submit`, `blame`, `fail`) are allowed.

Validating a coordinator command line ensures the command begins with a valid Python binary executing the coordinator implementation with authorized subcommands (`step`, `register-spawned`) or the telemetry implementation:

- Commands containing shell metacharacters or chaining operators are denied.

- Commands executing unauthorized scripts or missing python binaries are denied.

- Commands executing whitelisted coordinator subcommands are allowed.

Verifying coordinator and role worker callers searches subagent descriptor manifests in conversation directories to resolve the caller's type name.

Managing worker sessions records active worker identifiers alongside their assigned session identifiers in an atomic session state file in the workspace root.
