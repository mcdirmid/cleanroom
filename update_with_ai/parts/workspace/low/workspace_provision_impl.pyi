# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: a7c0a99e9fcf
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
          sets 0o444 on upstream contracts and 0o644 on targets, creates bin zipapps,
          writes role metadata, and registers the workspace descriptor.
        """
        ...

    @operation
    @override
    def decommission(
        self,
        role_name_or_dir: str,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        force: bool = False,
    ) -> bool:
        """Decommissions and safely removes an active role workspace.

        GROUNDING:
        - Checks for unharvested modifications across writable targets, aborts if dirty
          unless force is true, unregisters descriptor, and removes tree with shutil.rmtree.
        """
        ...
