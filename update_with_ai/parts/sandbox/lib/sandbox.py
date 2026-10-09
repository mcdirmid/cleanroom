# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-08T00:44:00Z
# LAST_CHANGED: 2026-10-08T00:44:00Z
# CHANGE: Remove materialize_templates from Sandbox protocol
# CODE_HASH: 60e70ad12195
# --- END CLEANROOM METADATA ---

# Requirements specified in sandbox.pyi
from typing import Protocol


class Sandbox(Protocol):
    @property
    def has_modifications(self) -> bool: ...
