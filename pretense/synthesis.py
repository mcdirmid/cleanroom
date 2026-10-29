"""Automated unit test synthesis from shrunken Hypothesis counterexample traces."""

from typing import Any, Dict, List, Optional
from update_python_with_ai.parts.pretense.lib.pretense import TraceStep


def synthesize_unit_test(
    test_name: str,
    proto_class_name: str,
    state_class_name: str,
    steps: List[TraceStep],
    failure_critique: Optional[str] = None,
) -> str:
    """Synthesize a pure, zero-dependency Python unit test function from a trace."""
    lines = [
        f"def {test_name}() -> None:",
        f'    """Synthesized deterministic regression test minimizing counterexample.',
    ]
    if failure_critique:
        lines.append(f"    Failure: {failure_critique}")
    lines.extend([
        '    """',
        f"    sm = {proto_class_name}.make_state_machine({state_class_name}())",
        "",
    ])

    for i, step in enumerate(steps, 1):
        args_repr = ", ".join(repr(a) for a in step.args)
        if step.is_seeding:
            lines.append(f"    # Step {i}: Seeding transition")
            lines.append(f"    sm.{step.transition_name}({args_repr})")
        else:
            lines.append(f"    # Step {i}: Method transition '{step.transition_name}'")
            if step.target_name:
                lines.append(f"    # target: {step.target_name}")
            lines.append(f"    sm.dispatch_transition({step.transition_name!r}, {args_repr})")
        lines.append("")

    lines.append("    # Verify invariants hold at conclusion")
    lines.append("    sm.check_invariants()")
    return "\n".join(lines)


__all__ = ["TraceStep", "synthesize_unit_test"]
