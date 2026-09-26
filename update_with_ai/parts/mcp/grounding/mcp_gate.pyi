from dataclasses import dataclass
from typing import Protocol, Sequence
from framework import data_type, operation, singleton_type
import mcp_session


@dataclass(frozen=True)
@data_type
class AccessDecision:
    """Represents the authorization result for an intercepted tool invocation."""

    def __init__(self, is_allowed: bool, reason: str) -> None:
        ...

    @property
    def is_allowed(self) -> bool:
        """Indicates whether the invocation is allowed to proceed."""
        ...

    @property
    def reason(self) -> str:
        """Details why access was permitted or denied."""
        ...


@singleton_type('system')
class AccessGate(Protocol):
    """System service that validates intercepted file access requests and sanitizes directory listings.

    REQUIREMENTS:
    - Validating access resolves tool permissions for the conversation and target file path, producing an access decision.
    - Filtering directory listings sanitizes child entries for the conversation and target directory path, preserving role blindness.
    """

    @operation
    def validate_access(self, conversation_id: mcp_session.ConversationId, tool_name: str, file_path: str) -> AccessDecision:
        """Validates access permissions for an intercepted file tool invocation.

        GROUNDING_PROVISIONS:
        - action("validate_file_access", AccessDecision): Validates tool access permissions for file operations.
        """
        ...

    @operation
    def filter_directory_listing(self, conversation_id: mcp_session.ConversationId, directory_path: str, entries: Sequence[str]) -> Sequence[str]:
        """Sanitizes directory listing entries according to role read permissions.

        GROUNDING_PROVISIONS:
        - action("sanitize_directory_entries", Sequence[str]): Sanitizes child directory entries to preserve role blindness.
        """
        ...
