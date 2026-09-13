from typing import Optional, Protocol
from . import file_alias, node_config, tool_provider

class GuideDelivery(Protocol):
    @property
    def has_steps_remaining(self) -> bool: ...

    @property
    def guide(self) -> Optional[node_config.Guide]: ...

    def parse_guide(self, content: file_alias.FileContent) -> node_config.Guide: ...

    def advance_step(
        self, verification_passed: bool, failure_diagnostics: Optional[str] = None
    ) -> Optional[tool_provider.Response]: ...
