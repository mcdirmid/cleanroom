"""Sandbox run control low-level interface specification."""

from typing import Any, Mapping, Optional, Protocol, Sequence, Set
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import file_alias
import node_config
import dag_storage
import tool_provider


@singleton_type("agent_session")
class CheckFilesTool(tool_provider.Tool, Singleton[AgentSessionTier], Protocol):
    """Tool that inspects verification checks across active files."""

    @property
    @override
    def name(self) -> tool_provider.ToolName:
        """Name of the tool.

        POSTCONDITIONS:
        - MUST return 'check_files'.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """Executes verification inspection.

        Args:
            actual_parameter_bindings: Tool parameter bindings.

        Returns:
            Response containing verification outcomes.

        POSTCONDITIONS:
        - WHEN verification results are outdated, MUST update verification results.
        - MUST evaluate verification checks across open targets and modified workspace files.
        - MUST present aggregated verification outcomes.
        - MUST track last tested file hashes.
        - WHEN verification fails, MUST fail.
        """
        ...


@singleton_type("agent_session")
class AdvanceTool(tool_provider.Tool, Singleton[AgentSessionTier], Protocol):
    """Tool that advances progressive guide steps upon passing verification."""

    @property
    @override
    def name(self) -> tool_provider.ToolName:
        """Name of the tool.

        POSTCONDITIONS:
        - MUST return 'advance'.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """Executes guide milestone advancement.

        Args:
            actual_parameter_bindings: Tool parameter bindings.

        Returns:
            Response delivering next milestone or failure feedback.

        POSTCONDITIONS:
        - WHEN verification passes, MUST coordinate step progression through guide delivery.
        """
        ...


@singleton_type("agent_session")
class GetWorkTool(tool_provider.Tool, Singleton[AgentSessionTier], Protocol):
    """Tool that retrieves active dirty nodes for processing."""

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """Acquires dirty nodes for execution.

        Args:
            actual_parameter_bindings: Tool parameter bindings.

        Returns:
            Response delivering session task prompt or idle message.

        POSTCONDITIONS:
        - MUST retrieve active dirty nodes.
        - MUST materialize startup templates.
        - MUST deliver the session task prompt, resolving the primary guide file from provisioned read-only documentation when omitted from node configuration.
        - WHEN in guide step mode, MUST specify follow-up execution of advance tool.
        """
        ...


@singleton_type("agent_session")
class RunController(Singleton[AgentSessionTier], Protocol):
    """Coordinates session termination tools and verification caching."""

    @operation
    def initialize(self) -> None:
        """Initializes session outcome tools upon agent session entry.

        POSTCONDITIONS:
        - MUST unconditionally install the submit tool, fail tool, check files tool, get work tool, and blame tool.
        - WHEN guide step mode is active, MUST install the advance tool.
        """
        ...

    @property
    def verification_checks(self) -> Sequence[node_config.VerificationCheck]:
        """Exposes verification checks validating session criteria.

        POSTCONDITIONS:
        - MUST return verification checks that validate session criteria.
        """
        ...

    @property
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[file_alias.BoundFile]]:
        """Exposes per-node blame targets eligible for defect attribution."""
        ...

    @property
    def is_passed(self) -> bool:
        """Exposes whether the latest verification evaluation passed.

        POSTCONDITIONS:
        - MUST return True when all verification checks passed, or False otherwise.
        """
        ...

    @property
    def is_unchanged(self) -> bool:
        """Exposes whether target file hashes are unchanged since the last evaluation.

        POSTCONDITIONS:
        - MUST return True when target file hashes are unchanged, or False otherwise.
        """
        ...

    @property
    def diagnostic_output(self) -> str:
        """Exposes aggregated diagnostic output from failing verification checks.

        POSTCONDITIONS:
        - MUST return aggregated diagnostic text from failing verification checks.
        """
        ...

    @operation
    def update_verification(self) -> None:
        """Updates and caches verification results if outdated.

        POSTCONDITIONS:
        - MUST cache verification evaluation results alongside target node file hashes.
        - WHEN no workspace files have been updated, MUST reuse cached verification outcome.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T18:30:00Z
# CHANGE: Update run_control low-level interface specification
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
