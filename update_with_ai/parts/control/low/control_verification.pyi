"""Low-level interface specification for control_verification."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_node_config
import dag_storage


@data_type
@dataclass(frozen=True)
class VerificationResult:
    """Outcome of verification check evaluation.

    Args:
        passed: True if all checks passed.
        diagnostic_output: Sanitized stdout and stderr output.
        is_cached: True if result was returned from hash cache.
    """

    passed: bool
    diagnostic_output: str
    is_cached: bool = False


@singleton_type("agent_session")
class VerificationEvaluator(InTier[AgentSessionTier], Protocol):
    """Evaluator that runs verification checks and sanitizes output."""

    @operation
    def evaluate_verification(
        self, target: Optional[dag_storage.DagNode] = None
    ) -> VerificationResult:
        """Evaluates verification checks for a specific target node or all open targets.

        POSTCONDITIONS:
        - When current file hashes match cached hash, MUST reuse cached result.
        - When checks fail, MUST strip diagnostic noise and record failure in cache.
        - When checks pass, MUST strip diagnostic noise and record success in cache.
        """
        ...

    @operation
    def clean_diagnostic_noise(self, text: str) -> str:
        """Strips build system noise lines from diagnostic text.

        POSTCONDITIONS:
        - MUST strip progress lines, load banners, and timing statistics.
        """
        ...
