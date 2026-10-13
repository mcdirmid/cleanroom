# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T11:20:00Z
# CHANGE: align with HLS role agent documentation customization
# CODE_HASH: 03b932b784d1
# SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for goose_workspace."""

from dataclasses import dataclass
from typing import Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


@data_type
@dataclass(frozen=True)
class GooseWorkspaceConfinementReport:
    """Confinement report for a configured Goose role workspace.

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
class GooseWorkspaceConfigurer(InTier[AgentSessionTier], Protocol):
    """Customizes role workspace instructions and boundary constraints for Goose."""

    @operation
    def configure_role_workspace(
        self,
        workspace_dir: str,
        role_name: str,
    ) -> GooseWorkspaceConfinementReport:
        """Configures role agent documentation with boundary constraints for Goose.

        POSTCONDITIONS:
        - MUST ensure role agent documentation instructs Goose agents never to access or mutate files outside the provisioned workspace root.
        - MUST embed command execution constraints in role agent documentation restricting shell usage strictly to the five prescribed workspace binaries.
        - MUST return GooseWorkspaceConfinementReport documenting configured files.
        """
        ...
