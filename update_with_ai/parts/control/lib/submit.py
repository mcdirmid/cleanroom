from __future__ import annotations
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton
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


class SubmissionCoordinator(Singleton[AgentSessionTier], Protocol):
    """Validates submission gating rules and resolves clean nodes."""

    # Contract: Submits target node after validating gating rules; rejects on failed verification, uncleaned in-batch dependency, summary/modification mismatch, or unaddressed feedback; marks node clean in graph storage.
    def submit_target(
        self,
        target_node: dag_storage.DagNode,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> SubmissionOutcome: ...

    # Contract: Submits file target after validating file gating rules (auditor verification targets, producer write permissions and directory scope, modification/summary consistency) and updates metadata.
    def submit_target_file(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> SubmissionOutcome: ...

    # Contract: Resolves target specification to canonical or workspace file path and unit name.
    def resolve_submit_target(
        self,
        target: str,
        repo_root: str,
        role_name: str,
        dir_scope: str = "staging",
    ) -> Tuple[Optional[str], Optional[str]]: ...

    # Contract: Parses part directory, unit name, and role name from file path.
    def parse_unit_from_file_path(
        self, file_path: str, repo_root: str
    ) -> Tuple[str, str, str]: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:20:44Z
# CHANGE: Remove the undeclared module-level resolution wrappers so the interface holds only the declared outcome type and coordinator protocol; callers now resolve the coordinator singleton directly
# --- END CLEANROOM METADATA ---
