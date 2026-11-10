"""markdown_preprocessor.py — CommonMark HTML comment conditional block evaluator for Autofab."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Optional, Sequence, Set

try:
    from . import experiments
except ImportError:
    import experiments  # type: ignore

_RE_IF = re.compile(r"^\s*<!--\s*(?:if:|if)\s+(.+?)\s*-->\s*$", re.IGNORECASE)
_RE_ELIF = re.compile(r"^\s*<!--\s*(?:elif:|elif)\s+(.+?)\s*-->\s*$", re.IGNORECASE)
_RE_ELSE = re.compile(r"^\s*<!--\s*else\s*-->\s*$", re.IGNORECASE)
_RE_ENDIF = re.compile(r"^\s*<!--\s*endif\s*-->\s*$", re.IGNORECASE)
_RE_LINE_SUFFIX_IF = re.compile(
    r"^(.*?)\s*<!--\s*(?:if:|if)\s+(.+?)\s*-->\s*$", re.IGNORECASE
)


@dataclass
class _BlockState:
    satisfied: bool
    emitting: bool
    parent_emitting: bool
    lineno: int


def eval_condition(expr: str, active_experiments: Set[str]) -> bool:
    """Evaluates a conditional expression string against the active experiment set.

    Supports:
    - experiment:<name>, experiment.<name>, or <name>
    - not <expr>
    - <expr1> and <expr2>
    - <expr1> or <expr2>
    - (<expr>)
    """
    norm_expr = expr.strip()
    # Normalize experiment:name -> name
    norm_expr = re.sub(r"\bexperiment:([a-zA-Z0-9_]+)\b", r"\1", norm_expr)

    try:
        parsed = ast.parse(norm_expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid conditional expression syntax: '{expr}'") from e

    def _eval(node: ast.AST) -> bool:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        elif isinstance(node, ast.Name):
            nid = node.id.lower()
            if nid in ("true", "1"):
                return True
            if nid in ("false", "0"):
                return False
            return nid.replace("-", "_") in active_experiments
        elif isinstance(node, ast.Attribute):
            # e.g. experiment.structured_blame
            return node.attr.lower().replace("-", "_") in active_experiments
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _eval(node.operand)
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(_eval(v) for v in node.values)
            elif isinstance(node.op, ast.Or):
                return any(_eval(v) for v in node.values)
        raise ValueError(
            f"Unsupported AST node in condition '{expr}': {type(node).__name__}"
        )

    return _eval(parsed)


def preprocess_markdown(
    content: str,
    active_experiments: Optional[Set[str]] = None,
    filename: str = "<string>",
) -> str:
    """Evaluates CommonMark HTML comment conditional blocks against active experiments.

    Inactive branches and comment directives are cleanly stripped, leaving pure Markdown text.
    """
    # Fast path: if no directives exist, return content verbatim
    if "<!--" not in content:
        return content
    content_lower = content.lower()
    if (
        "if" not in content_lower
        and "else" not in content_lower
        and "endif" not in content_lower
    ):
        return content

    if active_experiments is None:
        active_experiments = experiments.get_active_experiments()

    lines = content.splitlines()
    output_lines: list[str] = []
    stack: list[_BlockState] = []

    for lineno, line in enumerate(lines, start=1):
        m_if = _RE_IF.match(line)
        if m_if:
            expr = m_if.group(1)
            cond_met = eval_condition(expr, active_experiments)
            parent_emit = stack[-1].emitting if stack else True
            emit = parent_emit and cond_met
            stack.append(
                _BlockState(
                    satisfied=cond_met,
                    emitting=emit,
                    parent_emitting=parent_emit,
                    lineno=lineno,
                )
            )
            continue

        m_elif = _RE_ELIF.match(line)
        if m_elif:
            if not stack:
                raise ValueError(
                    f"{filename}:{lineno}: error: dangling '<!-- elif -->' directive without preceding if"
                )
            expr = m_elif.group(1)
            cond_met = eval_condition(expr, active_experiments)
            state = stack[-1]
            if not state.satisfied and cond_met:
                state.satisfied = True
                state.emitting = state.parent_emitting
            else:
                state.emitting = False
            continue

        m_else = _RE_ELSE.match(line)
        if m_else:
            if not stack:
                raise ValueError(
                    f"{filename}:{lineno}: error: dangling '<!-- else -->' directive without preceding if"
                )
            state = stack[-1]
            if not state.satisfied:
                state.satisfied = True
                state.emitting = state.parent_emitting
            else:
                state.emitting = False
            continue

        m_endif = _RE_ENDIF.match(line)
        if m_endif:
            if not stack:
                raise ValueError(
                    f"{filename}:{lineno}: error: dangling '<!-- endif -->' directive without preceding if"
                )
            stack.pop()
            continue

        # If inside a suppressed branch, discard line
        if stack and not stack[-1].emitting:
            continue

        # Check for line-suffix conditional: e.g. "some text <!-- if experiment:foo -->"
        m_suffix = _RE_LINE_SUFFIX_IF.match(line)
        if m_suffix:
            prefix = m_suffix.group(1)
            expr = m_suffix.group(2)
            if eval_condition(expr, active_experiments):
                output_lines.append(prefix.rstrip())
            continue

        output_lines.append(line)

    if stack:
        unclosed = stack[-1]
        raise ValueError(
            f"{filename}:{unclosed.lineno}: error: unclosed '<!-- if -->' conditional block"
        )

    if not output_lines:
        return ""

    result = "\n".join(output_lines)
    if content.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result
