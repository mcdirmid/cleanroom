from typing import Self
from framework import operation, override, singleton_type
import sandbox
import sandbox_file_editor


@singleton_type("agent_session")
class Sandbox(sandbox.Sandbox):
    """Implements sandbox to coordinate starter template materialization and file modification tracking.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, Sandbox coordinates template materialization and file modification queries, accessing collaborator singleton sandbox_file_editor.EditManager in the same session lifecycle tier.
    """

    @property
    @override
    def has_modifications(self) -> bool:
        """Queries the edit manager to determine if workspace files were modified.

        REQUIREMENTS:
        - Querying file modifications delegates to the edit manager.

        GROUNDING_PROVISIONS:
        - knows("has_modifications", bool): Reports file modifications to satisfy requirement 1.

        GROUNDING_ARGUMENT:
        - knows("has_modifications", Self) :- knows("has_modifications", sandbox_file_editor.EditManager).
        """
        ...

    @operation
    @override
    def materialize_startup_templates(self) -> None:
        """Materializes startup templates by delegating to the edit manager.

        REQUIREMENTS:
        - Materializing startup templates delegates to the edit manager to write template content to missing read-write files without overwriting existing files.

        GROUNDING_PROVISIONS:
        - action("materialize_startup_templates", None): Delegates template materialization to satisfy requirement 2.

        GROUNDING_ARGUMENT:
        - action("materialize_startup_templates", Self) :- action("materialize_templates", sandbox_file_editor.EditManager).
        """
        ...
