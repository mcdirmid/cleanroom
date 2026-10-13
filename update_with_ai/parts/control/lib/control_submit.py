# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-11T05:20:44Z
# CHANGE: Remove the undeclared module-level resolution wrappers so the interface holds only the declared outcome type and coordinator protocol; callers now resolve the coordinator singleton directly
# CODE_HASH: 6fe1a425f019
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence, Tuple
from update_with_ai.parts.dag.lib import dag_storage


@dataclass(frozen=True)
class SubmissionOutcome:
    """Outcome of target submission.

    Args:
        accepted: True if submission passed gating rules and was committed.
        message: Diagnostic feedback or acceptance message.
    """

    accepted: bool
    message: str


class SubmissionCoordinator(Protocol):
    """Validates submission gating rules and resolves clean nodes."""

    def submit_target(
        self,
        target_node: dag_storage.DagNode,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> SubmissionOutcome: ...

    def submit_target_file(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> SubmissionOutcome: ...

    def resolve_submit_target(
        self,
        target: str,
        repo_root: str,
        role_name: str,
        dir_scope: str = "staging",
    ) -> Tuple[Optional[str], Optional[str]]: ...

    def parse_unit_from_file_path(
        self, file_path: str, repo_root: str
    ) -> Tuple[str, str, str]: ...
