# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T17:45:00Z
# CHANGE: align dsh_workspace_impl low spec with auditor code inspection and terminal command restrictions
# CODE_HASH: 5854fe785540
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for dsh_workspace_impl."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
import agent_session
import dsh_ext
import dsh_workspace


@singleton_type("agent_session")
class DshWorkspaceConfigurer(
    dsh_workspace.DshWorkspaceConfigurer,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes workspace instruction customization and overlay patch generation for DeepSeek Harness.

    GROUNDING:
    - Customizes role agent documentation and generates Cordis overlay patch conforming
      to dsh_ext, verifies created files, and constructs a DshWorkspaceConfinementReport.
    """

    @operation
    @override
    def configure_role_workspace(
        self,
        workspace_dir: str,
        role_name: str,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> dsh_workspace.DshWorkspaceConfinementReport:
        """Configures role agent documentation and Cordis overlay patch for DeepSeek Harness.

        GROUNDING:
        - Incorporates explicit isolation boundaries, tripwires, restricted binary
          directives, and auditor rules (mandating in-workspace code and change header inspection while prohibiting code edits) tailored for DeepSeek Harness into AGENTS.md,
          writes Cordis patch into .cleanroom/dsh_patch.yml conforming to dsh_ext (resolving declared model profile names stripping model namespace prefixes against model configuration definitions discovered in workspace ancestors or repository root, setting high reasoning effort for DeepSeek providers, and disabling the todo plugin), verifies configured
          files exist, and returns a populated dsh_workspace.DshWorkspaceConfinementReport.
        """
        ...
