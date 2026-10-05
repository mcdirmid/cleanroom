# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: f33ee7b3f27e
# --- END CLEANROOM METADATA ---

# Requirements specified in sandbox.pyi
from typing import Protocol


class Sandbox(Protocol):
    @property
    def has_modifications(self) -> bool: ...

    def materialize_templates(self) -> None: ...
