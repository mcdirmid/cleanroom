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
    """Implementation of verification evaluator."""

    @operation
    @override
    def evaluate_verification(
        self, target: Optional[dag_storage.DagNode] = None
    ) -> control_verification.VerificationResult:
        ...

    @operation
    @override
    def clean_diagnostic_noise(self, text: str) -> str:
        ...
