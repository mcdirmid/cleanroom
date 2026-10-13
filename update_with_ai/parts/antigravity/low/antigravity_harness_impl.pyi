# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_harness_impl implementation low-level specification
# CODE_HASH: 68f98b377fe4
# SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for antigravity_harness_impl."""

from typing import Optional
from framework import operation, override, poly_type, singleton_type
from support.lib.lifecycle import InTier
import agent_session
import antigravity_ext
import antigravity_harness
import subagent_coordinator


@poly_type
class TranscriptTelemetryParser(antigravity_harness.TranscriptTelemetryParser):
    """Realizes JSONL transcript parsing and Gemini pricing calculation.

    GROUNDING:
    - Parses JSONL event lines conforming to antigravity_ext transcript event schemas,
      aggregates uncached, cached, and completion tokens, and applies Gemini Flash and Pro
      pricing rate cards to produce antigravity_harness.TranscriptTokenMetrics records.
    """

    @operation
    @override
    def parse_transcript_file(
        self,
        transcript_path: str,
        model_name: Optional[str] = None,
    ) -> antigravity_harness.TranscriptTokenMetrics:
        """Parses a transcript log file and returns token metrics.

        GROUNDING:
        - Reads lines from transcript_path according to antigravity_ext, sums token counts,
          and computes cost_usd using standardized rate cards.
        """
        ...


@poly_type
class AntigravityHarnessAdapter(antigravity_harness.AntigravityHarnessAdapter):
    """Realizes subagent execution in Antigravity role workspaces.

    GROUNDING:
    - Launches subagent processes bound to dispatch.workspace_dir, awaits completion,
      extracts token telemetry via TranscriptTelemetryParser, inspects blame buffers,
      and returns subagent_coordinator.RoleTurnResult objects.
    """

    @operation
    @override
    def dispatch_role(
        self,
        dispatch: subagent_coordinator.RoleDispatch,
    ) -> str:
        """Dispatches work directive to an Antigravity role workspace.

        GROUNDING:
        - Executes Antigravity subagent process bound to dispatch.workspace_dir and returns task handle.
        """
        ...

    @operation
    @override
    def await_role(
        self,
        task_handle: str,
    ) -> subagent_coordinator.RoleTurnResult:
        """Awaits subagent turn completion and returns outcome result.

        GROUNDING:
        - Awaits process completion, parses transcript telemetry via antigravity_harness,
          and constructs subagent_coordinator.RoleTurnResult.
        """
        ...

    @operation
    @override
    def poll_role(
        self,
        task_handle: str,
    ) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls subagent turn execution non-blockingly without waiting for completion.

        GROUNDING:
        - Checks subprocess status via poll() or equivalent non-blocking probe, returning
          None while active, or collating RoleTurnResult when terminated.
        """
        ...

    @operation
    @override
    def interrupt_role(
        self,
        task_handle: str,
    ) -> None:
        """Aborts active subagent task execution upon timeout or limit.

        GROUNDING:
        - Terminates the running subprocess associated with task_handle.
        """
        ...


@singleton_type("agent_session")
class AntigravityHarnessManager(
    antigravity_harness.AntigravityHarnessManager,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes management of Antigravity execution adapters and transcript parsing.

    GROUNDING:
    - Instantiates AntigravityHarnessAdapter and TranscriptTelemetryParser services
      within agent_session.AgentSessionTier.
    """

    @operation
    @override
    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        custom_cmd: Optional[str] = None,
    ) -> antigravity_harness.AntigravityHarnessAdapter:
        """Constructs an Antigravity harness adapter instance.

        GROUNDING:
        - Instantiates AntigravityHarnessAdapter with configured model and timeout.
        """
        ...

    @operation
    @override
    def get_transcript_parser(self) -> antigravity_harness.TranscriptTelemetryParser:
        """Returns the transcript telemetry parser service.

        GROUNDING:
        - Returns a singleton or reusable instance of TranscriptTelemetryParser.
        """
        ...
