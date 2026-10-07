# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: f09ef009f032
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for control_verification_impl."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import control_verification
import dag_storage


@singleton_type("agent_session")
class VerificationEvaluator(
    control_verification.VerificationEvaluator,
    InTier[AgentSessionTier],
):
    """Implementation of verification evaluator.

    GROUNDING:
    - Realizes verification check execution and diagnostic noise scrubbing by inspecting
      target check commands from NodeConfig, computing SHA-256 hashes of target files,
      executing check subprocesses, and caching verification outcomes.
    """

    @operation
    @override
    def evaluate_verification(
        self, target: Optional[dag_storage.DagNode] = None
    ) -> control_verification.VerificationResult:
        """Evaluates verification checks for a target or all open targets.

        GROUNDING:
        - Grounded via NodeConfig from agent_node_config to resolve verification commands
          for the target DagNode, file hashing to detect changes against cached results,
          and executing checks sequentially until failure or success.
        """
        ...

    @operation
    @override
    def clean_diagnostic_noise(self, text: str) -> str:
        """Strips build system progress indicators and compilation banners from output text.

        GROUNDING:
        - Grounded via regex patterns stripping Bazel progress lines, loading banners,
          and elapsed timing statistics from diagnostic output.
        """
        ...
