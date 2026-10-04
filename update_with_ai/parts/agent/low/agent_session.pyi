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
