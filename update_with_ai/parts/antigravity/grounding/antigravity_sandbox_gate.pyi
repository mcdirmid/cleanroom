from dataclasses import dataclass
from framework import data_type, operation, singleton_type
from typing import Any, Dict, Optional, Tuple

@data_type
@dataclass(frozen=True)
class GatingDecision:
    """
PURPOSE:
Represents the outcome of evaluating a tool call, exposing a decision status, a reason, and an optional overwrite mapping.

FRESH_REQUIREMENTS:
- A gating decision record represents the outcome of evaluating a tool call, exposing a decision status, a reason, and an optional overwrite mapping.
"""

    def __init__(self, decision: str, reason: str, overwrite: Optional[Dict[str, Any]]=None) -> None:
        ...

    @property
    def decision(self) -> str:
        """
PURPOSE:
Exposes the allow or deny decision outcome.
"""
        ...

    @property
    def reason(self) -> str:
        """
PURPOSE:
Exposes diagnostic explanation for the gating decision.
"""
        ...

    @property
    def overwrite(self) -> Optional[Dict[str, Any]]:
        """
PURPOSE:
Exposes sanitized argument overrides for allowed tool calls.
"""
        ...

@singleton_type('system')
class AntigravitySandboxGate:
    """
PURPOSE:
System service that validates subagent tool invocations before execution.
"""

    @operation
    def process_hook_input(self, payload: str) -> GatingDecision:
        """
PURPOSE:
Evaluates a raw JSON payload string and returns a gating decision.

FRESH_REQUIREMENTS:
- The antigravity sandbox gate evaluates a raw JSON payload string and returns a gating decision.
"""
        ...

    @operation
    def validate_worker_command(self, command_line: str) -> Tuple[bool, str]:
        """
PURPOSE:
Inspects a command line and determines whether execution is permitted.

FRESH_REQUIREMENTS:
- The antigravity sandbox gate inspects a command line and determines whether execution is permitted.
"""
        ...

    @operation
    def validate_coordinator_command(self, command_line: str) -> Tuple[bool, str]:
        """
PURPOSE:
Inspects a command line and determines whether coordinator execution is permitted.

FRESH_REQUIREMENTS:
- The antigravity sandbox gate inspects a command line and determines whether coordinator execution is permitted.
"""
        ...

    @operation
    def is_coordinator_caller(self, identifier: str) -> bool:
        """
PURPOSE:
Verifies whether a conversation identifier belongs to a coordinator subagent.

FRESH_REQUIREMENTS:
- The antigravity sandbox gate verifies whether a conversation identifier belongs to a coordinator subagent.
"""
        ...

    @operation
    def is_role_worker_caller(self, identifier: str) -> bool:
        """
PURPOSE:
Verifies whether a conversation identifier belongs to a role worker subagent.

FRESH_REQUIREMENTS:
- The antigravity sandbox gate verifies whether a conversation identifier belongs to a role worker subagent.
"""
        ...

    @operation
    def save_worker_session(self, worker_id: str, session_id: str) -> None:
        """
PURPOSE:
Associates a worker identifier with a session identifier.

FRESH_REQUIREMENTS:
- The antigravity sandbox gate associates a worker identifier with a session identifier.
"""
        ...

    @operation
    def remove_worker_session(self, worker_id: str) -> None:
        """
PURPOSE:
Disassociates a worker identifier.

FRESH_REQUIREMENTS:
- The antigravity sandbox gate disassociates a worker identifier.
"""
        ...

    @operation
    def read_worker_sessions(self) -> Dict[str, str]:
        """
PURPOSE:
Returns all active worker session associations.

FRESH_REQUIREMENTS:
- The antigravity sandbox gate returns all active worker session associations.
"""
        ...
