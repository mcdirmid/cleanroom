"""Low-level interface specification for provision."""

from typing import Optional, Protocol
from support.lib.framework import operation, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import cleanroom_files_ext
import role_registry


@singleton_type("agent_session")
class WorkspaceProvisioner(Singleton[AgentSessionTier], Protocol):
    """Service creating and configuring isolated, directory-scoped role workspaces."""

    @operation
    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        reset: bool = False,
        model: Optional[str] = None,
    ) -> role_registry.WorkspaceDescriptor:
        """Commissions an isolated role workspace with permission boundaries.

        POSTCONDITIONS:
        - MUST resolve the role definition for the requested role and directory scope, and resolve the bound methodology package declared by the target scope's cleanroom_files_ext.CLEANROOM_CONFIG_FILE.
        - MUST create the workspace directory tree including a bin directory, copying only target scope files and promoted assets belonging to the bound methodology package, while strictly ignoring unbound repository root directories.
        - WHEN reset is true, MUST clear stale pending work buffers in the workspace.
        - MUST copy writable target files with 0o644 permissions, projecting metadata headers to only retain CHANGE and FEEDBACK fields with an ephemeral CODE_HASH while omitting LAST_CLEANED, LAST_CHANGED, and audit tags.
        - MUST copy upstream contract dependencies with 0o444 permissions, projecting metadata headers to only retain CHANGE and FEEDBACK fields while omitting LAST_CLEANED, LAST_CHANGED, and audit tags.
        - WHEN the role definition declares stub role dependencies, MUST synthesize read-only test stubs raising NotImplementedError from companion specifications without copying real implementation files.
        - MUST package executable runner tools into the bin directory with 0o755 permissions.
        - MUST write cleanroom_files_ext.ROLE_DESCRIPTOR_FILE role configuration in the workspace root without exposing host repository paths.
        - WHEN model is specified, MUST record model execution parameters in cleanroom_files_ext.ROLE_DESCRIPTOR_FILE.
        - MUST synthesize role-tailored AGENTS.md instructions in the workspace root.
        - MUST configure test runner isolation in workspace configuration files restricting test discovery exclusively to the local workspace.
        - MUST record the created workspace descriptor in the persistent registry.
        - MUST return a workspace descriptor for the newly created workspace directory.
        """
        ...

    @operation
    def copy_file_with_permissions(
        self,
        src: str,
        dst: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        """Copies a file and applies exact read-only, writable, or executable permissions.

        POSTCONDITIONS:
        - MUST copy content from src to dst using buffered chunk streaming.
        - WHEN readonly is true, MUST set permissions to 0o444.
        - WHEN executable is true and readonly is true, MUST set permissions to 0o555.
        - WHEN executable is true and readonly is false, MUST set permissions to 0o755.
        - WHEN neither is true, MUST set permissions to 0o644.
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

    @operation
    def deploy_runner_zipapps(self, bin_dir: str) -> None:
        """Packages executable runner tools into the specified bin directory.

        POSTCONDITIONS:
        - MUST create bin_dir if absent.
        - MUST package runner zipapps for get_work, check_files, submit, blame, feedback, and fail tools with executable permissions (0o755).
        - MUST remove stale coverage script if present in bin_dir.
        """
        ...

    @operation
    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> None:
        """Synthesizes role-tailored AGENTS.md instructions in the workspace root.

        POSTCONDITIONS:
        - MUST resolve the role definition for role_name.
        - MUST write AGENTS.md in workspace_dir with 0o644 permissions.
        - MUST include boundary rules, contamination tripwires, permitted in-workspace shell commands and native harness tools while mandating round resolution through prescribed bin/ tools, fail-stop protocols, and role-tailored workflow instructions.
        """
        ...

    @operation
    def sync_test_stubs(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Synchronizes read-only test stubs for stub role dependencies.

        POSTCONDITIONS:
        - MUST resolve the role definition for role_name.
        - WHEN role declares stub role dependencies, MUST synthesize read-only test stubs raising NotImplementedError from companion specifications without copying real implementation files.
        - MUST delete orphaned stubs whose companion specifications no longer exist.
        - MUST return the count of synchronized or updated stub files.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T13:50:00Z
# LAST_CHANGED: 2026-10-22T13:50:00Z
# CHANGE: Restrict workspace provisioning exclusively to target scope and bound methodology package assets
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
