# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 31b65a6151b7
# --- END CLEANROOM METADATA ---

"""Template format low-level interface specification."""

from typing import Any, Mapping, NewType, Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier

TemplateText = NewType("TemplateText", str)
TemplateKey = NewType("TemplateKey", str)
FormattedText = NewType("FormattedText", str)


@singleton_type("agent_session")
class TemplateFormatter(InTier[AgentSessionTier], Protocol):
    """Formats template documents using supplied parameter bindings."""

    @operation
    def format_template(self, text: TemplateText, parameters: Mapping[TemplateKey, Any]) -> FormattedText:
        """Formats template text using supplied parameters to produce formatted text.

        Args:
            text: The template text containing placeholders, conditionals, and loops.
            parameters: Mapping of parameter keys to replacement values or collections.

        Returns:
            The formatted text resulting from template evaluation.

        POSTCONDITIONS:
        - MUST substitute parameter placeholders matching bound keys with their corresponding string representations.
        - MUST preserve parameter placeholders whose keys are absent from the supplied parameters as unrendered placeholders.
        - WHEN a condition key in parameters is truthy or absent, MUST include enclosed conditional content.
        - WHEN a condition key in parameters is falsy, MUST omit enclosed conditional content.
        - WHEN a collection key in parameters resolves to a sequence, MUST repeat loop blocks binding loop item variables.
        """
        ...
