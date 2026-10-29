"""Low-level interface specification for scaffold."""

from typing import Optional, Protocol, Sequence
from support.lib.framework import operation, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import cleanroom_files_ext
import roles


@singleton_type("agent_session")
class WorkspaceScaffolder(Singleton[AgentSessionTier], Protocol):
    """Service scaffolding runner tools, metadata, instructions, and target skeletons."""

    @operation
    def deploy_runner_zipapps(self, bin_dir: str, role_def: Optional[roles.RoleDefinition] = None, can_blame: bool = True) -> None:
        """Packages executable runner tools into the specified bin directory.

        POSTCONDITIONS:
        - MUST create bin_dir if absent.
        - MUST package runner zipapps for get_work, check_files, submit, and fail tools with executable permissions (0o755).
        - WHEN can_blame is True or role_def declares feedback capability or auditor tags, MUST package runner zipapps for blame and feedback tools.
        - WHEN can_blame is False or role_def lacks feedback capability, MUST omit blame and feedback tools and remove any existing blame or feedback executables.
        - WHEN role_def declares fused_roles, MUST package use-based micro-binaries (verify_<constituent_role> for each constituent role declared in fused_roles) with executable permissions (0o755).
        - MUST remove stale coverage script if present in bin_dir.
        """
        ...

    @operation
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

        POSTCONDITIONS:
        - MUST write cleanroom_files_ext.ROLE_DESCRIPTOR_FILE in workspace_dir with 0o644 permissions.
        - MUST record role identity, directory scope, and optional model profile configuration without exposing host repository paths.
        - WHEN fused_roles is specified, MUST record fused_roles sequence in role metadata.
        - WHEN common_spec_roles is specified, MUST record common_spec_roles sequence in role metadata.
        """
        ...

    @operation
    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_def: roles.RoleDefinition,
        dir_scope: str,
    ) -> None:
        """Synthesizes role-tailored AGENTS.md instructions in the workspace root.

        POSTCONDITIONS:
        - MUST write AGENTS.md in workspace_dir with 0o644 permissions.
        - MUST include boundary rules, contamination tripwires, permitted in-workspace shell commands and native harness tools while mandating round resolution through prescribed bin/ tools (omitting blame for roles without feedback capability), cleanroom compilation stub isolation rules for roles declaring stub dependencies, fail-stop protocols, role-tailored workflow instructions, and model-contingent payload ceiling protection for local or output-constrained models while omitting it for cloud models.
        - WHEN role_def declares fused_roles, MUST format multi-phase instructions incorporating use-based micro-binary verification, QA arbiter contract fidelity audits, coverage arbiter semantic closure audits requiring pruning uncontracted dead defensive code upon coverage failure, and an atomic completion protocol omitting per-target submissions.
        """
        ...

    @operation
    def create_missing_target_skeletons(
        self,
        workspace_dir: str,
        repo_root: str,
        dir_scope: str,
        role_def: roles.RoleDefinition,
    ) -> list[str]:
        """Creates starter skeletons for declared writable targets absent from disk.

        POSTCONDITIONS:
        - MUST generate starter skeleton files for missing targets matching role_def.writable_file_patterns.
        - MUST return relative paths of newly created skeleton files.
        """
        ...

    @operation
    def write_file_with_permissions(
        self,
        dst: str,
        content: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        """Writes text content to a destination file and applies exact permissions.

        POSTCONDITIONS:
        - MUST write content to dst with UTF-8 encoding.
        - WHEN readonly is true, MUST set permissions to 0o444.
        - WHEN executable is true and readonly is true, MUST set permissions to 0o555.
        - WHEN executable is true and readonly is false, MUST set permissions to 0o755.
        - WHEN neither is true, MUST set permissions to 0o644.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-27T11:35:00Z
# LAST_CHANGED: 2026-10-29T15:30:00Z
# CHANGE: Derive fused role micro-binaries strictly and dynamically from constituent role names with zero hardcoded role names
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
