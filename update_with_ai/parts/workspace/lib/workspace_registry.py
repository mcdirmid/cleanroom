# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:03Z
# LAST_CHANGED: 2026-10-11T05:04:08Z
# CHANGE: Reduce the interface to the declared role definition, workspace descriptor and registry protocol types, relocating the runtime implementation to the implementation module
# CODE_HASH: 7f17c633c98d
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


@dataclass(frozen=True)
class RoleDefinition:
    """Configuration definition for an autonomous development role.

    Args:
        role_name: Canonical role name.
        guide_path: Path to companion role guide.
        writable_file_patterns: Sequence of glob patterns for writable targets.
        readonly_file_patterns: Sequence of glob patterns for immutable contracts.
        feedback_role_deps: Sequence of role names receiving feedback.
        src_pattern: Primary source file path pattern with placeholders.
        role_deps: Sequence of intra-unit role dependencies.
        star_role_deps: Sequence of cross-unit star role dependencies.
        silent_role_deps: Sequence of intra-unit silent role dependencies.
        stub_role_deps: Sequence of intra-unit stub role dependencies.
        silent_cross_role_deps: Sequence of cross-unit silent role dependencies.
        active_component_types: Sequence of component classifications active for role.
        verify_template: Shell command template for verification.
        verification_success_message: Success message upon verification passing.
        persona: Human-readable role persona.
        workspace_files: Sequence of repository files copied into workspace.
        tools: Sequence of tool files copied into workspace.
        derive_build_template: Pre-sync command template for child build files.
        role_address: Optional full role target address.
        audit_tag: Optional metadata audit tag.
        task_prompt: Optional prompt template string.
        template: Optional path to template file.
        template_command: Optional shell command template for materializing starter templates.
    """

    role_name: str
    guide_path: str
    writable_file_patterns: Sequence[str]
    readonly_file_patterns: Sequence[str]
    feedback_role_deps: Sequence[str]
    src_pattern: str = ""
    role_deps: Sequence[str] = ()
    star_role_deps: Sequence[str] = ()
    silent_role_deps: Sequence[str] = ()
    stub_role_deps: Sequence[str] = ()
    silent_cross_role_deps: Sequence[str] = ()
    active_component_types: Sequence[str] = ()
    verify_template: str = ""
    verification_success_message: str = ""
    persona: str = ""
    workspace_files: Sequence[str] = ()
    tools: Sequence[str] = ()
    derive_build_template: str = ""
    role_address: Optional[str] = None
    audit_tag: Optional[str] = None
    task_prompt: Optional[str] = None
    template: str = ""
    template_command: str = ""


@dataclass(frozen=True)
class WorkspaceDescriptor:
    """Descriptor identifying an active role workspace.

    Args:
        workspace_dir: Absolute path to the role workspace directory.
        main_repository_root: Absolute path to canonical repository root.
        directory_scope: Package or directory scope for the role workspace.
        role_definition: Associated role definition configuration.
        last_sync_timestamp: Optional UTC ISO 8601 timestamp of last sync.
    """

    workspace_dir: str
    main_repository_root: str
    directory_scope: str
    role_definition: RoleDefinition
    last_sync_timestamp: Optional[str] = None


class WorkspaceRegistry(Protocol):
    """Registry resolving role specifications and tracking commissioned workspaces."""

    def discover_repository_root(self, start_dir: Optional[str] = None) -> str:
        """Discovers the canonical repository root from the filesystem environment or the current working directory.

        POSTCONDITIONS:
        - MUST resolve the canonical repository root from the filesystem environment.
        - WHEN no repository root is discoverable in the filesystem environment, MUST resolve the canonical repository root from the current working directory.
        - MUST return an absolute path to the canonical repository root.
        """
        ...

    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> RoleDefinition:
        """Resolves a role definition from a role name or qualified role address.

        POSTCONDITIONS:
        - MUST resolve role definitions from repository role configuration files or build files.
        - WHEN role_name_or_address is unqualified and dir_scope is specified, MUST resolve the role definition from the methodology configuration bound to that directory scope or its package hierarchy.
        - WHEN role_name_or_address is package-qualified, MUST resolve the role definition from the role definitions declared by the addressed package.
        - WHEN the queried role is undeclared, MUST raise KeyError.
        - WHEN feedback role dependencies are redundantly declared as role dependencies, MUST raise ValueError.
        - WHEN star role dependencies are redundantly declared as role dependencies, MUST raise ValueError.
        - WHEN a dependency is declared as both a role dependency and a silent role dependency, MUST raise ValueError.
        - WHEN an auditor role is declared as a role dependency, a star role dependency, or a feedback role dependency, MUST raise ValueError.
        - MUST return a role definition populated from the resolved declaration with its configured guide path, source pattern, and file patterns.
        """
        ...

    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[RoleDefinition]:
        """Loads and resolves all role definitions declared in the repository or bound methodology configuration.

        POSTCONDITIONS:
        - MUST parse role definition declarations from repository role configuration files or build files.
        - WHEN dir_scope is specified, MUST resolve role definitions from the methodology configuration bound to that directory scope or its package hierarchy.
        - WHEN feedback role dependencies are redundantly declared as role dependencies, MUST raise ValueError.
        - WHEN star role dependencies are redundantly declared as role dependencies, MUST raise ValueError.
        - WHEN a dependency is declared as both a role dependency and a silent role dependency, MUST raise ValueError.
        - WHEN an auditor role is declared as a role dependency, a star role dependency, or a feedback role dependency, MUST raise ValueError.
        - MUST return a role definition for every declared role.
        """
        ...

    def compute_workspace_dir(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> str:
        """Computes a sanitized role workspace directory path from a role name and directory scope.

        POSTCONDITIONS:
        - WHEN custom_dest is provided, MUST return the supplied destination directory.
        - MUST sanitize directory delimiter characters into underscores within the workspace folder name.
        - MUST return an absolute path to the role workspace directory.
        """
        ...

    def record_workspace(
        self, descriptor: WorkspaceDescriptor, repo_root: Optional[str] = None
    ) -> None:
        """Records an active workspace descriptor into the persistent workspaces registry file.

        POSTCONDITIONS:
        - MUST append or update the workspace descriptor in the persistent workspaces registry file.
        """
        ...

    def unregister_workspace(
        self, workspace_dir: str, repo_root: Optional[str] = None
    ) -> bool:
        """Removes a workspace descriptor from the persistent workspaces registry file.

        POSTCONDITIONS:
        - MUST remove the matching workspace directory entry from the persistent workspaces registry file.
        - WHEN a matching workspace directory entry is removed, MUST return true.
        """
        ...

    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[WorkspaceDescriptor]:
        """Loads all active workspace descriptors from the persistent workspaces registry file.

        POSTCONDITIONS:
        - MUST deserialize active workspace descriptors from the persistent workspaces registry file.
        - WHEN the persistent workspaces registry file is absent, MUST return an empty sequence.
        """
        ...
