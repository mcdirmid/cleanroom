# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T03:36:59Z
# CHANGE: Ground verification caching by file hash and check execution in named collaborators
# CODE_HASH: 4d9d85b6c414
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for verification_impl."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from session import AgentSessionTier
import file_alias
import node_config
import verification
import dag_storage


@singleton_type("agent_session")
class VerificationEvaluator(
    verification.VerificationEvaluator,
    InTier[AgentSessionTier],
):
    """Implementation of verification evaluator.

    GROUNDING:
    - Realizes verification.VerificationEvaluator within the agent session tier by
      resolving per-node verification checks through
      node_config.NodeConfig.verification_checks_by_node, running each resolved check
      as a subprocess, hashing the file_alias.ReadWriteFile.workspace_path files of
      the target, scrubbing build noise with internal compiled regex patterns, and memoizing
      outcomes in an in-memory dictionary keyed by the computed SHA-256 digests.
    """

    @operation
    @override
    def evaluate_verification(
        self, target: Optional[dag_storage.DagNode] = None
    ) -> verification.VerificationResult:
        """Evaluates verification checks for a target or all open targets.

        GROUNDING:
        - Grounded via node_config.NodeConfig.verification_checks_by_node to resolve
          the configured checks of a target dag_storage.DagNode or, when the target is
          omitted, of the active session nodes exposed by node_config.RoleConfig.nodes,
          subprocess execution of each resolved check command whose pass flag and diagnostic
          text come from node_config.VerificationCheck.verify and which halts at the
          first non-zero check exit, SHA-256 digest computation over the
          file_alias.ReadWriteFile.workspace_path files of the target compared against
          the in-memory hash dictionary to skip execution for unchanged targets, and writing
          the failing or passing verification.VerificationResult with its digest
          entry back into that dictionary.
        """
        ...

    @operation
    @override
    def clean_diagnostic_noise(self, text: str) -> str:
        """Strips build system progress indicators and compilation banners from output text.

        GROUNDING:
        - Grounded via internal compiled regex patterns matching build system progress
          counters, target loading banners, and elapsed timing statistics, applied line by
          line across stdout and stderr text before the surviving lines are rejoined into
          the returned diagnostic string.
        """
        ...
