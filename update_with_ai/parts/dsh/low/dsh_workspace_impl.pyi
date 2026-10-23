"""Low-level implementation specification for dsh_workspace_impl."""

from typing import Optional
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton
import session as agent_session
import dsh_ext
import dsh_workspace


@singleton_type("agent_session")
class DshWorkspaceConfigurer(dsh_workspace.DshWorkspaceConfigurer):
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
        - Incorporates explicit isolation boundaries, permitted in-workspace shell commands and
          native harness tools, auditor rules (mandating in-workspace code and change header inspection while prohibiting code edits), check_files ground truth mandates, continuous tool execution rules, round conclusion protocols directing workers to stop immediately without tool calls when all ready targets are resolved or only blocked targets remain, and model-contingent payload ceiling protection directives (mandating staged incremental writing for local or output-constrained models while omitting it for cloud models) into AGENTS.md,
          writes Cordis patch into .cleanroom/dsh_patch.yml conforming to dsh_ext (resolving declared model profile names stripping model namespace prefixes against model configuration definitions discovered in workspace ancestors, user configuration, or repository root, mapping local MLX providers to oMLX endpoints, setting high reasoning effort for DeepSeek providers, and disabling unneeded tool plugins including workflow, subagent, office skills, web, user question, jobs, and goal tools), verifies configured
          files exist, and returns a populated dsh_workspace.DshWorkspaceConfinementReport.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-20T22:12:00Z
# CHANGE: Document model-contingent payload ceiling protection in customized AGENTS.md instructions
# SPEC_QA_AUDIT: 2026-10-19T22:33:00Z
# --- END CLEANROOM METADATA ---
