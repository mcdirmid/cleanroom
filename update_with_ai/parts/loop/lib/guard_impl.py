from typing import Any, Mapping, Optional, Tuple, Union
from . import guard
from update_with_ai.parts.agent.lib.session import session as agent_session
from update_with_ai.parts.sandbox.lib import file_editor, tool_provider
from support.lib.lifecycle import (
    LifecycleIsolationError,
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)

# Threshold of two repetitions that warns an agent of a detected repetition.
_WARNING_THRESHOLD = 2

# Repetition count at which a detected repetition terminates the session.
_FATAL_THRESHOLD = 4


def _parameter_name(parameter: Any) -> str:
    if hasattr(parameter, "name"):
        return str(parameter.name)
    return str(parameter)


class LoopGuard(guard.LoopGuard):
    tier = agent_session

    def __init__(self) -> None:
        self._last_call: Optional[Tuple[str, Any]] = None
        self._consecutive_count: int = 0
        self._last_edit: Optional[Tuple[str, Any, Any]] = None
        self._edit_count: int = 0

    def _get_editing_tool(self) -> Optional[file_editor.EditingTool]:
        try:
            return get_singleton(file_editor.EditingTool)
        except (LifecycleResolutionError, LifecycleIsolationError, Exception):
            return None

    def _edit_location(
        self,
        edit_tool: file_editor.EditingTool,
        arguments: Mapping[
            tool_provider.ToolParameter[Any, Any],
            tool_provider.SomeParameterActualType,
        ],
    ) -> Optional[Tuple[str, Any, Any]]:
        path_param = edit_tool.path_parameter
        start_param = edit_tool.start_line_parameter
        end_param = edit_tool.end_line_parameter

        target_file = None
        start_line = None
        end_line = None

        path_name = str(getattr(path_param, "name", path_param))
        start_name = (
            str(getattr(start_param, "name", start_param))
            if start_param is not None
            else None
        )
        end_name = (
            str(getattr(end_param, "name", end_param))
            if end_param is not None
            else None
        )

        for param, value in arguments.items():
            param_key = _parameter_name(param)
            if param == path_param or param_key == path_name:
                target_file = value
            elif start_param is not None and (
                param == start_param or param_key == start_name
            ):
                start_line = value
            elif end_param is not None and (
                param == end_param or param_key == end_name
            ):
                end_line = value

        if not target_file:
            return None
        return (str(edit_tool.name), str(target_file), (start_line, end_line))

    # Contract: LoopGuard.evaluate - tracks consecutive identical tool executions and consecutive edits, producing LoopReminder at warning threshold (2) or LoopFailure at fatal threshold (4).
    def evaluate(
        self,
        tool_name: tool_provider.ToolName,
        arguments: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> Optional[Union[guard.LoopReminder, guard.LoopFailure]]:
        signature = (
            str(tool_name),
            frozenset(
                (_parameter_name(name), repr(value))
                for name, value in arguments.items()
            ),
        )
        if self._last_call == signature:
            self._consecutive_count += 1
        else:
            self._last_call = signature
            self._consecutive_count = 1

        edit_tool = self._get_editing_tool()
        edit_location: Optional[Tuple[str, Any, Any]] = None
        if edit_tool is not None and str(tool_name) == str(edit_tool.name):
            edit_location = self._edit_location(edit_tool, arguments)

        if edit_location is not None:
            if self._last_edit == edit_location:
                self._edit_count += 1
            else:
                self._last_edit = edit_location
                self._edit_count = 1
        else:
            self._last_edit = None
            self._edit_count = 0

        if self._consecutive_count >= _FATAL_THRESHOLD:
            return guard.LoopFailure(
                explanation=guard.FailureExplanation(
                    f"Fatal loop detected: tool '{tool_name}' executed "
                    f"{self._consecutive_count} times consecutively."
                )
            )
        if self._edit_count >= _FATAL_THRESHOLD:
            return guard.LoopFailure(
                explanation=guard.FailureExplanation(
                    f"Fatal loop detected: the same file and line range were edited "
                    f"{self._edit_count} times consecutively."
                )
            )
        if self._consecutive_count >= _WARNING_THRESHOLD:
            edit_action = (
                f"use '{edit_tool.name}' to modify files"
                if edit_tool is not None
                else "modify files"
            )
            return guard.LoopReminder(
                feedback=guard.LoopFeedback(
                    f"ACTION REQUIRED: tool '{tool_name}' has been executed "
                    f"{self._consecutive_count} times consecutively without modifying files. "
                    f"You must {edit_action}, "
                    "or conclude the round with 'blame' or 'fail' before executing this tool again. "
                    "No new information will be revealed until session read-write files are updated. "
                    "Repeating this tool call without modifying files will trigger fatal loop termination."
                )
            )
        if self._edit_count >= _WARNING_THRESHOLD:
            return guard.LoopReminder(
                feedback=guard.LoopFeedback(
                    f"Warning: the same file and line range were edited "
                    f"{self._edit_count} times consecutively, no new information will be "
                    "revealed until session read-write files are updated. Repeating this "
                    "edit without changing the file or line range will trigger fatal loop "
                    "termination."
                )
            )
        return None

    # Contract: LoopGuard.reset - reinitializes consecutive tool call counter, edit counter, and recorded signatures upon forward progress.
    def reset(self) -> None:
        self._consecutive_count = 0
        self._last_call = None
        self._edit_count = 0
        self._last_edit = None
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-21T20:00:00Z
# LAST_CHANGED: 2026-10-21T20:00:00Z
# CHANGE: Eliminate hardcoded edit tool names and dynamically resolve file_editor.EditingTool
# COVERAGE_AUDIT: 2026-10-21T20:00:00Z
# QA_AUDIT: 2026-10-21T20:00:00Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopGuard,
        keys=[LoopGuard, guard.LoopGuard],
        tier=agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
