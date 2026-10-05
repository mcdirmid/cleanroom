# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 972efcb88455
# --- END CLEANROOM METADATA ---

"""Sandbox guide delivery low-level interface specification."""

from typing import NewType, Optional, Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import tool_provider

InitialPrimer = NewType("InitialPrimer", str)


@singleton_type("agent_session")
class GuideDelivery(InTier[AgentSessionTier], Protocol):
    """Delivers sequential task guidance and gates progression behind verification checks."""

    @property
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
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
    def parse_guide(self, content: agent_file_alias.FileContent) -> agent_node_config.NodeGuide:
        """Parses markdown file content into a structured node guide.

        Args:
            content: The raw markdown content of the guide.

        Returns:
            The structured node guide.

        POSTCONDITIONS:
        - MUST parse file content into a structured node guide.
        """
        ...

    @operation
    def record_initial_primer(self, primer: InitialPrimer) -> None:
        """Records initial primer text prior to milestone progression.

        Args:
            primer: The initial instructional text.

        POSTCONDITIONS:
        - MUST record the initial primer text.
        """
        ...

    @operation
    def advance_step(
        self, verification_passed: bool, failure_diagnostics: agent_node_config.VerificationDiagnostic
    ) -> Optional[tool_provider.ToolResponse]:
        """Advances or preserves current milestone based on verification results.

        Args:
            verification_passed: Whether verification checks passed.
            failure_diagnostics: Diagnostic error output when verification failed.

        Returns:
            Optional response containing instructional text or failure diagnostics.

        POSTCONDITIONS:
        - WHEN verification passes, MUST deliver instructional text.
        - WHEN verification fails, MUST retain current milestone and report failure diagnostics alongside verification failure instructions.
        """
        ...
