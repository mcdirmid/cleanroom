# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T03:26:00Z
# CHANGE: Align configured guide delivery, milestone advancement, and failure reporting contracts
# CODE_HASH: 8948e9f16fed
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Sandbox guide delivery low-level interface specification."""

from typing import NewType, Optional, Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from session import AgentSessionTier
import file_alias
import node_config
import tool_provider

InitialPrimer = NewType("InitialPrimer", str)


@singleton_type("agent_session")
class GuideDelivery(InTier[AgentSessionTier], Protocol):
    """Delivers the instructions of a configured guide progressively and gates progression behind verification checks."""

    @property
    def guide(self) -> Optional[node_config.NodeGuide]:
        """Exposes the configured node guide.

        POSTCONDITIONS:
        - MUST return the configured node guide when present.
        """
        ...

    @property
    def has_steps_remaining(self) -> bool:
        """Indicates whether progressive steps remain to be completed.

        POSTCONDITIONS:
        - MUST return whether progressive steps remain to be completed.
        """
        ...

    @operation
    def parse_guide(self, content: file_alias.FileContent) -> node_config.NodeGuide:
        """Parses markdown file content into a structured node guide.

        Args:
            content: The raw markdown content of the guide.

        Returns:
            The structured node guide.

        POSTCONDITIONS:
        - MUST construct a guide containing a summary, sequential step sections, and verification failure instructions derived from the supplied file content.
        """
        ...

    @operation
    def record_initial_primer(self, primer: InitialPrimer) -> None:
        """Records initial primer text prior to milestone progression.

        Args:
            primer: The initial instructional text.

        POSTCONDITIONS:
        - MUST record the initial primer as the first instructional content of the session.
        """
        ...

    @operation
    def advance_step(
        self, verification_passed: bool, failure_diagnostics: node_config.VerificationDiagnostic
    ) -> Optional[tool_provider.ToolResponse]:
        """Advances or preserves current milestone based on verification results.

        Args:
            verification_passed: Whether verification checks passed.
            failure_diagnostics: Diagnostic error output when verification failed.

        Returns:
            Optional response containing instructional text or failure diagnostics.

        POSTCONDITIONS:
        - WHEN verification passes, MUST deliver instructional text for the next milestone.
        - WHEN verification fails, MUST retain the current milestone.
        - WHEN verification fails, MUST report the failure diagnostics.
        - WHEN verification fails, MUST report the verification failure instructions.
        """
        ...
