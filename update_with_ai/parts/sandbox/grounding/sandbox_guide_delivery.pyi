from typing import Optional, Protocol
from framework import operation, singleton_type
import agent_file_alias
import agent_node_config
import tool_provider


@singleton_type("agent_session")
class GuideDelivery(Protocol):
    """Defined as an agent session service that delivers step-by-step instructions from a guide."""

    @property
    def has_steps_remaining(self) -> bool:
        """Exposes whether progressive step sections remain to be completed.

        REQUIREMENTS:
        - Steps remaining indicates whether further step sections remain to be completed.

        GROUNDING_PROVISIONS:
        - knows("has_steps_remaining", bool): Exposes whether steps remain to satisfy requirement 4.
        """
        ...

    @property
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        """Exposes the configured guide for the session.

        GROUNDING_PROVISIONS:
        - knows("configured_guide", Optional[agent_node_config.NodeGuide]): Exposes configured guide to satisfy requirement 5.
        """
        ...

    @operation
    def parse_guide(self, content: agent_file_alias.FileContent) -> agent_node_config.NodeGuide:
        """Parses file content into a guide.

        Args:
            content: File content representing the guide document.

        Returns:
            Structured NodeGuide containing summary, step sections, and verification failure guidance.

        GROUNDING_PROVISIONS:
        - action("parse_guide", agent_node_config.NodeGuide): Parses guide file content to satisfy requirement 2.
        """
        ...

    @operation
    def set_initial_primer(self, primer: str) -> None:
        """Records initial primer content for the active task.

        Args:
            primer: Text content of the initial primer.

        REQUIREMENTS:
        - Can record an initial primer.

        GROUNDING_PROVISIONS:
        - action("set_initial_primer", None): Sets initial primer to satisfy requirement 3.
        """
        ...

    @operation
    def advance_step(
        self, verification_passed: bool, failure_diagnostics: Optional[str] = None
    ) -> Optional[tool_provider.ToolResponse]:
        """Advances to the next step section if verification passed, or retains the current step and reports failure diagnostics.

        Args:
            verification_passed: Whether verification checks passed.
            failure_diagnostics: Optional diagnostic feedback from verification failure.

        Returns:
            Optional response containing instructional text.

        REQUIREMENTS:
        - Advancing step delivers instructional text when verification passes, or retains the current milestone and reports failure diagnostics alongside verification failure instructions when verification fails.

        GROUNDING_PROVISIONS:
        - action("advance_step", Optional[tool_provider.ToolResponse]): Advances guide milestone to satisfy requirement 3.
        """
        ...
