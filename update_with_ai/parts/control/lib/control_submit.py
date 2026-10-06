# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-06T10:45:00Z
# LAST_CHANGED: 2026-10-06T10:45:00Z
# CHANGE: new file
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
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
