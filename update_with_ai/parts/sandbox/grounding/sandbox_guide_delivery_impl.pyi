from typing import Optional
from framework import operation, override, singleton_type
import agent_file_alias
import agent_node_config
import sandbox_guide_delivery
import tool_provider

@singleton_type('agent_session')
class GuideDelivery(sandbox_guide_delivery.GuideDelivery):
    """
PURPOSE:
Implements guide delivery to parse file content guides, obtain configured guide, and advance step sections

INHERITED_REQUIREMENTS:
- [GuideDelivery] Steps remaining indicates whether further step sections remain to be completed.

GROUNDING_ARGUMENT:
- As an agent_session singleton, GuideDelivery parses markdown guides and delivers progressive step sections, interacting with imported agent_node_config.NodeConfig in the same session lifecycle tier.
"""

    @property
    @override
    def has_steps_remaining(self) -> bool:
        """
PURPOSE:
Indicates whether a guide is configured and the current step index is less than the total count of step sections

GROUNDING_ARGUMENT:
- Computed from internal delivery state tracking the current step index against the total count of sections parsed from agent_node_config.NodeConfig.guide, updated as steps advance via mutable operation advance_step.
"""
        ...

    @operation
    def initialize(self) -> None:
        """
PURPOSE:
Obtains configured guide from node config

FRESH_REQUIREMENTS:
- Initializing the guide delivery obtains its guide from the node config.

GROUNDING_ARGUMENT:
- Obtains the configured task guide directly from imported agent_node_config.NodeConfig in the same session lifecycle tier.
"""
        ...

    @operation
    @override
    def parse_guide(self, content: agent_file_alias.FileContent) -> agent_node_config.Guide:
        """
PURPOSE:
Implements parse_guide to extract summary and step sections from file content

FRESH_REQUIREMENTS:
- Guide parsing extracts the summary from content preceding the first section heading and under any heading titled `Summary`, captures verification failure instructions when a section heading begins with `Verification failure`, and creates sequential step sections for subsequent level-two headings while excluding sections whose title begins with `Summary`, `Lint checks`, or `Verification failure`.

GROUNDING_ARGUMENT:
- Receives content directly as a parameter and parses the markdown text into summary, verification failure instructions, and step sections, excluding sections titled with Summary, Lint checks, or Verification failure.
"""
        ...

    @operation
    @override
    def advance_step(self, verification_passed: bool, failure_diagnostics: Optional[str]=None) -> Optional[tool_provider.Response]:
        """
PURPOSE:
Implements advance_step to deliver initial summary alone, subsequent step content with summary, or failure diagnostics with current step

FRESH_REQUIREMENTS:
- Advancing a step when verification passes emits a response containing the guide summary alone without delivering a step section when no step section has been delivered yet.
- Advancing a step when verification passes emits a response presenting the guide summary above the next step section content introduced by `Now check carefully:` and transitions to that step section when previous steps have been delivered and further step sections remain.
- Advancing a step when verification fails emits a response combining the guide summary, any configured verification failure instructions, and failure diagnostics without activating a step section when no step section has been delivered yet.
- Advancing a step when verification fails emits a response combining the guide summary, the current step section content introduced by `Now check carefully:`, any configured verification failure instructions, and failure diagnostics without advancing to subsequent sections when a step section is currently active.
- When no guide is configured or no step sections remain, the guide delivery indicates that no steps remain and advancing produces no response.

INHERITED_REQUIREMENTS:
- [GuideDelivery] Advancing step delivers instructional text when verification passes, or retains the current milestone and reports failure diagnostics alongside verification failure instructions when verification fails.

GROUNDING_ARGUMENT:
- Receives verification_passed and failure_diagnostics directly as parameters, evaluates the active delivery state against remaining sections on self, advances or retains the step state based on verification, and formats the response content combining any configured verification failure instructions using tool_provider.Response.
"""
        ...

    @property
    @override
    def guide(self) -> Optional[agent_node_config.Guide]:
        """
PURPOSE:
Exposes the configured guide for the session

GROUNDING_ARGUMENT:
- Returns the parsed guide instance stored on self.
"""
        ...
