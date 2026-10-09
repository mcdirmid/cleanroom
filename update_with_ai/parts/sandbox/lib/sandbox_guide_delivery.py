# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:19:34Z
# CHANGE: Fix sibling and cross-part imports
# CODE_HASH: b624f7f418bd
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Optional, Protocol
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier
import update_with_ai.parts.agent.lib.agent_file_alias as agent_file_alias
import update_with_ai.parts.agent.lib.agent_node_config as agent_node_config
from . import tool_provider

# Requirements specified in sandbox_guide_delivery.pyi

InitialPrimer = NewType('InitialPrimer', str)

class GuideDelivery(Protocol):
    @property
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        # TODO_guide_body
        ...

    @property
    def has_steps_remaining(self) -> bool:
        # TODO_has_steps_remaining_body
        ...

    def parse_guide(self, content: agent_file_alias.FileContent) -> agent_node_config.NodeGuide:
        # TODO_parse_guide_body
        ...

    def record_initial_primer(self, primer: InitialPrimer) -> None:
        # TODO_record_initial_primer_body
        ...

    def advance_step(self, verification_passed: bool, failure_diagnostics: agent_node_config.VerificationDiagnostic) -> Optional[tool_provider.ToolResponse]:
        # TODO_advance_step_body
        ...
