# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:45:00Z
# CHANGE: Define workspace_roles interface component
# CODE_HASH: 63c2557ee0fe
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_roles."""

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


class RoleResolver(Protocol):
    """Resolver loading role configurations and validating declaration rules."""

    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> RoleDefinition:
        """Resolves a role definition from a role name or qualified role address."""
        ...

    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[RoleDefinition]:
        """Loads and resolves all role definitions declared in the repository or bound methodology configuration."""
        ...
