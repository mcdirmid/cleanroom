# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-06T12:35:00Z
# LAST_CHANGED: 2026-10-06T12:35:00Z
# CHANGE: add grounding sections
# CODE_HASH: 30e55d74c5f1
# --- END CLEANROOM METADATA ---

"""Sandbox implementation low-level specification."""

from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import sandbox
import agent_node_config
import dag_storage
import sandbox_file_editor


@singleton_type("agent_session")
class Sandbox(sandbox.Sandbox, InTier[AgentSessionTier]):
    """Realizes session template materialization and file modification tracking.

    GROUNDING:
    - Coordinates session startup and change tracking by delegating template writing
      to DagStorage, resolving session files from NodeConfig, and querying file diffs
      from EditManager within the agent session tier.
    """

    @property
    @override
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session.

        GROUNDING:
        - Grounded via EditManager.has_modifications from sandbox_file_editor,
          querying whether diff-based file mutations were recorded.
        """
        ...

    @operation
    @override
    def materialize_templates(self) -> None:
        """Materializes startup templates into missing read-write files.

        GROUNDING:
        - Grounded via NodeConfig from agent_node_config to resolve session read-write files
          and starter templates, FileAlias.owning_node to identify target nodes, and
          DagStorage.materialize_template from dag_storage to write boilerplate without
          overwriting existing files.
        """
        ...
