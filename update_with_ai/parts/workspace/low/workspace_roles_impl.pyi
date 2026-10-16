# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:45:00Z
# CHANGE: Define workspace_roles_impl low-level specification
# CODE_HASH: a6441977c532
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_roles_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import workspace_roles


@singleton_type("agent_session")
class RoleResolver(
    workspace_roles.RoleResolver,
    InTier[AgentSessionTier],
):
    """Realizes role configuration parsing, constraint verification, and methodology resolution.

    GROUNDING:
    - Parses role declarations from declarative TOML files and build file AST structures, enforcing
      dependency declaration constraints, qualifying addresses, and caching parsed definitions.
    """

    @operation
    @override
    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> workspace_roles.RoleDefinition:
        """Resolves a role definition from a role name or qualified role address.

        GROUNDING:
        - Evaluates repository role declarations via TOML parsing or build file AST evaluation,
          discovering package methodology configurations across directory scopes, enforcing dependency
          validation rules, and qualifying returned definitions.
        """
        ...

    @operation
    @override
    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[workspace_roles.RoleDefinition]:
        """Loads and resolves all role definitions declared in the repository or bound methodology configuration.

        GROUNDING:
        - Evaluates all declared role definitions from repository TOML files or build file AST structures,
          validating constraints and returning resolved definitions.
        """
        ...
