# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_harness interface low-level specification
# CODE_HASH: 70b476bfbf14
# SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for subagent_harness."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import subagent_coordinator


@poly_type
class CommandHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns through configurable process command templates."""

    @operation
    def format_task_prompt(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Constructs instructional task prompt for the role subagent.

        POSTCONDITIONS:
        - MUST format instructional task prompt detailing role, directory scope, targets, verification commands, and submit or blame actions.
        """
        ...

    @operation
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a subagent bound to the role workspace.

        POSTCONDITIONS:
        - MUST record initial pending targets from workspace pending work buffer.
        - MUST spawn subagent process matching configured command template within workspace directory.
        - MUST return unique task handle tracking the running turn.
        """
        ...

    @operation
    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits subagent turn completion and returns outcome result.

        POSTCONDITIONS:
        - MUST await process completion without mandatory timeout unless an explicit limit is configured.
        - WHEN process times out, MUST terminate process and return failed result.
        - MUST inspect workspace blame buffer for reported defects.
        - MUST determine submitted targets by set difference with remaining pending items.
        - MUST extract token usage metrics and return synthesized RoleTurnResult.
        """
        ...

    @operation
    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls subagent turn execution without blocking.

        POSTCONDITIONS:
        - WHEN subagent process has terminated, MUST return role turn result.
        - WHEN subagent process is still running, MUST return None without blocking or termination.
        """
        ...

    @operation
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or loop limit.

        POSTCONDITIONS:
        - MUST terminate active subagent process associated with task handle.
        """
        ...


@singleton_type("agent_session")
class HarnessResolver(InTier[AgentSessionTier], Protocol):
    """Resolves harness adapter instances for designated platforms."""

    @operation
    def resolve_harness(
        self,
        platform_name: str,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
    ) -> subagent_coordinator.HarnessAdapter:
        """Resolves a harness adapter for a platform name or custom command template.

        POSTCONDITIONS:
        - MUST return CommandHarnessAdapter configured with canonical platform command template or custom command.
        - WHEN platform is simulated or simulation_mode is true, MUST return simulated harness adapter.
        """
        ...
