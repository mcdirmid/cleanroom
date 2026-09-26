from typing import Self, Sequence
from framework import operation, override, singleton_type
import filesystem_ext
import mcp_gate
import mcp_session
import sandbox_file_editor
import sandbox_file_reader


@singleton_type('system')
class AccessGate(mcp_gate.AccessGate):
    """Implements access gate to validate intercepted hook tool calls and sanitize directory listings.

    GROUNDING_ARGUMENT:
    - As a system singleton, AccessGate coordinates with imported mcp_session.RoleSessionManager to retrieve session scopes, querying sandbox_file_reader.ReadManager and sandbox_file_editor.EditManager within the activated scope.
    """

    @operation
    @override
    def validate_access(self, conversation_id: mcp_session.ConversationId, tool_name: str, file_path: str) -> mcp_gate.AccessDecision:
        """Validates access permissions for an intercepted file tool invocation.

        GROUNDING_PROVISIONS:
        - action("validate_file_access", mcp_gate.AccessDecision): Validates file access permissions.

        GROUNDING_ARGUMENT:
        - action("validate_file_access", Self) :- action("get_session_scope", mcp_session.RoleSessionManager), action("can_read", sandbox_file_reader.ReadManager), action("can_write", sandbox_file_editor.EditManager), knows("target_file_path", Self).
        """
        ...

    @operation
    @override
    def filter_directory_listing(self, conversation_id: mcp_session.ConversationId, directory_path: str, entries: Sequence[str]) -> Sequence[str]:
        """Sanitizes directory listing entries according to role read permissions.

        GROUNDING_PROVISIONS:
        - action("sanitize_directory_entries", Sequence[str]): Filters directory listing entries.

        GROUNDING_ARGUMENT:
        - action("sanitize_directory_entries", Self) :- action("get_session_scope", mcp_session.RoleSessionManager), action("can_read", sandbox_file_reader.ReadManager), knows("role_blindness_exclusions", Self).
        """
        ...
