from __future__ import annotations
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from update_with_ai.parts.dag.lib import dag_storage


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


class VerificationEvaluator(Singleton[AgentSessionTier], Protocol):
    """Evaluates verification checks and filters compiler diagnostic noise."""

    # Contract: Evaluates configured verification checks for target or all open targets, memoizes by target file hashes, and cleans diagnostic noise.
    def evaluate_verification(
        self, target: Optional[dag_storage.DagNode] = None
    ) -> VerificationResult: ...

    # Contract: Strips build progress indicators, load banners, and elapsed timing statistics from diagnostic text.
    def clean_diagnostic_noise(self, text: str) -> str: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-06T10:45:00Z
# CHANGE: new file
# --- END CLEANROOM METADATA ---
