# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T03:37:01Z
# CHANGE: Align role workspace commissioning, permissions, and runner deployment contracts
# CODE_HASH: db56695ed05f
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_provision."""

from typing import Optional, Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import cleanroom_files_ext
import workspace_registry


@singleton_type("agent_session")
class WorkspaceProvisioner(InTier[AgentSessionTier], Protocol):
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
    ) -> workspace_registry.WorkspaceDescriptor:
        """Commissions an isolated role workspace with permission boundaries.

        POSTCONDITIONS:
        - MUST resolve the role definition for the requested role and directory scope.
        - MUST create the workspace directory tree including a bin directory.
        - WHEN reset is true, MUST clear stale pending work buffers in the workspace.
        - MUST copy writable target files with 0o644 permissions.
        - MUST copy upstream contract dependencies with 0o444 permissions.
        - WHEN the role definition declares stub role dependencies, MUST synthesize read-only test stubs raising NotImplementedError from companion specifications without copying real implementation files.
        - MUST package executable runner tools into the bin directory with 0o755 permissions.
        - MUST write cleanroom_files_ext.ROLE_DESCRIPTOR_FILE role configuration in the workspace root without exposing host repository paths.
        - WHEN model is specified, MUST record model execution parameters in cleanroom_files_ext.ROLE_DESCRIPTOR_FILE.
        - MUST synthesize role-tailored AGENTS.md instructions in the workspace root.
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
        - MUST copy content from src to dst.
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
        - MUST include boundary rules, contamination tripwires, terminal command restrictions, fail-stop protocols, and role-tailored workflow instructions.
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
