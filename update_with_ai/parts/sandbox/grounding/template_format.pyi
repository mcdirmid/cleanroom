from typing import Any, Mapping, Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


@singleton_type("agent_session")
class TemplateFormatter(InTier[AgentSessionTier], Protocol):
    """Formats template documents using supplied parameter bindings."""

    @operation
    def format_template(self, text: str, parameters: Mapping[str, Any]) -> str:
        """Formats template text using supplied parameters to produce formatted text.

        Args:
            text: The template text containing placeholders, conditionals, and loops.
            parameters: Mapping of parameter keys to replacement values or collections.

        Returns:
            The formatted text resulting from template evaluation.

        REQUIREMENTS:
        - MUST substitute parameter placeholders matching bound keys with their corresponding string representations.
        - MUST preserve parameter placeholders whose keys are absent from the supplied parameters as unrendered placeholders.
        - WHEN a condition key in parameters is truthy or absent, MUST include enclosed conditional content.
        - WHEN a condition key in parameters is falsy, MUST omit enclosed conditional content.
        - WHEN a collection key in parameters resolves to a sequence, MUST repeat loop blocks binding loop item variables.

        GROUNDING_PROVISIONS:
        - action("format_template", str): Formats template text using parameters to satisfy requirements 1, 2, 3, 4, and 5.
        """
        ...
