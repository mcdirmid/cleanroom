# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 5d8e73ad4078
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Sandbox guide delivery implementation low-level specification."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import sandbox_guide_delivery
import tool_provider


@singleton_type("agent_session")
class GuideDelivery(
    sandbox_guide_delivery.GuideDelivery, InTier[AgentSessionTier]
):
    """Realizes markdown guide parsing and milestone-gated step progression.

    GROUNDING:
    - Tracks the parsed NodeGuide, active step offset, and optional InitialPrimer
      in private attributes within the agent session tier.
    """

    @property
    @override
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        """Exposes the configured node guide.

        GROUNDING:
        - Exposes the internal parsed NodeGuide or None if unconfigured.
        """
        ...

    @property
    @override
    def has_steps_remaining(self) -> bool:
        """Exposes whether steps remain to be completed.

        GROUNDING:
        - Checks whether the active step offset is less than the total count of step sections.
        """
        ...

    @operation
    @override
    def parse_guide(self, content: agent_file_alias.FileContent) -> agent_node_config.NodeGuide:
        """Parses markdown text into structured guide sections.

        Args:
            content: The raw markdown content of the guide.

        Returns:
            The parsed node guide.

        POSTCONDITIONS:
        - MUST extract the guide summary from content preceding the first heading and under headings titled "Summary".
        - MUST capture verification failure instructions when a section heading begins with "Verification failure".
        - MUST create sequential step sections for level-two headings excluding sections titled "Summary", "Lint checks", or "Verification failure".

        GROUNDING:
        - Parses markdown text by splitting on section headings, extracting summary, failure instructions, and step sections.
        """
        ...

    @operation
    @override
    def record_initial_primer(self, primer: sandbox_guide_delivery.InitialPrimer) -> None:
        """Records the initial primer instructional context.

        GROUNDING:
        - Stores the supplied InitialPrimer in private session state.
        """
        ...

    @operation
    @override
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

        GROUNDING:
        - Advances step offset if verification passed and steps remain; otherwise preserves offset and formats failure response with failure instructions and diagnostics.
        """
        ...
