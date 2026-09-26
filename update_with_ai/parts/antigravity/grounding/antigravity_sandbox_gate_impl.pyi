from framework import operation, override, singleton_type
from typing import Dict, Self, Tuple
import antigravity_run_logger
import antigravity_sandbox_gate

@singleton_type('system')
class AntigravitySandboxGate(antigravity_sandbox_gate.AntigravitySandboxGate):
    """Realizes pre-tool gating enforcement to confine Antigravity subagent operations to authorized actions and boundaries.

    GROUNDING_ARGUMENT:
    - System singleton evaluating pre-tool payloads, whitelisting worker shell commands, inspecting subagent manifests, and querying HTTP validation routes.
    """

    @operation
    @override
    def process_hook_input(self, payload: str) -> antigravity_sandbox_gate.GatingDecision:
        """
        REQUIREMENTS:
        - Processing hook input parses the incoming JSON payload into conversation identifier, tool name, and arguments.
        - When the tool is `invoke_subagent` spawning a role worker, the gate verifies that the caller is a coordinator subagent, denying unauthorized spawns.
        - When the caller is a role worker executing `run_command`, the gate validates the command line against a strict whitelist.
        - When the caller is a role worker invoking file tools (`view_file`, `replace_file_content`, `write_to_file`), the gate verifies that the Model Context Protocol server is active and queries its HTTP validation route.
        - When the caller is a coordinator executing `run_command`, the gate validates the command line against a strict coordinator whitelist, denying arbitrary commands, troubleshooting utilities, and file modifications.
        - Other callers bypass command and file gating.

        GROUNDING_PROVISIONS:
        - action("evaluate_tool_payload", antigravity_sandbox_gate.GatingDecision): Parses and evaluates tool hook payload.

        GROUNDING_ARGUMENT:
        - action("evaluate_tool_payload", Self) :- action("validate_worker_command_line", Self), action("validate_coordinator_command_line", Self), action("verify_coordinator_caller", Self), action("verify_role_worker_caller", Self), action("query_active_worker_sessions", Self).
        """
        ...

    @operation
    @override
    def validate_worker_command(self, command_line: str) -> Tuple[bool, str]:
        """
        REQUIREMENTS:
        - Commands containing shell metacharacters or chaining operators are denied.
        - Commands executing unauthorized scripts or missing python binaries are denied.
        - Commands executing whitelisted subcommands (`register`, `deregister`, `get-work`, `check-files`, `check-file`, `submit`, `blame`, `fail`) are allowed.

        GROUNDING_IMPLEMENTS:
        - action("validate_worker_command_line", Tuple[bool, str]): Validates worker command against whitelist.
        """
        ...

    @operation
    @override
    def validate_coordinator_command(self, command_line: str) -> Tuple[bool, str]:
        """
        REQUIREMENTS:
        - Commands containing shell metacharacters or chaining operators are denied.
        - Commands executing unauthorized scripts or missing python binaries are denied.
        - Commands executing whitelisted coordinator subcommands are allowed.

        GROUNDING_IMPLEMENTS:
        - action("validate_coordinator_command_line", Tuple[bool, str]): Validates coordinator command against whitelist.
        """
        ...

    @operation
    @override
    def is_coordinator_caller(self, identifier: str) -> bool:
        """
        REQUIREMENTS:
        - Verifying coordinator and role worker callers searches subagent descriptor manifests in conversation directories to resolve the caller's type name.

        GROUNDING_IMPLEMENTS:
        - action("verify_coordinator_caller", bool): Checks if caller is coordinator.
        """
        ...

    @operation
    @override
    def is_role_worker_caller(self, identifier: str) -> bool:
        """
        REQUIREMENTS:
        - Verifying coordinator and role worker callers searches subagent descriptor manifests in conversation directories to resolve the caller's type name.

        GROUNDING_IMPLEMENTS:
        - action("verify_role_worker_caller", bool): Checks if caller is role worker.
        """
        ...

    @operation
    @override
    def save_worker_session(self, worker_id: str, session_id: str) -> None:
        """
        REQUIREMENTS:
        - Managing worker sessions records active worker identifiers alongside their assigned session identifiers in an atomic session state file in the workspace root.

        GROUNDING_IMPLEMENTS:
        - action("associate_worker_session", None): Saves worker session association.
        """
        ...

    @operation
    @override
    def remove_worker_session(self, worker_id: str) -> None:
        """
        REQUIREMENTS:
        - Managing worker sessions records active worker identifiers alongside their assigned session identifiers in an atomic session state file in the workspace root.

        GROUNDING_IMPLEMENTS:
        - action("disassociate_worker_session", None): Removes worker session association.
        """
        ...

    @operation
    @override
    def read_worker_sessions(self) -> Dict[str, str]:
        """
        REQUIREMENTS:
        - Managing worker sessions records active worker identifiers alongside their assigned session identifiers in an atomic session state file in the workspace root.

        GROUNDING_IMPLEMENTS:
        - action("query_active_worker_sessions", Dict[str, str]): Reads active worker session associations.
        """
        ...
