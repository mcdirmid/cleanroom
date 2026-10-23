"""Low-level interface specification for verification."""

from dataclasses import dataclass
from typing import Optional, Protocol
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import dag_storage


@data_type
@dataclass(frozen=True)
class VerificationResult:
    """Outcome of verification check evaluation.

    Args:
        passed: True if all configured verification checks passed.
        diagnostic_output: Sanitized stdout and stderr output.
        is_cached: Reuse status indicating whether evaluation was reused from cache.
    """

    passed: bool
    diagnostic_output: str
    is_cached: bool = False


@singleton_type("agent_session")
class VerificationEvaluator(Singleton[AgentSessionTier], Protocol):
    """Agent session's verification evaluator coordinating verification execution for active targets."""

    @operation
    def evaluate_verification(
        self, target: Optional[dag_storage.DagNode] = None
    ) -> VerificationResult:
        """Evaluates configured verification checks for a specified target node or all open session targets.

        POSTCONDITIONS:
        - WHEN a target node is supplied, MUST evaluate the configured verification checks
          for that target node.
        - WHEN the target node is omitted, MUST evaluate verification checks across all open
          session targets.
        - MUST memoize verification results keyed by target file hashes.
        - WHEN current target file hashes match the memoized hashes, MUST return the memoized
          verification result with the cached flag set.
        - WHEN check execution produces diagnostic output, MUST sanitize the output by
          removing build progress lines, load banners, and elapsed timing statistics before
          reporting the outcome.
        - MUST execute verification checks polymorphically, supporting verification objects providing a verify method and command objects declaring a shell command string executed with a bounded timeout.
        - WHEN a configured verification check fails, MUST report a failing verification result.
        - WHEN all configured verification checks succeed, MUST report a passing verification result.
        """
        ...

    @operation
    def clean_diagnostic_noise(self, text: str) -> str:
        """Strips build system noise lines from diagnostic text.

        POSTCONDITIONS:
        - MUST strip build system progress indicators from diagnostic text.
        - MUST strip target load banners from diagnostic text.
        - MUST strip elapsed timing statistics from diagnostic text.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T03:36:59Z
# CHANGE: Split verification evaluation and diagnostic noise filtering into atomic contracts
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
