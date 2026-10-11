# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:02Z
# LAST_CHANGED: 2026-10-11T03:06:35Z
# CHANGE: Align agent session tier with the simplified agent definition and system tier relationship
# CODE_HASH: f42f7c539a61
# SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
# --- END CLEANROOM METADATA ---

"""Agent session lifecycle tier component."""

from framework import singleton_type
from support.lib.lifecycle import ChildTierOf, SystemTier


@singleton_type("system")
class AgentSessionTier(ChildTierOf[SystemTier]):
    """Lifecycle tier bounding the execution, conversation, and ephemeral state of an agent under the system lifecycle tier."""
    ...
