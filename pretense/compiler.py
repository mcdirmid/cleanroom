"""Hypothesis stateful test case generation for Pretense prototypes."""

from typing import Any, List, Optional
import update_python_with_ai.parts.pretense.lib.pretense_impl as _impl

_ACTIVE_STEP: Any = None
_ACTIVE_TRACE: List[Any] = []


def get_active_step() -> Any:
    global _ACTIVE_STEP
    if _ACTIVE_STEP is not None:
        return _ACTIVE_STEP
    return _impl.get_active_step()


def get_active_trace() -> List[Any]:
    global _ACTIVE_TRACE
    if _ACTIVE_TRACE:
        return list(_ACTIVE_TRACE)
    return _impl.get_active_trace()


def format_active_step_diagnostic(*args: Any, **kwargs: Any) -> Optional[str]:
    global _ACTIVE_STEP, _ACTIVE_TRACE
    if _ACTIVE_STEP is not None:
        lines = [
            f"Active Pretense Transition: '{_ACTIVE_STEP.transition_name}' (method: {_ACTIVE_STEP.target_name or '<seeding>'})",
            f"Arguments: {_ACTIVE_STEP.args!r}",
        ]
        if len(_ACTIVE_TRACE) > 1:
            lines.append(f"Preceding Steps ({len(_ACTIVE_TRACE) - 1}):")
            for i, step in enumerate(_ACTIVE_TRACE[:-1], 1):
                args_str = ", ".join(repr(a) for a in step.args)
                lines.append(f"  {i}. {step.transition_name}({args_str})")
        return "\n".join(lines)
    return _impl.format_active_step_diagnostic(*args, **kwargs)


compile_hypothesis_test_case = _impl.compile_hypothesis_test_case

__all__ = [
    "compile_hypothesis_test_case",
    "format_active_step_diagnostic",
    "get_active_step",
    "get_active_trace",
]
