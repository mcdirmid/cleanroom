# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-09T02:19:15Z
# CHANGE: Fix bare import of agent_session
# CODE_HASH: 74dfd41a78a8
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Mapping, NewType, Protocol
from update_with_ai.parts.agent.lib.session import AgentSessionTier

# Requirements specified in template_format.pyi

TemplateText = NewType('TemplateText', str)

TemplateKey = NewType('TemplateKey', str)

FormattedText = NewType('FormattedText', str)

# Contract: TemplateFormatter protocol - formats template documents using supplied parameter bindings.
class TemplateFormatter(Protocol):
    # Contract: TemplateFormatter.format_template - formats template text with placeholders, conditionals, and loops using supplied parameters.
    def format_template(self, text: TemplateText, parameters: Mapping[TemplateKey, Any]) -> FormattedText:
        # TODO_format_template_body
        ...
