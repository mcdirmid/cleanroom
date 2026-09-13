from typing import Optional, Protocol
from . import file_alias, node_config, tool_provider

StepSection = node_config.StepSection
Guide = node_config.Guide


class GuideDelivery(Protocol):
    @property
    def has_steps_remaining(self) -> bool: ...

    @property
    def guide(self) -> Optional[Guide]: ...

    def parse_guide(self, content: file_alias.FileContent) -> Guide: ...

    def advance_step(
        self, verification_passed: bool, failure_diagnostics: Optional[str] = None
    ) -> Optional[tool_provider.Response]: ...
