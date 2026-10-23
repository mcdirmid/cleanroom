"""Low-level interface specification for dsh_workspace."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton
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
class DshWorkspaceConfigurer(Singleton[AgentSessionTier], Protocol):
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
        - MUST embed command execution constraints in role agent documentation permitting in-workspace shell commands and native harness tools while mandating round resolution through prescribed bin/ tools.
        - MUST incorporate model-contingent incremental authoring directives into role agent documentation when configured for local or output-constrained models, omitting them for cloud models.
        - MUST generate Cordis overlay patch file configuring model routing, resolving declared model configuration profiles to their underlying model identifiers, and non-interactive permissions.
        - MUST return DshWorkspaceConfinementReport documenting configured files.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-20T22:12:00Z
# CHANGE: Incorporate model-contingent payload ceiling directives into dsh_workspace low-level specification
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
