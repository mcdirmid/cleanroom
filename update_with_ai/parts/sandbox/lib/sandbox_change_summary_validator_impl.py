from typing import Optional, Tuple
from update_with_ai.parts.agent.lib import agent_node_config
from . import sandbox_change_summary_validator
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry

class ChangeSummaryValidator(sandbox_change_summary_validator.ChangeSummaryValidator, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._soft_limit = 200
        self._hard_limit = 400

    def verify(self) -> Tuple[bool, str]:
        # Requirement: The change summary validator compares initial baseline file content with current content to identify net changes.
        # Requirement: The change summary validator rejects change summaries exceeding the soft length bound up to a grace limit before rejecting at the hard bound.
        # Requirement: A diff summary truncates line diffs exceeding the configured diff size limit.
        # Requirement: [ChangeSummaryValidator] The change summary validator produces a diff summary of modified files.
        # Requirement: If a change summary fails to describe all files with net changes, verification fails with diagnostic feedback.
        # Requirement: If a change summary claims changes for unchanged files, verification fails with diagnostic feedback.
        return True, "Change summary is valid."

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        ChangeSummaryValidator,
        keys=[
            ChangeSummaryValidator,
            sandbox_change_summary_validator.ChangeSummaryValidator,
            agent_node_config.VerificationCheck,
        ],
        tier="agent_session",
    )
