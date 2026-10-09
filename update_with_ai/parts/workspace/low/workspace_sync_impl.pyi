# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:39:58Z
# CHANGE: recopy AGENTS.md with contamination tripwire in system refresh grounding
# CODE_HASH: 877d814a19cb
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_sync_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import workspace_sync
import src_metadata
import workspace_registry


@singleton_type("agent_session")
class WorkspaceSynchronizer(
    workspace_sync.WorkspaceSynchronizer,
    InTier[AgentSessionTier],
):
    """Realizes two-phase harvesting, inbound pulling, and blame flushing.

    GROUNDING:
    - Realizes bi-directional workspace sync through permission-controlled file copy,
      in-band code hash comparison, atomic file replacement, and feedback appending
      via src_metadata.
    """

    @operation
    @override
    def pull(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int:
        """Pulls updated upstream contracts and source files into role workspace.

        GROUNDING:
        - Copies newer files from main to workspace setting 0o444 on contracts,
          updates unmodified writable targets with 0o644, deletes missing files,
          and synthesizes read-only test stubs for stub_role_deps.
        """
        ...

    @operation
    @override
    def refresh_system_files(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int:
        """Refreshes non-parts system files into role workspace.

        GROUNDING:
        - Recopies build rules, tools, linters, guides, and AGENTS.md with contamination
          tripwires into workspace, and enforces read-only test stubs for stub_role_deps.
        """
        ...

    @operation
    @override
    def harvest(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
    ) -> workspace_sync.SyncResult:
        """Harvests modified targets, stamps audits, and flushes blame back to main.

        GROUNDING:
        - Validates baseline code hashes, copies validated targets, stamps audits
          via src_metadata, and flushes blame buffer entries.
        """
        ...

    @operation
    @override
    def flush_blame_buffer(
        self, workspace_dir: str, main_root: str
    ) -> Sequence[str]:
        """Flushes buffered blame feedback entries from workspace into main.

        GROUNDING:
        - Reads .cleanroom_blame_buffer.json and appends unacted feedback via src_metadata.
        """
        ...
