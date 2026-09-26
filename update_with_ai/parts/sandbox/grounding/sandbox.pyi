from typing import Protocol
from framework import operation, singleton_type


@singleton_type("agent_session")
class Sandbox(Protocol):
    """Defined as an agent session service coordinating starter template materialization and file modification tracking."""

    @property
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session.

        REQUIREMENTS:
        - The sandbox exposes whether workspace file modifications occurred during the session.

        GROUNDING_PROVISIONS:
        - knows("has_modifications", bool): Exposes whether file modifications occurred to satisfy requirement 1.
        """
        ...

    @operation
    def materialize_startup_templates(self) -> None:
        """Materializes starter templates into missing read-write files at session start.

        REQUIREMENTS:
        - Materializing startup templates populates missing read-write files without overwriting existing files.

        GROUNDING_PROVISIONS:
        - action("materialize_startup_templates", None): Populates initial files to satisfy requirement 2.
        """
        ...
