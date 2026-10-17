# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_workspace interface low-level specification
# CODE_HASH: 9b74bc618e72
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for dsh_workspace."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from session import AgentSessionTier


@data_type
@dataclass(frozen=True)
class DshWorkspaceConfinementReport:
    """Confinement report for a configured DeepSeek Harness role workspace.

    Args:
        workspace_dir: Absolute path to the role workspace directory.
        role_name: Assigned Cleanroom role identifier.
        configured_files: Sequence of created or modified boundary file paths.
        status: Confinement status indicator string.
    """

    workspace_dir: str
    role_name: str
    configured_files: Sequence[str] = ()
    status: str = "configured"


@singleton_type("agent_session")
class DshWorkspaceConfigurer(InTier[AgentSessionTier], Protocol):
    """Customizes role workspace instructions, boundary constraints, and overlay patches for DeepSeek Harness."""

    @operation
    def configure_role_workspace(
        self,
        workspace_dir: str,
        role_name: str,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> DshWorkspaceConfinementReport:
        """Configures role agent documentation and Cordis overlay patch for DeepSeek Harness.

        POSTCONDITIONS:
        - MUST ensure role agent documentation instructs DeepSeek Harness agents never to access or mutate files outside the provisioned workspace root.
        - MUST embed command execution constraints in role agent documentation restricting shell usage strictly to the five prescribed workspace binaries.
        - MUST generate Cordis overlay patch file configuring model routing, resolving declared model configuration profiles to their underlying model identifiers, and non-interactive permissions.
        - MUST return DshWorkspaceConfinementReport documenting configured files.
        """
        ...
