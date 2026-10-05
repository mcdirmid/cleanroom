# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: a2c35dc78022
# COVERAGE_AUDIT: 2026-10-05T04:28:01Z
# QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

from typing import Any, Mapping, Optional, Tuple, Union
from . import loop_guard
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.sandbox.lib import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry


class LoopGuard(loop_guard.LoopGuard, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._last_call: Optional[Tuple[str, Any]] = None
        self._consecutive_count: int = 0
        self._reminder_threshold: int = 2
        self._fatal_threshold: int = 5

    def evaluate(
        self,
        tool_name: tool_provider.ToolName,
        arguments: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> Optional[Union[loop_guard.LoopReminder, loop_guard.LoopFailure]]:
        params = {getattr(name, "name", str(name)): v for name, v in arguments.items()}
        if tool_name in ("replace_file_content", "edit_file", "edit"):
            target_file = (
                params.get("path")
                or params.get(
                    "target_file"
                )  # pragma: no cover (assumption: editing tool arguments adhere to tool parameter schema)
                or params.get(
                    "file_name"
                )  # pragma: no cover (assumption: editing tool arguments adhere to tool parameter schema)
                or ""  # pragma: no cover (assumption: editing tool arguments adhere to tool parameter schema)
            )
            start_line = params.get("start_line")
            end_line = params.get("end_line")
            if start_line is not None and end_line is not None:
                call_key = (
                    str(tool_name),
                    (str(target_file), str(start_line), str(end_line)),
                )
            elif target_file:  # pragma: no cover (assumption: editing tool arguments adhere to tool parameter schema)
                call_key = (str(tool_name), str(target_file))
            else:  # pragma: no cover (assumption: editing tool arguments adhere to tool parameter schema)
                call_key = (
                    str(tool_name),
                    frozenset(
                        (getattr(name, "name", str(name)), str(v))
                        for name, v in arguments.items()
                    ),
                )
        else:
            call_key = (
                str(tool_name),
                frozenset(
                    (getattr(name, "name", str(name)), str(v))
                    for name, v in arguments.items()
                ),
            )
        if self._last_call == call_key:
            self._consecutive_count += 1
        else:
            self._last_call = call_key
            self._consecutive_count = 1

        if self._consecutive_count >= self._fatal_threshold:
            return loop_guard.LoopFailure(
                explanation=loop_guard.FailureExplanation(
                    f"Fatal loop detected: tool '{tool_name}' executed {self._consecutive_count} times consecutively."
                )
            )
        elif self._consecutive_count >= self._reminder_threshold:
            return loop_guard.LoopReminder(
                feedback=loop_guard.LoopFeedback(
                    f"Warning: tool '{tool_name}' has been executed {self._consecutive_count} times consecutively, no new information will be revealed by this tool call until session read-write files are updated. Repeating this tool call without modifying files will trigger fatal loop termination."
                )
            )
        return None

    def reset(self) -> None:
        self._consecutive_count = 0
        self._last_call = None


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopGuard,
        keys=[LoopGuard, loop_guard.LoopGuard],
        tier=agent_session,
    )
