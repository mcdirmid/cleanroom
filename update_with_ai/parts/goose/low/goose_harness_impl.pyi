# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T09:50:00Z
# CHANGE: author goose_harness_impl implementation low-level specification
# CODE_HASH: e03616bfe8a3
# SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for goose_harness_impl."""

from typing import Optional
from framework import operation, override, poly_type, singleton_type
from support.lib.lifecycle import InTier
import agent_session
import goose_ext
import goose_harness
import subagent_coordinator
import workspace_work


@poly_type
class GooseTelemetryParser(goose_harness.GooseTelemetryParser):
    """Realizes SQLite session database parsing and Goose pricing calculation.

    GROUNDING:
    - Queries SQLite sessions.db tables conforming to goose_ext, aggregates
      uncached, cached, and completion tokens, falls back to text logs when database
      records are absent, and applies model pricing rate cards to produce
      goose_harness.GooseSessionTokenMetrics records.
    """

    @operation
    @override
    def parse_session_db(
        self,
        sessions_db_path: str,
        session_name: str,
        model_name: Optional[str] = None,
    ) -> goose_harness.GooseSessionTokenMetrics:
        """Queries the SQLite sessions database and returns token metrics.

        GROUNDING:
        - Executes SQL queries against sessions and usage_ledger tables in sessions_db_path
          matching session_name according to goose_ext, and computes cost_usd using rate cards.
        """
        ...

    @operation
    @override
    def parse_log_text(
        self,
        log_text: str,
        model_name: Optional[str] = None,
    ) -> goose_harness.GooseSessionTokenMetrics:
        """Parses stdout log text for token metrics when database records are unavailable.

        GROUNDING:
        - Extracts token metrics from stdout strings conforming to goose_ext and computes cost_usd.
        """
        ...


@poly_type
class GooseHarnessAdapter(goose_harness.GooseHarnessAdapter):
    """Realizes subagent execution in Goose role workspaces.

    GROUNDING:
    - Launches Goose CLI processes bound to dispatch.workspace_dir with instructions
      file, tracks initial pending targets via workspace_work.WorkspaceWorkManager,
      awaits completion, extracts token telemetry via GooseTelemetryParser, inspects
      blame buffers, and returns subagent_coordinator.RoleTurnResult objects.
    """

    @operation
    @override
    def dispatch_role(
        self,
        dispatch: subagent_coordinator.RoleDispatch,
    ) -> str:
        """Dispatches work directive to a Goose role workspace.

        GROUNDING:
        - Executes Goose CLI process bound to dispatch.workspace_dir using instructions path
          conforming to goose_ext and returns task handle.
        """
        ...

    @operation
    @override
    def await_role(
        self,
        task_handle: str,
    ) -> subagent_coordinator.RoleTurnResult:
        """Awaits Goose subagent turn completion and returns outcome result.

        GROUNDING:
        - Awaits process completion without mandatory timeout unless configured, computes buffer
          differences via workspace_work, parses session telemetry via goose_harness,
          and constructs subagent_coordinator.RoleTurnResult.
        """
        ...

    @operation
    @override
    def poll_role(
        self,
        task_handle: str,
    ) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls Goose subagent turn execution without blocking.

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
        """Aborts active Goose subagent task execution upon timeout or limit.

        GROUNDING:
        - Terminates the running subprocess associated with task_handle.
        """
        ...


@singleton_type("agent_session")
class GooseHarnessManager(
    goose_harness.GooseHarnessManager,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes management of Goose execution adapters and telemetry parsing.

    GROUNDING:
    - Instantiates GooseHarnessAdapter and GooseTelemetryParser services
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
        sessions_db_path: Optional[str] = None,
    ) -> goose_harness.GooseHarnessAdapter:
        """Constructs a Goose harness adapter instance.

        GROUNDING:
        - Instantiates GooseHarnessAdapter with configured model, timeout, and database path.
        """
        ...

    @operation
    @override
    def get_telemetry_parser(self) -> goose_harness.GooseTelemetryParser:
        """Returns the Goose telemetry parser service.

        GROUNDING:
        - Returns a singleton or reusable instance of GooseTelemetryParser.
        """
        ...
