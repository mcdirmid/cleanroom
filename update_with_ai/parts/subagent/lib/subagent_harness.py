"""Interface specification for subagent_harness."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol
from support.lib.lifecycle import Singleton
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from . import subagent_coordinator


# Contract: CommandHarnessAdapter executes subagent turns through configurable process command templates.
class CommandHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns through configurable process command templates."""

    # Contract: CommandHarnessAdapter.format_task_prompt - formats instructional task prompt detailing role, scope, targets, and tools.
    def format_task_prompt(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Constructs instructional task prompt for the role subagent."""
        ...

    # Contract: CommandHarnessAdapter.dispatch_role - records initial pending targets, spawns subagent process, and returns task handle.
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a subagent bound to the role workspace."""
        ...

    # Contract: CommandHarnessAdapter.await_role - awaits process completion, inspects blame buffer, computes submitted targets, and returns RoleRoundResult.
    def await_role(self, task_handle: str) -> subagent_coordinator.RoleRoundResult:
        """Awaits subagent round completion and returns outcome result."""
        ...

    # Contract: CommandHarnessAdapter.poll_role - polls subagent round execution non-blockingly without waiting for completion.
    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
        """Polls subagent round execution without blocking."""
        ...

    # Contract: CommandHarnessAdapter.interrupt_role - aborts active subagent task execution upon timeout or loop limit.
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or loop limit."""
        ...


# Contract: HarnessAdapterFactory constructs harness adapters for subagent execution.
class HarnessAdapterFactory(Protocol):
    """Constructs harness adapters for subagent execution."""

    # Contract: Constructs and returns configured subagent coordinator harness adapter.
    def __call__(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
        **kwargs: Any,
    ) -> subagent_coordinator.HarnessAdapter:
        ...


# Contract: HarnessRegistry maintains installed platform harness adapter factories and resolves adapters in the agent session tier.
class HarnessRegistry(Singleton[AgentSessionTier], Protocol):
    """Maintains installed platform harness adapter factories and resolves adapters."""

    # Contract: Returns mapping of installed platform names to harness adapter factories.
    @property
    def installed_harnesses(self) -> Mapping[str, HarnessAdapterFactory]:
        ...

    # Contract: HarnessRegistry.install_harness - registers adapter factory under platform name in installed harnesses mapping.
    def install_harness(
        self,
        platform_name: str,
        adapter_factory: HarnessAdapterFactory,
    ) -> None:
        ...

    # Contract: HarnessRegistry.resolve_harness - resolves harness adapter for platform name, custom command template, or simulation mode.
    def resolve_harness(
        self,
        platform_name: str,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
    ) -> subagent_coordinator.HarnessAdapter:
        """Resolves a harness adapter for a platform name or custom command template."""
        ...


HarnessResolver = HarnessRegistry

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_harness interface library
# --- END CLEANROOM METADATA ---
