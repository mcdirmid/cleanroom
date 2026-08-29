# lib/runner_logger.py
"""
Interface definitions for the LLS RunnerLogger.
"""

from typing import Any, Callable, Dict, Optional, Protocol, Tuple
from .conversation_history import LogEvent, LoggerCallback


class RunnerLogger(Protocol):
    def resolve_log_path(self) -> str:
        ...

    def format_compact_log(self, event: LogEvent, data: Dict[str, Any]) -> Optional[str]:
        ...

    def format_full_log(self, event: LogEvent, data: Dict[str, Any]) -> str:
        ...

    def create_agent_logger(self, log_path: str) -> Tuple[LoggerCallback, Callable[[], None]]:
        ...
