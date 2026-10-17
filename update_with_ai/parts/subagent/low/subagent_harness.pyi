# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_harness interface low-level specification
# CODE_HASH: 3bbd2d379c23
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for subagent_harness."""

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol, Sequence
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
        - MUST extract token usage metrics and compute rate-card costs from execution logs.
        - WHEN a process exits with non-zero status, MUST capture failure diagnostics from the tail of the log.
        - MUST return synthesized RoleTurnResult.
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


@poly_type
class HarnessAdapterFactory(Protocol):
    """Constructs harness adapters for subagent execution."""

    @operation
    def __call__(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
        **kwargs: Any,
    ) -> subagent_coordinator.HarnessAdapter:
        """Constructs a configured harness adapter instance.

        POSTCONDITIONS:
        - MUST construct and return configured subagent coordinator harness adapter.
        """
        ...


@singleton_type("agent_session")
class HarnessRegistry(InTier[AgentSessionTier], Protocol):
    """Maintains installed platform harness adapter factories and resolves adapters."""

    @property
    def installed_harnesses(self) -> Mapping[str, HarnessAdapterFactory]:
        """Returns mapping of installed platform names to harness adapter factories."""
        ...

    @operation
    def install_harness(
        self,
        platform_name: str,
        adapter_factory: HarnessAdapterFactory,
    ) -> None:
        """Installs a harness adapter factory for a designated platform name.

        POSTCONDITIONS:
        - MUST register adapter factory under platform name in installed harnesses mapping.
        """
        ...

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
        - MUST return CommandHarnessAdapter configured with custom command or simulation mode when requested.
        - WHEN platform is installed, MUST invoke installed adapter factory and return harness adapter.
        - WHEN platform is not installed, MUST raise ValueError.
        """
        ...


HarnessResolver = HarnessRegistry
