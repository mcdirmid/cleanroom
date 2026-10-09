# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: e9e218b5d8cf
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_registry_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import workspace_registry


@singleton_type("agent_session")
class WorkspaceRegistry(
    workspace_registry.WorkspaceRegistry,
    InTier[AgentSessionTier],
):
    """Realizes role configuration resolution and persistent workspace registration.

    GROUNDING:
    - Realizes role resolution and persistent JSON registry storage through ancestor
      marker traversal, standard Cleanroom pattern tables, path sanitization, and atomic
      file writing with temporary staging files.
    """

    @operation
    @override
    def discover_repository_root(
        self, start_dir: Optional[str] = None
    ) -> str:
        """Discovers canonical repository root by searching ancestor directories.

        GROUNDING:
        - Traverses upward from start_dir checking for MODULE.bazel or .git files,
          falling back to ambient directory state if markers are absent.
        """
        ...

    @operation
    @override
    def resolve_role_definition(
        self, role_name_or_address: str, repo_root: Optional[str] = None
    ) -> workspace_registry.RoleDefinition:
        """Resolves role configuration matching standard roles or build rules.

        GROUNDING:
        - Parses define_role declarations from build file using AST evaluation, extracting all
          attributes and deriving patterns and audit tags, raising KeyError if unknown.
        """
        ...

    @operation
    @override
    def list_roles(
        self, repo_root: Optional[str] = None
    ) -> Sequence[workspace_registry.RoleDefinition]:
        """Loads and resolves all role definitions declared in repository build files.

        GROUNDING:
        - Parses all define_role declarations from repository build file into RoleDefinition objects.
        """
        ...

    @operation
    @override
    def compute_workspace_dir(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> str:
        """Computes sanitized path for a role workspace working tree.

        GROUNDING:
        - Sanitizes path separators into underscores and constructs workspace paths
          under the role_workspaces directory sibling to the main repository.
        """
        ...

    @operation
    @override
    def record_workspace(
        self,
        descriptor: workspace_registry.WorkspaceDescriptor,
        repo_root: Optional[str] = None,
    ) -> None:
        """Records active workspace descriptor into .cleanroom_workspaces.json.

        GROUNDING:
        - Atomically rewrites the JSON registry file using temporary file replacement.
        """
        ...

    @operation
    @override
    def unregister_workspace(
        self, workspace_dir: str, repo_root: Optional[str] = None
    ) -> bool:
        """Removes workspace descriptor from .cleanroom_workspaces.json.

        GROUNDING:
        - Filters out the matching workspace directory and atomically commits the registry.
        """
        ...

    @operation
    @override
    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[workspace_registry.WorkspaceDescriptor]:
        """Loads active workspace descriptors from .cleanroom_workspaces.json.

        GROUNDING:
        - Reads and parses JSON array from .cleanroom_workspaces.json into descriptors.
        """
        ...
