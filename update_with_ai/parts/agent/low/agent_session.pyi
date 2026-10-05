# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: a2f2b4bf21f6
# --- END CLEANROOM METADATA ---

"""Agent session lifecycle tier component."""

from framework import singleton_type
from support.lib.lifecycle import ChildTierOf, SystemTier


@singleton_type("system")
class AgentSessionTier(ChildTierOf[SystemTier]):
    """Lifecycle tier governing per-session agent execution subordinate to the system tier.

    INVARIANTS:
    - The agent session lifecycle tier is defined under the system lifecycle tier.
    """
    ...
