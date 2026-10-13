# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_harness_impl implementation low-level specification
# CODE_HASH: 56b5639a8a6b
# SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for dsh_harness_impl."""

from typing import Optional
from framework import operation, override, poly_type, singleton_type
from support.lib.lifecycle import InTier
import agent_session
import dsh_ext
import dsh_harness
import subagent_coordinator
import workspace_work


@poly_type
class DshTelemetryParser(dsh_harness.DshTelemetryParser):
    """Realizes session storage archive and event stream parsing for DeepSeek Harness.

    GROUNDING:
    - Queries session.v4.jsonl.zstd archives or parses stdout stream events conforming to dsh_ext,
      aggregates uncached, cached, and completion tokens, falls back to text logs when structured
      records are absent, and applies model pricing rate cards to produce
      dsh_harness.DshSessionTokenMetrics records.
    """

    @operation
    @override
    def parse_session_storage(
        self,
        sessions_dir: str,
        workspace_dir: str,
        model_name: Optional[str] = None,
    ) -> dsh_harness.DshSessionTokenMetrics:
        """Queries session storage archives and returns token metrics.

        GROUNDING:
        - Locates session directories under sessions_dir matching workspace_dir slug according to
          dsh_ext, decompresses session.v4.jsonl.zstd, aggregates token usage, and computes cost_usd.
        """
        ...

    @operation
    @override
    def parse_stream_text(
        self,
        stream_text: str,
        model_name: Optional[str] = None,
    ) -> dsh_harness.DshSessionTokenMetrics:
        """Parses stdout JSON event streams or log text for token metrics.

        GROUNDING:
        - Extracts token metrics from JSON run events or stdout strings conforming to dsh_ext
          and computes cost_usd.
        """
        ...


@poly_type
class DshHarnessAdapter(dsh_harness.DshHarnessAdapter):
    """Realizes subagent execution in DeepSeek Harness role workspaces.

    GROUNDING:
    - Launches dsh headless CLI processes bound to dispatch.workspace_dir with Cordis overlay
      patches, tracks initial pending targets via workspace_work.WorkspaceWorkManager,
      awaits completion, extracts token telemetry via DshTelemetryParser, inspects blame buffers,
      and returns subagent_coordinator.RoleTurnResult objects.
    """

    @operation
    @override
    def dispatch_role(
        self,
        dispatch: subagent_coordinator.RoleDispatch,
    ) -> str:
        """Dispatches work directive to a DeepSeek Harness role workspace.

        GROUNDING:
        - Executes dsh CLI process bound to dispatch.workspace_dir using headless profile and
          overlay patches conforming to dsh_ext and returns task handle.
        """
        ...

    @operation
    @override
    def await_role(
        self,
        task_handle: str,
    ) -> subagent_coordinator.RoleTurnResult:
        """Awaits DeepSeek Harness subagent turn completion and returns outcome result.

        GROUNDING:
        - Awaits process completion without mandatory timeout unless configured, computes buffer
          differences via workspace_work, parses session telemetry via dsh_harness,
          and constructs subagent_coordinator.RoleTurnResult.
        """
        ...

    @operation
    @override
    def poll_role(
        self,
        task_handle: str,
    ) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls DeepSeek Harness subagent turn execution without blocking.

        GROUNDING:
        - Polls process status via poll(), returning None if still running,
          or processing blame records, buffer differences, and session telemetry upon completion.
        """
        ...

    @operation
    @override
    def interrupt_role(
        self,
        task_handle: str,
    ) -> None:
        """Aborts active DeepSeek Harness subagent task execution upon timeout or limit.

        GROUNDING:
        - Terminates the running subprocess associated with task_handle.
        """
        ...


@singleton_type("agent_session")
class DshHarnessManager(
    dsh_harness.DshHarnessManager,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes management of DeepSeek Harness execution adapters and telemetry parsing.

    GROUNDING:
    - Instantiates DshHarnessAdapter and DshTelemetryParser services
      within agent_session.AgentSessionTier.
    """

    @operation
    @override
    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        sessions_dir: Optional[str] = None,
    ) -> dsh_harness.DshHarnessAdapter:
        """Constructs a DeepSeek Harness adapter instance.

        GROUNDING:
        - Instantiates DshHarnessAdapter with configured model, timeout, and session storage path.
        """
        ...

    @operation
    @override
    def get_telemetry_parser(self) -> dsh_harness.DshTelemetryParser:
        """Returns the DeepSeek Harness telemetry parser service.

        GROUNDING:
        - Returns a singleton or reusable instance of DshTelemetryParser.
        """
        ...
