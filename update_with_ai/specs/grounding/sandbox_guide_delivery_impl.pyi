from typing import Optional
from framework import operation, override, singleton_type
import file_alias
import node_config
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
- As an agent_session singleton, GuideDelivery parses markdown guides and delivers progressive step sections, interacting with imported node_config.NodeConfig in the same session lifecycle tier.
"""

    @property
    @override
    def has_steps_remaining(self) -> bool:
        """
PURPOSE:
Indicates whether a guide is configured and the current step index is less than the total count of step sections

GROUNDING_ARGUMENT:
- Computed from internal delivery state tracking the current step index against the total count of sections parsed from node_config.NodeConfig.guide, updated as steps advance via mutable operation advance_step.
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
- Obtains the configured task guide directly from imported node_config.NodeConfig in the same session lifecycle tier.
"""
        ...

    @operation
    @override
    def parse_guide(self, content: file_alias.FileContent) -> sandbox_guide_delivery.Guide:
        """
PURPOSE:
Implements parse_guide to extract summary and step sections from file content

FRESH_REQUIREMENTS:
- Guide parsing extracts the summary from content preceding the first section heading and excludes sections whose title begins with `Lint checks`.

INHERITED_REQUIREMENTS:
- [GuideDelivery] Parsing file content extracts the summary from content preceding the first section heading and excludes sections whose title begins with `Lint checks`.

GROUNDING_ARGUMENT:
- Receives content directly as a parameter and parses the markdown text into summary and step sections, excluding sections titled with Lint checks.
"""
        ...

    @operation
    @override
    def advance_step(self, verification_passed: bool) -> Optional[tool_provider.Response]:
        """
PURPOSE:
Implements advance_step to deliver initial summary and first step, or next step content on passed verification

FRESH_REQUIREMENTS:
- When advancing a step with passed verification before any step is delivered, the response combines the guide summary and first step section content, advancing to the first section.
- When advancing a step with passed verification and subsequent steps remain, the response contains the next step section content and the step index advances to that section.
- When advancing a step with failed verification, the current step index is retained and no response is produced.
- When no guide is configured or no step sections remain, advancing a step produces no response.

INHERITED_REQUIREMENTS:
- [GuideDelivery] When verification passes on initial delivery, advancing a step produces a response containing the guide summary and first step section content.
- [GuideDelivery] When verification passes on subsequent steps and steps remain, advancing a step produces a response containing the next step section content.
- [GuideDelivery] When verification fails, advancing a step retains the current step section and produces no response.

GROUNDING_ARGUMENT:
- Receives verification_passed directly as a parameter, evaluates the current step index against remaining sections on self, advances the step state when verification passes, and formats the response content using tool_provider.Response.
"""
        ...
