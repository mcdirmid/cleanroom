from framework import operation, override, singleton_type
from typing import Dict, Tuple
import antigravity_run_logger
import antigravity_sandbox_gate

@singleton_type('system')
class AntigravitySandboxGate(antigravity_sandbox_gate.AntigravitySandboxGate):
    """
PURPOSE:
Realizes pre-tool gating enforcement to confine Antigravity subagent operations to authorized actions and boundaries.

GROUNDING_ARGUMENT:
- System singleton evaluating pre-tool payloads, whitelisting worker shell commands, inspecting subagent manifests, and querying HTTP validation routes.
"""

    @operation
    @override
    def process_hook_input(self, payload: str) -> antigravity_sandbox_gate.GatingDecision:
        """
PURPOSE:
Parses the incoming JSON payload into conversation identifier, tool name, and arguments, verifying permissions based on caller identity.

FRESH_REQUIREMENTS:
- Processing hook input parses the incoming JSON payload into conversation identifier, tool name, and arguments.
- When the tool is `invoke_subagent` spawning a role worker, the gate verifies that the caller is a coordinator subagent, denying unauthorized spawns.
- When the caller is a role worker executing `run_command`, the gate validates the command line against a strict whitelist.
- When the caller is a role worker invoking file tools (`view_file`, `replace_file_content`, `write_to_file`), the gate verifies that the Model Context Protocol server is active and queries its HTTP validation route.
- When the caller is a coordinator executing `run_command`, the gate validates the command line against a strict coordinator whitelist, denying arbitrary commands, troubleshooting utilities, and file modifications.
- Other callers bypass command and file gating.

INHERITED_REQUIREMENTS:
- [AntigravitySandboxGate] The antigravity sandbox gate evaluates a raw JSON payload string and returns a gating decision.

GROUNDING_ARGUMENT:
- Parses JSON payload, checks caller descriptor, applies subcommand and file tool routing, querying FastMCP validate_access HTTP endpoint.
"""
        ...

    @operation
    @override
    def validate_worker_command(self, command_line: str) -> Tuple[bool, str]:
        """
PURPOSE:
Ensures the command begins with a valid Python binary executing the client script with an authorized subcommand.

FRESH_REQUIREMENTS:
- Commands containing shell metacharacters or chaining operators are denied.
- Commands executing unauthorized scripts or missing python binaries are denied.
- Commands executing whitelisted subcommands (`register`, `deregister`, `get-work`, `check-files`, `check-file`, `submit`, `blame`, `fail`) are allowed.

INHERITED_REQUIREMENTS:
- [AntigravitySandboxGate] The antigravity sandbox gate inspects a command line and determines whether execution is permitted.

GROUNDING_ARGUMENT:
- Splits command tokens using shlex, checks for shell metacharacters, validates python binary name, checks target script path, and validates subcommand against whitelist.
"""
        ...

    @operation
    @override
    def validate_coordinator_command(self, command_line: str) -> Tuple[bool, str]:
        """
PURPOSE:
Ensures the command begins with a valid Python binary executing the coordinator implementation with authorized subcommands or the telemetry implementation.

FRESH_REQUIREMENTS:
- Commands containing shell metacharacters or chaining operators are denied.
- Commands executing unauthorized scripts or missing python binaries are denied.
- Commands executing whitelisted coordinator subcommands are allowed.

INHERITED_REQUIREMENTS:
- [AntigravitySandboxGate] The antigravity sandbox gate inspects a command line and determines whether coordinator execution is permitted.

GROUNDING_ARGUMENT:
- Splits command tokens using shlex, checks for shell metacharacters, validates python binary name, checks target script or module path, and validates coordinator subcommand against whitelist.
"""
        ...

    @operation
    @override
    def is_coordinator_caller(self, identifier: str) -> bool:
        """
PURPOSE:
Verifies whether a conversation identifier belongs to a coordinator subagent.

FRESH_REQUIREMENTS:
- Verifying coordinator and role worker callers searches subagent descriptor manifests in conversation directories to resolve the caller's type name.

INHERITED_REQUIREMENTS:
- [AntigravitySandboxGate] The antigravity sandbox gate verifies whether a conversation identifier belongs to a coordinator subagent.

GROUNDING_ARGUMENT:
- Reads subagent descriptor JSON file corresponding to conversation identifier from Antigravity brain directories, checking typeName equals cleanroom_coordinator.
"""
        ...

    @operation
    @override
    def is_role_worker_caller(self, identifier: str) -> bool:
        """
PURPOSE:
Verifies whether a conversation identifier belongs to a role worker subagent.

FRESH_REQUIREMENTS:
- Verifying coordinator and role worker callers searches subagent descriptor manifests in conversation directories to resolve the caller's type name.

INHERITED_REQUIREMENTS:
- [AntigravitySandboxGate] The antigravity sandbox gate verifies whether a conversation identifier belongs to a role worker subagent.

GROUNDING_ARGUMENT:
- Reads subagent descriptor JSON file corresponding to conversation identifier from Antigravity brain directories, checking typeName equals cleanroom_role_worker.
"""
        ...

    @operation
    @override
    def save_worker_session(self, worker_id: str, session_id: str) -> None:
        """
PURPOSE:
Records active worker identifiers alongside their assigned session identifiers in an atomic session state file in the workspace root.

FRESH_REQUIREMENTS:
- Managing worker sessions records active worker identifiers alongside their assigned session identifiers in an atomic session state file in the workspace root.

INHERITED_REQUIREMENTS:
- [AntigravitySandboxGate] The antigravity sandbox gate associates a worker identifier with a session identifier.

GROUNDING_ARGUMENT:
- Loads session state JSON, adds or updates the worker mapping, and writes atomically via replacement.
"""
        ...

    @operation
    @override
    def remove_worker_session(self, worker_id: str) -> None:
        """
PURPOSE:
Removes active worker session mappings.

FRESH_REQUIREMENTS:
- Managing worker sessions records active worker identifiers alongside their assigned session identifiers in an atomic session state file in the workspace root.

INHERITED_REQUIREMENTS:
- [AntigravitySandboxGate] The antigravity sandbox gate disassociates a worker identifier.

GROUNDING_ARGUMENT:
- Loads session state JSON, deletes the worker key if present, and saves updated file atomically.
"""
        ...

    @operation
    @override
    def read_worker_sessions(self) -> Dict[str, str]:
        """
PURPOSE:
Reads all active worker session associations.

FRESH_REQUIREMENTS:
- Managing worker sessions records active worker identifiers alongside their assigned session identifiers in an atomic session state file in the workspace root.

INHERITED_REQUIREMENTS:
- [AntigravitySandboxGate] The antigravity sandbox gate returns all active worker session associations.

GROUNDING_ARGUMENT:
- Reads and parses the worker session JSON file from disk, returning an empty dictionary if absent.
"""
        ...
