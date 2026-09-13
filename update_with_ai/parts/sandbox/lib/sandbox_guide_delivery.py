from typing import Optional, Protocol
from . import tool_provider
from update_with_ai.parts.agent.lib import agent_file_alias, agent_node_config


class GuideDelivery(Protocol):
    @property
    def has_steps_remaining(self) -> bool: ...

    @property
    def guide(self) -> Optional[agent_node_config.Guide]: ...

    def parse_guide(
        self, content: agent_file_alias.FileContent
    ) -> agent_node_config.Guide: ...

    def advance_step(
        self, verification_passed: bool, failure_diagnostics: Optional[str] = None
    ) -> Optional[tool_provider.Response]: ...
