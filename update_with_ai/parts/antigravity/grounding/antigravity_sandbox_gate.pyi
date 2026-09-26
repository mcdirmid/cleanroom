from dataclasses import dataclass
from framework import data_type, operation, singleton_type
from typing import Any, Dict, Optional, Tuple

@data_type
@dataclass(frozen=True)
class GatingDecision:
    """Represents the outcome of evaluating a tool call.

    REQUIREMENTS:
    - A gating decision record represents the outcome of evaluating a tool call, exposing a decision status, a reason, and an optional overwrite mapping.

    GROUNDING_PROVISIONS:
    - knows("decision", Self)
    - knows("reason", Self)
    - knows("overwrite", Self)
    """

    def __init__(self, decision: str, reason: str, overwrite: Optional[Dict[str, Any]]=None) -> None:
        ...

    @property
    def decision(self) -> str:
        ...

    @property
    def reason(self) -> str:
        ...

    @property
    def overwrite(self) -> Optional[Dict[str, Any]]:
        ...

@singleton_type('system')
class AntigravitySandboxGate:
    """System service that validates subagent tool invocations before execution.

    REQUIREMENTS:
    - The antigravity sandbox gate evaluates a raw JSON payload string and returns a gating decision.
    - The antigravity sandbox gate inspects a command line and determines whether execution is permitted.
    - The antigravity sandbox gate inspects a command line and determines whether coordinator execution is permitted.
    - The antigravity sandbox gate verifies whether a conversation identifier belongs to a coordinator subagent.
    - The antigravity sandbox gate verifies whether a conversation identifier belongs to a role worker subagent.
    - The antigravity sandbox gate associates a worker identifier with a session identifier.
    - The antigravity sandbox gate disassociates a worker identifier.
    - The antigravity sandbox gate returns all active worker session associations.

    GROUNDING_PROVISIONS:
    - action("evaluate_tool_payload", GatingDecision): Evaluates incoming tool hook payload.
    - action("validate_worker_command_line", Tuple[bool, str]): Validates command line against role worker whitelist.
    - action("validate_coordinator_command_line", Tuple[bool, str]): Validates command line against coordinator whitelist.
    - action("verify_coordinator_caller", bool): Verifies whether caller is coordinator subagent.
    - action("verify_role_worker_caller", bool): Verifies whether caller is role worker subagent.
    - action("associate_worker_session", None): Associates worker identifier with session identifier.
    - action("disassociate_worker_session", None): Removes worker identifier association.
    - action("query_active_worker_sessions", Dict[str, str]): Returns all active worker session associations.
    """

    @operation
    def process_hook_input(self, payload: str) -> GatingDecision:
        ...

    @operation
    def validate_worker_command(self, command_line: str) -> Tuple[bool, str]:
        ...

    @operation
    def validate_coordinator_command(self, command_line: str) -> Tuple[bool, str]:
        ...

    @operation
    def is_coordinator_caller(self, identifier: str) -> bool:
        ...

    @operation
    def is_role_worker_caller(self, identifier: str) -> bool:
        ...

    @operation
    def save_worker_session(self, worker_id: str, session_id: str) -> None:
        ...

    @operation
    def remove_worker_session(self, worker_id: str) -> None:
        ...

    @operation
    def read_worker_sessions(self) -> Dict[str, str]:
        ...
