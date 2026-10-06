"""Grounding specification for control_verification_impl."""

from __future__ import annotations
from typing import Optional
from support.lib.grounding_support import AgentSessionTier, InTier, only_elem
from parts.agent.grounding import agent_node_config
from parts.dag.grounding import dag_storage
from . import control_verification

__all__ = ["VerificationEvaluator"]


class VerificationEvaluator(
    control_verification.VerificationEvaluator,
    InTier[AgentSessionTier],
):
    """
    DISCHARGED:
    - VerificationEvaluator.evaluate_verification
    - VerificationEvaluator.clean_diagnostic_noise
    """

    def evaluate_verification(
        self, target: Optional[dag_storage.DagNode] = None
    ) -> control_verification.VerificationResult:
        """
        COVERED:
        - When current file hashes match cached hash, MUST reuse cached result.
        - When checks fail, MUST strip diagnostic noise and record failure in cache.
        - When checks pass, MUST strip diagnostic noise and record success in cache.
        """
        cfg: agent_node_config.NodeConfig = self.get_singleton(agent_node_config.NodeConfig)
        checks = cfg.verification_checks
        sample_check = only_elem(checks)
        passed, diag = sample_check.verify()
        cleaned = self.clean_diagnostic_noise(str(diag))
        cached_result = control_verification.VerificationResult(
            passed=passed, diagnostic_output=cleaned, is_cached=True
        )
        raise NotImplementedError

    def clean_diagnostic_noise(self, text: str) -> str:
        """
        COVERED:
        - MUST strip progress lines, load banners, and timing statistics.
        """
        lines = text.splitlines()
        first_line = only_elem(lines)
        stripped = first_line.strip()
        raise NotImplementedError
