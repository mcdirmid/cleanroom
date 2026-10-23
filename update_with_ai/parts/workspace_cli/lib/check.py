from __future__ import annotations
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton
from typing import Optional, Protocol


# Contract: WorkspaceChecker protocol executes work discovery and file verification for role workspaces.
class WorkspaceChecker(Singleton[AgentSessionTier], Protocol):
    """Executes work discovery and file verification for role workspaces."""

    # Contract: Evaluates dirty work in local workspace and prints ready tasks, respecting batch_size and max_feedback_chars.
    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> int: ...

    # Contract: Executes role-specific verification checks, linters, and type checking for targets, regenerating missing files if regenerable.
    def run_check_files(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int: ...

    # Contract: Returns True if the target has been checked via check_files since its last modification.
    def is_checked_since_modification(
        self,
        ws_root: str,
        target_path: str,
    ) -> bool: ...

    # Contract: Records file verification execution and content hash in .cleanroom/.last_check_files.json.
    def record_check_executed(
        self,
        ws_root: str,
        target_path: str,
        passed: bool,
    ) -> None: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:25:00Z
# CHANGE: Define check interface
# --- END CLEANROOM METADATA ---
