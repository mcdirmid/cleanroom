# Requirements specified in antigravity_sandbox_gate.pyi
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Tuple


@dataclass(frozen=True)
class GatingDecision:
    decision: str
    reason: str
    overwrite: Optional[Dict[str, Any]] = None


class AntigravitySandboxGate(Protocol):
    def process_hook_input(self, payload: str) -> GatingDecision: ...

    def validate_worker_command(self, command_line: str) -> Tuple[bool, str]: ...

    def is_coordinator_caller(self, identifier: str) -> bool: ...

    def is_role_worker_caller(self, identifier: str) -> bool: ...

    def save_worker_session(self, worker_id: str, session_id: str) -> None: ...

    def remove_worker_session(self, worker_id: str) -> None: ...

    def read_worker_sessions(self) -> Dict[str, str]: ...
