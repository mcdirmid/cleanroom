# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_harness interface library
# CODE_HASH: 48affbb885ea
# --- END CLEANROOM METADATA ---

"""Interface specification for subagent_harness."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol
from support.lib.lifecycle import InTier
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier
from . import subagent_coordinator


class CommandHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns through configurable process command templates."""

    def format_task_prompt(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Constructs instructional task prompt for the role subagent."""
        ...

    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a subagent bound to the role workspace."""
        ...

    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits subagent turn completion and returns outcome result."""
        ...

    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls subagent turn execution without blocking."""
        ...

    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or loop limit."""
        ...


class HarnessAdapterFactory(Protocol):
    """Constructs harness adapters for subagent execution."""

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


class HarnessRegistry(InTier[AgentSessionTier], Protocol):
    """Maintains installed platform harness adapter factories and resolves adapters."""

    @property
    def installed_harnesses(self) -> Mapping[str, HarnessAdapterFactory]:
        ...

    def install_harness(
        self,
        platform_name: str,
        adapter_factory: HarnessAdapterFactory,
    ) -> None:
        ...

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
