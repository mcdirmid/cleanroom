# Requirements specified in sandbox.pyi
from typing import Protocol


class Sandbox(Protocol):
    @property
    def has_modifications(self) -> bool: ...

    def materialize_startup_templates(self) -> None: ...
