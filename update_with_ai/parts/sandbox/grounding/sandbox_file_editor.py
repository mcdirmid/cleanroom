# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: c898a4ef21d7
# GROUNDING_QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""Sandbox file editor grounding specification module."""

from __future__ import annotations
from typing import Any, Mapping, NewType, Optional, Protocol, Set, Union
from support.lib.grounding_support import InTier, AgentSessionTier, key, value
from parts.agent.grounding import agent_file_alias
from parts.sandbox.grounding import tool_provider

FileUpdateRevision = NewType("FileUpdateRevision", int)
LineNumber = NewType("LineNumber", int)
TargetContent = NewType("TargetContent", str)
ReplacementContent = NewType("ReplacementContent", str)
FileHash = NewType("FileHash", str)
AllowMultiple = NewType("AllowMultiple", bool)


class EditingTool(tool_provider.Tool, Protocol):
    """Polymorphic tool that modifies a read-write file."""

    @property
    def name(self) -> tool_provider.ToolName:
        """
        DEFERRED:
        - Unique name of editing tool.
        """
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        DEFERRED:
        - Human-readable description of editing tool.
        """
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        DEFERRED:
        - Parameters accepted by editing tool.
        """
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        """
        DEFERRED:
        - Execution dispatch for editing tool.
        """
        raise NotImplementedError


class EditManager(InTier[AgentSessionTier], Protocol):
    """Agent session service that installs editing tools and tracks session modifications."""

    @property
    def has_modifications(self) -> bool:
        """
        DEFERRED:
        - WHEN workspace file contents differ from their initial state prior to editing, MUST return true.
        - Deferred to sandbox_file_editor_impl.py.
        - WHEN workspace file contents match their initial state prior to editing, MUST return false.
        - Deferred to sandbox_file_editor_impl.py.
        """
        raise NotImplementedError

    @property
    def file_update_revision(self) -> FileUpdateRevision:
        """
        DEFERRED:
        - MUST return a file update revision that tracks sequential updates made to workspace files.
        - Deferred to sandbox_file_editor_impl.py.
        """
        raise NotImplementedError

    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        """
        DEFERRED:
        - MUST return the most recently read or edited file alias across the session.
        - Deferred to sandbox_file_editor_impl.py.
        """
        raise NotImplementedError

    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        """
        DEFERRED:
        - MUST record that the file was read, updating the last read or edited file in the session.
        """
        raise NotImplementedError

    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        """
        DEFERRED:
        - MUST record that the file was edited, updating the last read or edited file in the session.
        """
        raise NotImplementedError

    def file_hash(self, file: agent_file_alias.FileAlias) -> FileHash:
        """
        COVERED:
        - MUST return a file hash for the read-write file computed from its content.
          - Consequent knowledge: return FileHash string.

        DEFERRED:
        - MD5 digest computation deferred to sandbox_file_editor_impl.py.
        """
        _h = FileHash("da39a3ee5e6b4b0d3255bfef95601890afd80709")
        raise NotImplementedError

    def can_write(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        """
        DEFERRED:
        - WHEN checking write access for a workspace path or file alias matching a declared read-write file, MUST confirm access.
        - WHEN checking write access for a path that is not a declared read-write file, MUST fail with guidance.
        """
        raise NotImplementedError


class ReplaceFileContentTool(EditingTool, InTier[AgentSessionTier], Protocol):
    """Editing tool that replaces target content in a read-write file."""

    @property
    def path_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """
        DEFERRED:
        - Path parameter specification.
        """
        raise NotImplementedError

    @property
    def target_content_parameter(
        self,
    ) -> tool_provider.ToolParameter[TargetContent, str]:
        """
        DEFERRED:
        - Target content parameter specification.
        """
        raise NotImplementedError

    @property
    def replacement_content_parameter(
        self,
    ) -> tool_provider.ToolParameter[ReplacementContent, str]:
        """
        DEFERRED:
        - Replacement content parameter specification.
        """
        raise NotImplementedError

    @property
    def start_line_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[LineNumber], int]:
        """
        DEFERRED:
        - Start line parameter specification.
        """
        raise NotImplementedError

    @property
    def end_line_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[LineNumber], int]:
        """
        DEFERRED:
        - End line parameter specification.
        """
        raise NotImplementedError

    @property
    def allow_multiple_parameter(
        self,
    ) -> tool_provider.ToolParameter[AllowMultiple, bool]:
        """
        DEFERRED:
        - Allow multiple parameter specification.
        """
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - MUST replace target content with replacement content within the bounded line range.
          - Condition knowledge: access path, target_content, and replacement_content bindings.
          - Consequent knowledge: return ToolResponse.
        - WHEN multiple replacements are permitted, MUST replace multiple occurrences.
          - Condition knowledge: evaluate allow_multiple parameter binding.
          - Consequent knowledge: replace all occurrences in content.

        DEFERRED:
        - In-place text replacement algorithm, line bounds checks, and exact match fallback deferred to sandbox_file_editor_impl.py."""
        sample_param = key(actual_parameter_bindings)
        sample_val = value(actual_parameter_bindings)
        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content="Replacement completed successfully",
        )
        raise NotImplementedError
