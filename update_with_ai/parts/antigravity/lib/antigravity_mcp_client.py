# Requirements specified in antigravity_mcp_client.pyi
from __future__ import annotations

from typing import Any, Mapping


class AntigravityMcpClient:
    def call_tool(self, name: str, arguments: Mapping[str, Any], port: int = 8765) -> str:
        raise NotImplementedError

    def register_session(self, identifier: str, role: str, unit: str, port: int = 8765) -> str:
        raise NotImplementedError

    def deregister_session(self, identifier: str, port: int = 8765) -> str:
        raise NotImplementedError

    def get_work(self, identifier: str, port: int = 8765) -> str:
        raise NotImplementedError

    def check_files(self, identifier: str, port: int = 8765) -> str:
        raise NotImplementedError

    def submit(self, identifier: str, target: str, summary: str, port: int = 8765) -> str:
        raise NotImplementedError

    def blame(self, identifier: str, target: str, blame_target: str, explanation: str, port: int = 8765) -> str:
        raise NotImplementedError

    def shutdown(self, port: int = 8765) -> str:
        raise NotImplementedError

    def next_batch(self, unit: str, port: int = 8765) -> str:
        raise NotImplementedError
