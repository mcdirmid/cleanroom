# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T11:20:00Z
# CHANGE: align with HLS role agent documentation customization
# CODE_HASH: bc414e4d6a4f
# SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for goose_workspace_impl."""

from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
import agent_session
import goose_ext
import goose_workspace


@singleton_type("agent_session")
class GooseWorkspaceConfigurer(
    goose_workspace.GooseWorkspaceConfigurer,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes workspace instruction customization and role confinement for Goose.

    GROUNDING:
    - Customizes role agent documentation conforming to goose_ext, verifies created
      instruction files, and constructs a GooseWorkspaceConfinementReport.
    """

    @operation
    @override
    def configure_role_workspace(
        self,
        workspace_dir: str,
        role_name: str,
    ) -> goose_workspace.GooseWorkspaceConfinementReport:
        """Configures role agent documentation with boundary constraints for Goose.

        GROUNDING:
        - Incorporates explicit isolation boundaries, tripwires, and restricted binary
          directives tailored for Goose into AGENTS.md in workspace_dir conforming to
          goose_ext, verifies configured files exist and are readable, and returns a
          populated goose_workspace.GooseWorkspaceConfinementReport.
        """
        ...
