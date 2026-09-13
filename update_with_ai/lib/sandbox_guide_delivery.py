from typing import Optional, Protocol
from . import agent_file_alias, agent_node_config, tool_provider

class GuideDelivery(Protocol):
    @property
    def has_steps_remaining(self) -> bool: ...

    @property
    def guide(self) -> Optional[agent_node_config.Guide]: ...

    def parse_guide(self, content: agent_file_alias.FileContent) -> agent_node_config.Guide: ...

    def advance_step(
        self, verification_passed: bool, failure_diagnostics: Optional[str] = None
    ) -> Optional[tool_provider.Response]: ...
