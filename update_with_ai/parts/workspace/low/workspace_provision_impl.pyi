# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:39:58Z
# CHANGE: add contamination tripwire to AGENTS.md formatting grounding
# CODE_HASH: 15bb7e542505
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_provision_impl."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import workspace_provision
import workspace_registry


@singleton_type("agent_session")
class WorkspaceProvisioner(
    workspace_provision.WorkspaceProvisioner,
    InTier[AgentSessionTier],
):
    """Realizes role workspace directory provisioning, permissions, and runner deployment.

    GROUNDING:
    - Realizes workspace provisioning via recursive directory copying with chmod
      permission enforcement, zipapp runner packaging, role configuration writing,
      and safe teardown with modification verification.
    """

    @operation
    @override
    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> workspace_registry.WorkspaceDescriptor:
        """Commissions an isolated role workspace with permission boundaries.

        GROUNDING:
        - Resolves role definition and paths via WorkspaceRegistry, copies directory trees,
          sets 0o444 on upstream contracts and 0o644 on targets, synthesizes read-only test
          stubs for stub_role_deps without copying implementation files, formats AGENTS.md with
          boundary rules, contamination tripwires, and fail-stop constraints, creates bin zipapps,
          writes role metadata, and registers the workspace descriptor.
        """
        ...
