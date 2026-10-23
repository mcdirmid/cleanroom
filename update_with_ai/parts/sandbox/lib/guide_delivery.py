from __future__ import annotations
from support.lib.lifecycle import Singleton
from typing import NewType, Optional, Protocol
from update_with_ai.parts.agent.lib.session import AgentSessionTier
import update_with_ai.parts.agent.lib.file_alias as file_alias
import update_with_ai.parts.agent.lib.node_config as node_config
from . import tool_provider

# Requirements specified in guide_delivery.pyi

InitialPrimer = NewType('InitialPrimer', str)

class GuideDelivery(Singleton[AgentSessionTier], Protocol):
    # Contract: GuideDelivery.guide - exposes the configured node guide when present.
    @property
    def guide(self) -> Optional[node_config.NodeGuide]:
        # TODO_guide_body
        ...

    # Contract: GuideDelivery.has_steps_remaining - indicates whether progressive steps remain to be completed.
    @property
    def has_steps_remaining(self) -> bool:
        # TODO_has_steps_remaining_body
        ...

    # Contract: GuideDelivery.parse_guide - constructs a guide containing a summary, sequential step sections, and verification failure instructions.
    def parse_guide(self, content: file_alias.FileContent) -> node_config.NodeGuide:
        # TODO_parse_guide_body
        ...

    # Contract: GuideDelivery.record_initial_primer - records the initial primer as the first instructional content of the session.
    def record_initial_primer(self, primer: InitialPrimer) -> None:
        # TODO_record_initial_primer_body
        ...

    # Contract: GuideDelivery.advance_step - advances or preserves current milestone based on verification results.
    def advance_step(self, verification_passed: bool, failure_diagnostics: node_config.VerificationDiagnostic) -> Optional[tool_provider.ToolResponse]:
        # TODO_advance_step_body
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-09T02:19:34Z
# CHANGE: Fix sibling and cross-part imports
# --- END CLEANROOM METADATA ---
