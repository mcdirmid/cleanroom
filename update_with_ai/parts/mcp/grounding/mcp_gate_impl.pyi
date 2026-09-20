from typing import Sequence
from framework import operation, override, singleton_type
import filesystem_ext
import mcp_gate
import mcp_session
import sandbox_file_editor
import sandbox_file_reader
import tool_provider

@singleton_type('system')
class AccessGate(mcp_gate.AccessGate):
    """
PURPOSE:
Implements access gate to validate intercepted hook tool calls and sanitize directory listings

INHERITED_REQUIREMENTS:
- [AccessGate] Validating access resolves tool permissions for the conversation and target file path, producing an access decision.
- [AccessGate] Filtering directory listings sanitizes child entries for the conversation and target directory path, preserving role blindness.

GROUNDING_ARGUMENT:
- As a system singleton, AccessGate coordinates with imported mcp_session.RoleSessionManager to retrieve session scopes, executing guard tools in imported tool_provider.ToolManager within the activated scope.
"""

    @operation
    @override
    def validate_access(self, conversation_id: mcp_session.ConversationId, tool_name: str, file_path: str) -> mcp_gate.AccessDecision:
        """
PURPOSE:
Validates access permissions for an intercepted file tool invocation

GROUNDING_ARGUMENT:
- Resolves the session scope via imported mcp_session.RoleSessionManager.get_session_scope, fails closed if absent, normalizes file_path against workspace root via imported filesystem_ext, activates scope via scope.activate(), and dispatches to can_write or can_read tool on imported tool_provider.ToolManager.
"""
        ...

    @operation
    @override
    def filter_directory_listing(self, conversation_id: mcp_session.ConversationId, directory_path: str, entries: Sequence[str]) -> Sequence[str]:
        """
PURPOSE:
Sanitizes directory listing entries according to role read permissions

GROUNDING_ARGUMENT:
- Resolves the session scope via imported mcp_session.RoleSessionManager.get_session_scope, activates scope via scope.activate(), and tests candidate entries against can_read tool on imported tool_provider.ToolManager, returning only readable child entries.
"""
        ...
