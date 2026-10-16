# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:58:00Z
# CHANGE: Track independent repetition streaks for identical tool invocations and for repeated edits to the same file and line range, each with warning and fatal thresholds, and clear both on reset
# CODE_HASH: 6242a3830abb
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

from typing import Any, Mapping, Optional, Tuple, Union
from . import loop_guard
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.sandbox.lib import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry

# Tools whose arguments name a session read-write file and an edited line range.
_EDIT_TOOLS = ("replace_file_content", "edit_file", "edit")

# Threshold of two repetitions that warns an agent of a detected repetition.
_WARNING_THRESHOLD = 2

# Repetition count at which a detected repetition terminates the session.
_FATAL_THRESHOLD = 3


def _parameter_name(parameter: Any) -> str:
    return str(getattr(parameter, "name", parameter))


class LoopGuard(loop_guard.LoopGuard, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._last_call: Optional[Tuple[str, Any]] = None
        self._consecutive_count: int = 0
        self._last_edit: Optional[Tuple[str, Any, Any]] = None
        self._edit_count: int = 0

    def _edit_location(
        self,
        tool_name: tool_provider.ToolName,
        arguments: Mapping[
            tool_provider.ToolParameter[Any, Any],
            tool_provider.SomeParameterActualType,
        ],
    ) -> Optional[Tuple[str, Any, Any]]:
        params = {_parameter_name(name): value for name, value in arguments.items()}
        target_file = (
            params.get("path")
            or params.get("target_file")
            or params.get("file_name")
            or ""
        )
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        if not target_file:
            return None
        return (str(tool_name), str(target_file), (start_line, end_line))

    def evaluate(
        self,
        tool_name: tool_provider.ToolName,
        arguments: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> Optional[Union[loop_guard.LoopReminder, loop_guard.LoopFailure]]:
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

        edit_location: Optional[Tuple[str, Any, Any]] = None
        if str(tool_name) in _EDIT_TOOLS:
            edit_location = self._edit_location(tool_name, arguments)
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
            return loop_guard.LoopFailure(
                explanation=loop_guard.FailureExplanation(
                    f"Fatal loop detected: tool '{tool_name}' executed "
                    f"{self._consecutive_count} times consecutively."
                )
            )
        if self._edit_count >= _FATAL_THRESHOLD:
            return loop_guard.LoopFailure(
                explanation=loop_guard.FailureExplanation(
                    f"Fatal loop detected: the same file and line range were edited "
                    f"{self._edit_count} times consecutively."
                )
            )
        if self._consecutive_count >= _WARNING_THRESHOLD:
            return loop_guard.LoopReminder(
                feedback=loop_guard.LoopFeedback(
                    f"Warning: tool '{tool_name}' has been executed "
                    f"{self._consecutive_count} times consecutively, no new information "
                    "will be revealed by this tool call until session read-write files "
                    "are updated. Repeating this tool call without modifying files will "
                    "trigger fatal loop termination."
                )
            )
        if self._edit_count >= _WARNING_THRESHOLD:
            return loop_guard.LoopReminder(
                feedback=loop_guard.LoopFeedback(
                    f"Warning: the same file and line range were edited "
                    f"{self._edit_count} times consecutively, no new information will be "
                    "revealed until session read-write files are updated. Repeating this "
                    "edit without changing the file or line range will trigger fatal loop "
                    "termination."
                )
            )
        return None

    def reset(self) -> None:
        self._consecutive_count = 0
        self._last_call = None
        self._edit_count = 0
        self._last_edit = None


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopGuard,
        keys=[LoopGuard, loop_guard.LoopGuard],
        tier=agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
