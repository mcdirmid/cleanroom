from typing import Any, Mapping, Protocol
from framework import operation, singleton_type

@singleton_type('agent_session')
class TemplateFormatter(Protocol):
    """
PURPOSE:
Agent session service that formats template documents using supplied parameter bindings
"""

    @operation
    def format_template(self, text: str, parameters: Mapping[str, Any]) -> str:
        """
PURPOSE:
Formats template text using supplied parameters to produce formatted text

FRESH_REQUIREMENTS:
- The template formatter formats template text using parameters to produce formatted text.
- Substitutes parameter placeholders matching bound keys with their corresponding string representations.
- Preserves parameter placeholders whose keys are absent from the supplied parameters as unrendered placeholders.
- Evaluates conditional blocks and line-suffix conditionals based on the truthiness of their condition keys in the parameters, including enclosed content when true or absent from parameters and omitting content when false.
- Repeats loop blocks and line-suffix loops across items when the collection key resolves to a sequence in the parameters, binding loop item variables during repetition.
"""
        ...
