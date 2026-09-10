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
    def advance_step(self, verification_passed: bool, failure_diagnostics: Optional[str]=None) -> Optional[tool_provider.Response]:
        """
PURPOSE:
Implements advance_step to deliver initial summary alone, subsequent step content with summary, or failure diagnostics with current step

FRESH_REQUIREMENTS:
- When advancing a step with passed verification, if no steps have been delivered yet, the guide delivery emits a response containing the guide summary alone without delivering a step section.
- When advancing a step with passed verification, if steps have already been delivered and further step sections remain, the guide delivery emits a response presenting the guide summary above the next step section content and advances its index to that section.
- When advancing a step with failed verification, if no step section has been delivered yet, the guide delivery retains its index and emits a response combining the guide summary and failure diagnostics.
- When advancing a step with failed verification, if a step section is currently active, the guide delivery retains the current step index without advancement and emits a response combining the guide summary, the current step section content, and the failure diagnostics.
- When no guide is configured or no step sections remain, the guide delivery indicates that no steps remain and advancing produces no response.

INHERITED_REQUIREMENTS:
- [GuideDelivery] When advancing a step with passed verification on initial delivery, the response contains the guide summary alone.
- [GuideDelivery] When advancing a step with passed verification on subsequent steps and steps remain, the response presents the guide summary above the next step section content.
- [GuideDelivery] When advancing a step with failed verification, advancing retains the current step section and reports the failure diagnostics.

GROUNDING_ARGUMENT:
- Receives verification_passed and failure_diagnostics directly as parameters, evaluates the active delivery state against remaining sections on self, advances or retains the step state based on verification, and formats the response content using tool_provider.Response.
"""
        ...
