"""Low-level interface specification for sync."""

from dataclasses import dataclass
from typing import Protocol, Sequence
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import cleanroom_files_ext


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
class WorkspaceSynchronizer(Singleton[AgentSessionTier], Protocol):
    """Transfers files and in-band metadata between canonical repositories and role workspaces."""

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
        - MUST copy newer upstream files into the role workspace.
        - MUST preserve 0o444 read-only permissions on upstream contracts.
        - WHEN copying files into the role workspace, MUST project metadata headers to only retain CHANGE and FEEDBACK fields, computing and injecting an ephemeral CODE_HASH on writable targets while omitting LAST_CLEANED, LAST_CHANGED, and audit tags.
        - WHEN the role declares stub role dependencies, MUST synchronize read-only test
          stubs from companion specifications without copying implementation code.
        - MUST return the count of pulled files.
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
        """Refreshes non-parts system files from main into role workspace.

        POSTCONDITIONS:
        - MUST refresh non-parts system files from the canonical main repository into the
          role workspace.
        - MUST leave writable targets unmodified.
        - MUST enforce read-only test stub integrity for stub role dependencies.
        - MUST scope workspace tool configurations to the role workspace boundaries.
        - MUST return the count of refreshed files.
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
        - MUST scan writable target files to identify modified content against ephemeral code hashes.
        - MUST validate canonical main target baselines against workspace baseline hashes
          before committing harvested files.
        - MUST copy validated target files into the canonical main repository, stripping ephemeral code hashes.
        - MUST update in-band clean timestamps on committed targets.
        - WHEN the role is an auditor role, MUST stamp role audits on verified targets in
          the canonical main repository.
        - MUST flush buffered blame feedback into culprit files in the canonical main
          repository.
        """
        ...

    @operation
    def flush_blame_buffer(
        self, workspace_dir: str, main_root: str
    ) -> Sequence[str]:
        """Flushes buffered blame feedback entries from workspace into main.

        POSTCONDITIONS:
        - WHEN the role workspace contains the blame buffer file designated by cleanroom_files_ext,
          MUST parse buffered blame entries.
        - MUST append unacted feedback to culprit files in the canonical main repository.
        - MUST remove the blame buffer file designated by cleanroom_files_ext upon successful
          application.
        - MUST return the sequence of culprit file paths receiving appended feedback.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T03:37:02Z
# CHANGE: Align synchronizer typing and test stub integrity; remove unused import
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
