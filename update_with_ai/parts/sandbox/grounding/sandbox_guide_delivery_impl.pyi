from typing import Optional, Self
from framework import operation, override, singleton_type
import agent_file_alias
import agent_node_config
import sandbox_guide_delivery
import tool_provider


@singleton_type("agent_session")
class GuideDelivery(sandbox_guide_delivery.GuideDelivery):
    """Implements guide delivery to parse file content guides, obtain configured guide, and advance step sections.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, GuideDelivery parses markdown guides and delivers progressive step sections, interacting with imported agent_node_config.NodeConfig in the same session lifecycle tier.
    """

    @property
    @override
    def has_steps_remaining(self) -> bool:
        """Indicates whether a guide is configured and the current step index is less than the total count of step sections.

        GROUNDING_IMPLEMENTS:
        - knows("has_steps_remaining", bool): Reports whether steps remain to satisfy requirement 7.
        """
        ...

    @operation
    def initialize(self) -> None:
        """Obtains configured guide from node config.

        REQUIREMENTS:
        - When initialized for an agent session, the guide delivery obtains its guide parsed from configured guide file content.

        GROUNDING_PROVISIONS:
        - action("initialize_guide", None): Initializes guide to satisfy requirement 1.

        GROUNDING_ARGUMENT:
        - action("initialize_guide", Self) :- knows("guide", agent_node_config.NodeConfig).
        """
        ...

    @operation
    @override
    def parse_guide(self, content: agent_file_alias.FileContent) -> agent_node_config.NodeGuide:
        """Parses file content into a structured guide.

        Args:
            content: The file content to parse.

        Returns:
            The parsed guide.

        REQUIREMENTS:
        - Parsing extracts guide summary from content preceding the first section heading and under headings titled Summary, captures verification failure instructions when heading begins with Verification failure, and creates sequential step sections for subsequent level-two headings excluding Summary, Lint checks, or Verification failure.

        GROUNDING_IMPLEMENTS:
        - action("parse_guide", agent_node_config.NodeGuide): Parses markdown guide content to satisfy requirement 2.
        """
        ...

    @operation
    def set_initial_primer(self, primer: str) -> None:
        """Sets the initial primer content delivered for the task.

        Args:
            primer: The initial primer text.

        REQUIREMENTS:
        - Can record an initial primer.

        GROUNDING_IMPLEMENTS:
        - action("set_initial_primer", None): Records initial primer to satisfy requirement 3.
        """
        ...

    @operation
    @override
    def advance_step(
        self, verification_passed: bool, failure_diagnostics: Optional[str] = None
    ) -> Optional[tool_provider.ToolResponse]:
        """Delivers instructional text or failure diagnostics based on verification outcome.

        Args:
            verification_passed: Whether verification passed.
            failure_diagnostics: Optional diagnostic feedback.

        Returns:
            Optional response containing step instructions or feedback.

        REQUIREMENTS:
        - Advancing a step when verification passes emits a response presenting the next step section content introduced by Now check carefully: alongside instructions to check carefully, make edits if the source file does not conform to any checklist item, and call advance() only when conforming, transitioning to that step section when further step sections remain.
        - Advancing a step when verification fails emits a response combining the initial primer content (or guide summary when an initial primer is omitted), any configured verification failure instructions, and failure diagnostics without activating a step section when no step section has been delivered yet.
        - Advancing a step when verification fails emits a response combining the current step section content introduced by Now check carefully:, any configured verification failure instructions, and failure diagnostics without advancing to subsequent sections when a step section is currently active.
        - When no guide is configured or no step sections remain, the guide delivery indicates that no steps remain and advancing produces no response.

        GROUNDING_IMPLEMENTS:
        - action("advance_step", Optional[tool_provider.ToolResponse]): Advances guide milestone to satisfy requirements 3, 4, 5, and 6.
        """
        ...

    @property
    @override
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        """Exposes the configured guide for the session.

        GROUNDING_PROVISIONS:
        - knows("configured_guide", Optional[agent_node_config.NodeGuide]): Exposes parsed guide.

        GROUNDING_ARGUMENT:
        - knows("configured_guide", Self) :- knows("guide", agent_node_config.NodeConfig).
        """
        ...
