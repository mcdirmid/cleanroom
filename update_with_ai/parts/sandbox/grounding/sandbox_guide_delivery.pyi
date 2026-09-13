from typing import Optional, Protocol
from framework import operation, singleton_type
import agent_file_alias
import agent_node_config
import tool_provider

@singleton_type('agent_session')
class GuideDelivery(Protocol):
    """
PURPOSE:
Defined as an agent session service that delivers step-by-step instructions from a guide

FRESH_REQUIREMENTS:
- Steps remaining indicates whether further step sections remain to be completed.
"""

    @property
    def has_steps_remaining(self) -> bool:
        """
PURPOSE:
Exposes whether progressive step sections remain to be completed
"""
        ...

    @property
    def guide(self) -> Optional[agent_node_config.Guide]:
        """
PURPOSE:
Exposes the configured guide for the session
"""
        ...

    @operation
    def parse_guide(self, content: agent_file_alias.FileContent) -> agent_node_config.Guide:
        """
PURPOSE:
Parses file content into a guide
"""
        ...

    @operation
    def advance_step(self, verification_passed: bool, failure_diagnostics: Optional[str]=None) -> Optional[tool_provider.Response]:
        """
PURPOSE:
Advances to the next step section if verification passed, or retains the current step and reports failure diagnostics

FRESH_REQUIREMENTS:
- Advancing step delivers instructional text when verification passes, or retains the current milestone and reports failure diagnostics alongside verification failure instructions when verification fails.
"""
        ...
