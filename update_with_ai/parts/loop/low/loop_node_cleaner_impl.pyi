# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T12:45:00Z
# CHANGE: add grounding sections
# CODE_HASH: 7b6f7f52b0be
# --- END CLEANROOM METADATA ---

"""Loop node cleaner implementation low-level specification."""

from typing import Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import dag_storage
import loop_node_cleaner


@singleton_type("system")
class NodeCleaner(loop_node_cleaner.NodeCleaner, InTier[SystemTier]):
    """Realizes node clean execution, session seeding, and message dispatch.

    GROUNDING:
    - Binds abstract node cleaning directives to agent session phases, driving turns
      via LoopDriver, and translating outcomes into in-band graph storage mutations.
    """

    @operation
    @override
    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool:
        """Cleans dirty nodes within an agent session phase.

        Args:
            nodes: The sequence of dirty nodes sharing a role to clean.

        Returns:
            True if processing should continue, or False if an unhandleable failure occurred.

        GROUNDING:
        - Grounded via establishing agent session phase, initializing conversation with
          instructions to call get_work, executing turns via LoopDriver.drive, retrying once
          on unexpected failures, resolving promptless nodes directly, and mutating DagStorage
          node cleanliness and feedback messages according to turn termination outcomes.

        POSTCONDITIONS:
        - MUST clean dirty nodes within an agent session phase presenting the node role.
        - MUST retry the session phase once upon encountering an unexpected failure before propagating.
        - WHEN the outcome signals advancement with file modifications, MUST mark the nodes clean in graph storage with the change summary.
        - WHEN the outcome signals advancement without file modifications, MUST mark the nodes clean without advancing last changed timestamps.
        - WHEN the outcome signals blame attributed to a configured blame target, MUST deliver feedback messages strictly to the declared feedback dependency node owning the blamed file.
        - WHEN the outcome signals blame attributed to a target failing to match a configured blame target, MUST produce no propagating messages and leave nodes dirty.
        - MUST NOT deliver feedback messages to non-feedback dependencies, guides, or fixed node specifications.
        - WHEN the outcome signals run failure, MUST leave nodes dirty and return false.
        - WHEN dirty nodes define no task prompt, MUST resolve pass-through changes without establishing an agent session.
        """
        ...
