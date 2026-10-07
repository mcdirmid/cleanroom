# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: d4d289bee37e
# --- END CLEANROOM METADATA ---

# Requirements specified in sandbox_guide_delivery.pyi
from typing import NewType, Optional, Protocol
from . import tool_provider
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.agent.lib import agent_node_config

InitialPrimer = NewType("InitialPrimer", str)


class GuideDelivery(Protocol):
    @property
    def has_steps_remaining(self) -> bool: ...

    @property
    def guide(self) -> Optional[agent_node_config.NodeGuide]: ...

    def parse_guide(
        self, content: agent_file_alias.FileContent
    ) -> agent_node_config.NodeGuide: ...

    def record_initial_primer(self, primer: InitialPrimer) -> None: ...

    def advance_step(
        self,
        verification_passed: bool,
        failure_diagnostics: agent_node_config.VerificationDiagnostic,
    ) -> Optional[tool_provider.ToolResponse]: ...
