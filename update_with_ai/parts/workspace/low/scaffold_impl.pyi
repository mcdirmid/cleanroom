"""Low-level implementation specification for scaffold_impl."""

from typing import Optional, Sequence
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import cleanroom_files_ext
import roles
import scaffold


@singleton_type("agent_session")
class WorkspaceScaffolder(scaffold.WorkspaceScaffolder):
    """Realizes runner zipapp packaging, role metadata, guide synthesis, and starter skeletons.

    GROUNDING:
    - Realizes scaffold.WorkspaceScaffolder by packaging zipapps, serializing
      metadata into cleanroom_files_ext.ROLE_DESCRIPTOR_FILE, formatting AGENTS.md instructions,
      and generating starter skeletons from companion specifications (workspace_scaffold_mechanics).
    """

    @operation
    @override
    def deploy_runner_zipapps(self, bin_dir: str, role_def: Optional[roles.RoleDefinition] = None, can_blame: bool = True) -> None:
        """Packages executable runner tools into the specified bin directory.

        GROUNDING:
        - Packages self-contained executable runner zipapp wrappers into bin_dir with 0o755
          permissions, embedding the active methodology cleanroom_files_ext.CLEANROOM_ROLES_FILE manifest inside the archive,
          configuring runner import paths bounded strictly to the active role workspace
          root on sys.path without injecting arbitrary workspace subdirectories onto sys.path,
          isolating runner execution from the canonical repository root in sys.path, packaging blame
          only when role_def declares feedback capability or auditor tags, and omitting blame for
          author roles without feedback capability (workspace_scaffold_mechanics).
        """
        ...

    @operation
    @override
    def write_role_metadata(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_feedback_chars: Optional[int] = None,
        fused_roles: Optional[Sequence[str]] = None,
        common_spec_roles: Optional[Sequence[str]] = None,
    ) -> None:
        """Writes role configuration metadata in the workspace root.

        GROUNDING:
        - Writes cleanroom_files_ext.ROLE_DESCRIPTOR_FILE with role identity, directory scope,
          common_spec_roles, and optional model parameters with 0o644 permissions (workspace_scaffold_mechanics).
        """
        ...

    @operation
    @override
    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_def: roles.RoleDefinition,
        dir_scope: str,
    ) -> None:
        """Synthesizes role-tailored AGENTS.md instructions in the workspace root.

        GROUNDING:
        - Formats AGENTS.md instructions carrying role constraints, boundary rules explaining projected
          in-band metadata and main repository lifecycle timestamp authority, contamination tripwires,
          companion guide references resolved from workspace root and repository root,
          permitted in-workspace shell commands and native harness tools while mandating round resolution
          through prescribed bin/ tools (omitting blame for roles without feedback capability), round conclusion protocols instructing workers that when they have no outstanding work to do and bin/get_work does not give them more work to do (all ready targets have been resolved or only blocked targets remain), they can and must conclude the round immediately by delivering their text summary without further tool calls,
          cleanroom compilation stub isolation rules for roles declaring stub dependencies,
          prohibitions against runner binary inspection and linter hunting,
          model-contingent payload ceiling protection for local or output-constrained models while omitting it for cloud models,
          multi-phase instructions for fused roles dynamically derived from constituent role metadata (contract sources, implementation targets, verification targets), incorporating contract grounding, test authoring embedding operational postconditions into transition ctx.ensures(...) handlers and driving scenarios via transition dispatch without redundant manual assertions while forbidding assertions on uncontracted non-concerns or synthetic graph placeholders, implementation realization, and targeted reads, use-based micro-binary verification, arbiter self-audits, and defensive code pruning directives requiring pruning uncontracted dead defensive code upon coverage failure,
          fail-stop reporting protocols (clarifying test timeouts and SIGTERM as code defects rather than infrastructure failures), and tool execution instructions with 0o644 permissions (workspace_scaffold_mechanics).
        """
        ...

    @operation
    @override
    def create_missing_target_skeletons(
        self,
        workspace_dir: str,
        repo_root: str,
        dir_scope: str,
        role_def: roles.RoleDefinition,
    ) -> list[str]:
        """Creates starter skeletons for declared writable targets absent from disk.

        GROUNDING:
        - Inspects declared units and generates starter skeleton code from companion specifications
          or templates resolved both from workspace root and repository root (workspace_scaffold_mechanics).
        """
        ...

    @operation
    @override
    def write_file_with_permissions(
        self,
        dst: str,
        content: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        """Writes text content to a destination file and applies exact permissions.

        GROUNDING:
        - Realizes permission-enforced file writing (workspace_scaffold_mechanics) applying
          0o444, 0o644, 0o555, or 0o755 mode flags.
        """
        ...


def __orphan__() -> None:
    """Orphan contracts for workspace role metadata writing.

    POSTCONDITIONS:
    - MUST write role configuration metadata with 0o644 permissions.
    """
    ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-27T11:35:00Z
# LAST_CHANGED: 2026-10-29T00:40:00Z
# CHANGE: Support recording common_spec_roles in write_role_metadata
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
