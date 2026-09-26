from support.lib.lifecycle import ChildTierOf, SystemTier
from framework import singleton_type


@singleton_type("system")
class AgentSessionTier(ChildTierOf[SystemTier]):
    """Lifecycle tier governing per-session agent execution subordinate to the system tier."""
    ...
