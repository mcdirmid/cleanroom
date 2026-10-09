# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-06T12:35:00Z
# CHANGE: add grounding sections
# CODE_HASH: 57b757257994
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Sandbox implementation low-level specification."""

from framework import override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import sandbox
import sandbox_file_editor


@singleton_type("agent_session")
class Sandbox(sandbox.Sandbox, InTier[AgentSessionTier]):
    """Realizes session file modification tracking.

    GROUNDING:
    - Coordinates change tracking by querying file diffs from EditManager within the agent session tier.
    """

    @property
    @override
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session.

        GROUNDING:
        - Grounded via EditManager.has_modifications from sandbox_file_editor,
          querying whether diff-based file mutations were recorded.
        """
        ...
