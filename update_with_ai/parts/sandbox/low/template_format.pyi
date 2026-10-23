"""Template format low-level interface specification."""

from typing import Any, Mapping, NewType, Protocol
from support.lib.framework import operation, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier

TemplateText = NewType("TemplateText", str)
TemplateKey = NewType("TemplateKey", str)
FormattedText = NewType("FormattedText", str)


@singleton_type("agent_session")
class TemplateFormatter(Singleton[AgentSessionTier], Protocol):
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
        - MUST substitute parameter placeholders matching bound keys with their corresponding string representations, recognizing angle-bracket placeholders (<parameter.path>) defined by commonmark_ext.
        - MUST preserve parameter placeholders whose keys are absent from the supplied parameters as unrendered placeholders.
        - WHEN a condition key in parameters is truthy or absent, MUST include enclosed conditional content.
        - WHEN a condition key in parameters is falsy, MUST omit enclosed conditional content.
        - WHEN a collection key in parameters resolves to a sequence, MUST repeat loop blocks and line-suffix loops binding loop item variables.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T03:44:40Z
# CHANGE: Contract repetition of line-suffix loops alongside loop blocks
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
