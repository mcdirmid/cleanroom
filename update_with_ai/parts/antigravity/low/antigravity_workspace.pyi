# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_workspace interface low-level specification
# CODE_HASH: d0f8981d543f
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for antigravity_workspace."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from session import AgentSessionTier


@data_type
@dataclass(frozen=True)
class WorkspaceConfinementReport:
    """Captures the configured isolation state of a role workspace.

    Args:
        workspace_dir: Absolute path to the role workspace directory.
        rule_paths: Sequence of relative paths to created isolation rules.
        role_name: Name of the assigned role.
        is_confined: Confinement configuration status.
    """

    workspace_dir: str
    rule_paths: Sequence[str]
    role_name: str
    is_confined: bool


@singleton_type("agent_session")
class AntigravityWorkspaceConfigurer(InTier[AgentSessionTier], Protocol):
    """Configures Antigravity-specific isolation rules and workspace confinement."""

    @operation
    def configure_workspace(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> WorkspaceConfinementReport:
        """Establishes Antigravity isolation rules and returns a confinement report.

        POSTCONDITIONS:
        - MUST write workspace-local isolation rules into .agents/rules/ inside workspace_dir.
        - MUST write role guidance documentation referencing local runner binaries.
        - MUST return workspace confinement report containing created file paths and status.
        """
        ...
