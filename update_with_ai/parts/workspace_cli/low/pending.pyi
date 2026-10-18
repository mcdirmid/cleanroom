# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T17:40:00Z
# CHANGE: Define pending interface specification
# CODE_HASH: 52ed1a94f090
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for pending."""

from typing import Optional, Protocol, Sequence
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from session import AgentSessionTier
import cleanroom_files_ext


@singleton_type("agent_session")
class WorkspacePendingManager(InTier[AgentSessionTier], Protocol):
    """Tracks active pending tasks and buffer persistence within role workspaces."""

    @operation
    def get_pending_work(self, workspace_dir: str) -> Sequence[str]:
        """Reads target paths from local pending work buffer.

        POSTCONDITIONS:
        - When buffer file is present, MUST return list of pending target paths.
        - When buffer file is missing, MUST return an empty sequence.
        """
        ...

    @operation
    def clear_pending_work(self, workspace_dir: str) -> None:
        """Removes local pending work buffer file if present.

        POSTCONDITIONS:
        - MUST delete pending work file designated by cleanroom_files_ext from workspace directory.
        """
        ...

    @operation
    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        """Records pending target paths into local buffer file.

        POSTCONDITIONS:
        - When targets sequence is empty, MUST clear pending work buffer.
        - When targets sequence is non-empty, MUST serialize targets to pending work file designated by cleanroom_files_ext.
        """
        ...

    @operation
    def remove_pending_target(self, workspace_dir: str, submitted_target: str) -> None:
        """Removes a submitted target from local pending work buffer.

        POSTCONDITIONS:
        - MUST remove matching target from pending work file designated by cleanroom_files_ext.
        """
        ...

    @operation
    def is_pending_target_dirty(
        self,
        target_path: str,
        workspace_dir: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> bool:
        """Checks whether a pending target file is still dirty.

        POSTCONDITIONS:
        - MUST check in-band metadata dirty status across local workspace and main repository.
        - MUST resolve canonical lifecycle metadata from main repository when available.
        - MUST evaluate feedback role dependencies and star role dependencies as implicit role dependencies.
        - WHEN any star role dependency is modified, MUST return true.
        - MUST return true if target is missing, marked dirty, or has unacted feedback.
        """
        ...
