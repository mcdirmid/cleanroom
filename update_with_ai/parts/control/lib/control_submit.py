# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-06T10:45:00Z
# CHANGE: new file
# CODE_HASH: ff654c8a9b2b
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


def resolve_submit_target(
    target: str,
    repo_root: str,
    role_name: str,
    dir_scope: str = "staging",
) -> Tuple[Optional[str], Optional[str]]:
    from support.lib.lifecycle import get_singleton
    coord = get_singleton(SubmissionCoordinator)
    return coord.resolve_submit_target(target, repo_root, role_name, dir_scope)


def parse_unit_from_file_path(
    file_path: str, repo_root: str
) -> Tuple[str, str, str]:
    from support.lib.lifecycle import get_singleton
    coord = get_singleton(SubmissionCoordinator)
    return coord.parse_unit_from_file_path(file_path, repo_root)



def is_auditor_node(node: dag_storage.DagNode) -> bool:
    """Checks whether the node's role is classified as an auditor."""
    role_clean = node.role_address.split(":")[-1].strip().lower()
    return role_clean in ("grounding_qa", "qa", "coverage", "spec_qa", "low_qa")
