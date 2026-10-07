# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 4a011171eed3
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_sync."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


@data_type
@dataclass(frozen=True)
class SyncResult:
    """Outcome of a synchronization operation.

    Args:
        pulled_files: Number of files pulled from main to workspace.
        harvested_files: Number of files harvested from workspace to main.
        stamped_audits: Sequence of target paths with attested audits.
        flushed_blames: Sequence of culprit paths receiving blame feedback.
    """

    pulled_files: int
    harvested_files: int
    stamped_audits: Sequence[str]
    flushed_blames: Sequence[str]


@singleton_type("agent_session")
class WorkspaceSynchronizer(InTier[AgentSessionTier], Protocol):
    """Coordinates bi-directional synchronization and blame flushing."""

    @operation
    def pull(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int:
        """Pulls updated upstream contracts and source files into role workspace.

        POSTCONDITIONS:
        - MUST copy newer upstream files into workspace.
        - MUST preserve 0o444 read-only permissions on upstream contracts.
        - MUST return count of pulled files.
        """
        ...

    @operation
    def refresh_system_files(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int:
        """Refreshes non-parts build files, tools, guides, and linters into workspace.

        POSTCONDITIONS:
        - MUST recopy system tools, linters, and guides without modifying targets.
        - MUST return count of refreshed files.
        """
        ...

    @operation
    def harvest(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
    ) -> SyncResult:
        """Harvests modified targets, stamps audits, and flushes blame back to main.

        POSTCONDITIONS:
        - MUST validate main target baselines before writing harvested files.
        - MUST commit validated target files and update in-band timestamps.
        - When role is an auditor role, MUST stamp role audits on verified targets.
        - MUST flush buffered blame feedback into culprit files in main.
        - MUST return SyncResult summarizing operations.
        """
        ...

    @operation
    def flush_blame_buffer(
        self, workspace_dir: str, main_root: str
    ) -> Sequence[str]:
        """Flushes buffered blame feedback entries from workspace into main.

        POSTCONDITIONS:
        - MUST read .cleanroom_blame_buffer.json if present.
        - MUST append unacted feedback to culprit files in main repository.
        - MUST remove .cleanroom_blame_buffer.json upon successful application.
        - MUST return sequence of updated culprit file paths.
        """
        ...
