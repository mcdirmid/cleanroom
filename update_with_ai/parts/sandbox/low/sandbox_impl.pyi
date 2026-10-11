# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:03Z
# LAST_CHANGED: 2026-10-11T03:26:02Z
# CHANGE: State modification reporting as delegation to the edit manager
# CODE_HASH: 863c55d9447e
# SPEC_QA_AUDIT: 2026-10-11T22:09:03Z
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
    - Reports workspace file modification status for the session by delegating all modification
      state determination to EditManager, holding no modification state of its own.
    """

    @property
    @override
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session.

        GROUNDING:
        - Delegates to EditManager.has_modifications from sandbox_file_editor, which reports
          whether workspace file contents differ from their in-band code hashes.
        """
        ...
