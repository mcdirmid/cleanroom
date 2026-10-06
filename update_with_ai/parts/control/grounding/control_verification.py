"""Grounding specification for control_verification."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from support.lib.grounding_support import AgentSessionTier, InTier
from parts.dag.grounding import dag_storage

__all__ = ["VerificationResult", "VerificationEvaluator"]


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    diagnostic_output: str
    is_cached: bool = False


class VerificationEvaluator(InTier[AgentSessionTier], Protocol):
    def evaluate_verification(
        self, target: Optional[dag_storage.DagNode] = None
    ) -> VerificationResult:
        """
        DEFERRED:
        - When current file hashes match cached hash, MUST reuse cached result.
        - When checks fail, MUST strip diagnostic noise and record failure in cache.
        - When checks pass, MUST strip diagnostic noise and record success in cache.
        """
        raise NotImplementedError

    def clean_diagnostic_noise(self, text: str) -> str:
        """
        DEFERRED:
        - MUST strip progress lines, load banners, and timing statistics.
        """
        raise NotImplementedError
