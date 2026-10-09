# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-06T10:45:00Z
# CHANGE: new file
# CODE_HASH: 080c571d8c6f
# --- END CLEANROOM METADATA ---

from __future__ import annotations
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


class VerificationEvaluator(Protocol):
    """Evaluates verification checks and filters compiler diagnostic noise."""

    def evaluate_verification(
        self, target: Optional[dag_storage.DagNode] = None
    ) -> VerificationResult: ...

    def clean_diagnostic_noise(self, text: str) -> str: ...
