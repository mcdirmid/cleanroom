# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-09T04:43:52Z
# CHANGE: Eliminate unreachable negation branches in _eval_condition
# CODE_HASH: 9b80951c2098
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

import re
from typing import Any, List, Mapping, Optional, Sequence, Tuple
from support.lib.lifecycle import (
    InTier,
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier, agent_session
from . import template_format

# Requirements specified in template_format_impl.pyi

PLACEHOLDER_PATTERN = re.compile(r"<([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*)>")
DIRECTIVE_STRIP = re.compile(r"<!--\s*(?:IF|ENDIF|FOR|ENDFOR)[^>]*-->")


def _lookup_path(path: str, context: Mapping[str, Any]) -> Tuple[bool, Any]:
    parts = path.strip().split(".")
    curr: Any = context
    for part in parts:
        if isinstance(curr, Mapping):
            if part in curr:
                curr = curr[part]
            else:
                return False, None
        elif hasattr(curr, part):
            curr = getattr(curr, part)
        else:
            return False, None
    return True, curr


def _eval_condition(cond_path: str, context: Mapping[str, Any]) -> bool:
    found, val = _lookup_path(cond_path.strip(), context)
    if not found:
        return True
    return bool(val)


def _resolve_path(path: str, context: Mapping[str, Any]) -> Any:
    found, val = _lookup_path(path, context)
    return val if found else None


def _substitute_placeholders(text: str, context: Mapping[str, Any]) -> str:
    def _repl(match: re.Match[str]) -> str:
        var_path = match.group(1)
        found, val = _lookup_path(var_path, context)
        if found:
            return str(val) if val is not None else ""
        return match.group(0)

    res = PLACEHOLDER_PATTERN.sub(_repl, text)
    return DIRECTIVE_STRIP.sub("", res)


def _render_lines(lines: Sequence[str], context: Mapping[str, Any]) -> List[str]:
    output: List[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        m_for = re.match(r"^\s*<!--\s*FOR\s+([a-zA-Z0-9_]+)\s+IN\s+([^\s]+)\s*-->\s*$", line)
        if m_for:
            item_var = m_for.group(1)
            list_path = m_for.group(2)
            block_lines: List[str] = []
            depth = 1
            i += 1
            while i < n:
                if re.match(r"^\s*<!--\s*FOR\s+", lines[i]):
                    depth += 1
                elif re.match(r"^\s*<!--\s*ENDFOR\s*-->\s*$", lines[i]):
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                block_lines.append(lines[i])
                i += 1

            coll = _resolve_path(list_path, context)
            if coll and isinstance(coll, (list, tuple, set, Sequence)):
                for elem in coll:
                    child_ctx = {**context, item_var: elem}
                    output.extend(_render_lines(block_lines, child_ctx))
            continue

        m_if = re.match(r"^\s*<!--\s*IF\s+([^\s]+)\s*-->\s*$", line)
        if m_if:
            cond_path = m_if.group(1)
            block_lines = []
            depth = 1
            i += 1
            while i < n:
                if re.match(r"^\s*<!--\s*IF\s+", lines[i]):
                    depth += 1
                elif re.match(r"^\s*<!--\s*ENDIF\s*-->\s*$", lines[i]):
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                block_lines.append(lines[i])
                i += 1

            if _eval_condition(cond_path, context):
                output.extend(_render_lines(block_lines, context))
            continue

        m_line_for = re.match(r"^(.*?)\s*<!--\s*FOR\s+([a-zA-Z0-9_]+)\s+IN\s+([^\s]+)\s*-->\s*$", line)
        if m_line_for:
            content_part = m_line_for.group(1)
            item_var = m_line_for.group(2)
            list_path = m_line_for.group(3)
            coll = _resolve_path(list_path, context)
            if coll and isinstance(coll, (list, tuple, set, Sequence)):
                for elem in coll:
                    child_ctx = {**context, item_var: elem}
                    output.append(_substitute_placeholders(content_part, child_ctx))
            i += 1
            continue

        m_line_if = re.match(r"^(.*?)\s*<!--\s*IF\s+([^\s]+)\s*-->\s*$", line)
        if m_line_if:
            content_part = m_line_if.group(1)
            cond_path = m_line_if.group(2)
            if _eval_condition(cond_path, context):
                output.append(_substitute_placeholders(content_part, context))
            i += 1
            continue

        output.append(_substitute_placeholders(line, context))
        i += 1

    return output


class TemplateFormatter(template_format.TemplateFormatter, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    def format_template(
        self,
        text: template_format.TemplateText,
        parameters: Mapping[template_format.TemplateKey, Any],
    ) -> template_format.FormattedText:
        lines = str(text).splitlines()
        rendered_lines = _render_lines(lines, {str(k): v for k, v in parameters.items()})
        res = "\n".join(rendered_lines)
        if str(text).endswith("\n"):
            res += "\n"
        res = re.sub(r"\n{3,}", "\n\n", res)
        return template_format.FormattedText(res)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        TemplateFormatter,
        keys=[TemplateFormatter, template_format.TemplateFormatter, InTier[AgentSessionTier]],
        tier=agent_session,
    )

_initialize_ = __initialize__
