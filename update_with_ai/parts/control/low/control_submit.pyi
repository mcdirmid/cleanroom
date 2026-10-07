# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 590cd64b577f
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for control_submit."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import dag_storage


@data_type
@dataclass(frozen=True)
class SubmissionOutcome:
    """Outcome of target submission.

    Args:
        accepted: True if submission passed gating rules and was committed.
        message: Diagnostic feedback or acceptance message.
    """

    accepted: bool
    message: str


@singleton_type("agent_session")
class SubmissionCoordinator(InTier[AgentSessionTier], Protocol):
    """Coordinator that validates preconditions and commits clean submissions."""

    @operation
    def submit_target(
        self,
        target_node: dag_storage.DagNode,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> SubmissionOutcome:
        """Submits a target node after validating gating rules.

        POSTCONDITIONS:
        - When verification fails, MUST reject submission.
        - When an in-batch dependency is not clean, MUST reject submission.
        - When auditor role supplies a change summary, MUST reject submission.
        - When files modified and change summary omitted, MUST reject submission.
        - When files unmodified and change summary supplied, MUST reject submission.
        - When accepted, MUST mark target node clean in graph storage and record change message.
        """
    @operation
    def submit_target_file(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> SubmissionOutcome:
        """Submits a file target after validating gating rules and updating metadata.

        POSTCONDITIONS:
        - When auditor role attempts to submit a verification or test file, MUST reject submission.
        - When producer role attempts to submit a read-only target, MUST reject submission.
        - When target is modified and change summary is omitted, MUST reject submission.
        - When target is unmodified and change summary is supplied, MUST reject submission.
        - When accepted, MUST update in-band metadata or execute build submission target in main repository.
        - MUST return SubmissionOutcome indicating acceptance status and message.
        """
        ...
