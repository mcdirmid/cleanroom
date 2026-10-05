# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 3918b8c73696
# COVERAGE_AUDIT: 2026-10-05T20:52:01Z
# QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

# Requirements specified in template_format_impl.pyi
import re
from typing import Any, Mapping, Optional, Sequence
from update_with_ai.parts.agent.lib.agent_session import agent_session
from . import template_format
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry

VAR_RE = re.compile(r"<([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)>")
LINE_IF_RE = re.compile(
    r"^(.+?\S)\s*<!--\s*if:\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*-->\s*$"
)
LINE_FOR_RE = re.compile(
    r"^(.+?\S)\s*<!--\s*for:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*-->\s*$"
)
BLOCK_IF_START = re.compile(
    r"^\s*<!--\s*if:\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*-->\s*$"
)
BLOCK_IF_END = re.compile(r"^\s*<!--\s*endif\s*-->\s*$")
BLOCK_FOR_START = re.compile(
    r"^\s*<!--\s*for:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*-->\s*$"
)
BLOCK_FOR_END = re.compile(r"^\s*<!--\s*endfor\s*-->\s*$")


def _resolve_lookup(path: str, context: Mapping[str, Any]) -> tuple[bool, Any]:
    parts = path.split(".")
    val: Any = context
    for p in parts:
        if isinstance(val, (dict, Mapping)) and p in val:
            val = val[p]
        elif hasattr(val, p):
            val = getattr(val, p)
        else:
            return False, None
    return True, val


def _interpolate_vars(text: str, context: Mapping[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        found, val = _resolve_lookup(key, context)
        return str(val) if found else match.group(0)

    return VAR_RE.sub(replace, text)


class TemplateFormatter(template_format.TemplateFormatter, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    def format_template(
        self,
        text: template_format.TemplateText,
        parameters: Mapping[template_format.TemplateKey, Any],
    ) -> template_format.FormattedText:
        lines = text.splitlines()
        result_lines = self._format_lines(lines, parameters)
        return template_format.FormattedText("\n".join(result_lines))

    def _format_lines(
        self, lines: Sequence[str], context: Mapping[Any, Any]
    ) -> list[str]:
        output: list[str] = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]

            m_for = LINE_FOR_RE.match(line)
            if m_for:
                tmpl, var_name, list_key = m_for.groups()
                found, items = _resolve_lookup(list_key, context)
                if found and isinstance(items, (list, tuple)):
                    for item in items:
                        sub_ctx = dict(context)
                        sub_ctx[var_name] = item
                        output.append(_interpolate_vars(tmpl, sub_ctx))
                else:
                    output.append(_interpolate_vars(tmpl, context))
                i += 1
                continue

            m_if = LINE_IF_RE.match(line)
            if m_if:
                tmpl, cond_key = m_if.groups()
                found, cond_val = _resolve_lookup(cond_key, context)
                if found:
                    if bool(cond_val):
                        output.append(_interpolate_vars(tmpl, context))
                else:
                    output.append(_interpolate_vars(tmpl, context))
                i += 1
                continue

            m_bfor = BLOCK_FOR_START.match(line)
            if m_bfor:
                var_name, list_key = m_bfor.groups()
                i += 1
                depth = 1
                body_lines: list[str] = []
                while i < n:
                    if BLOCK_FOR_START.match(lines[i]):
                        depth += 1
                    elif BLOCK_FOR_END.match(lines[i]):
                        depth -= 1
                        if depth == 0:
                            i += 1
                            break
                    body_lines.append(lines[i])
                    i += 1

                trimmed_body = self._trim_extra_boundary_newlines(body_lines)
                found, items = _resolve_lookup(list_key, context)
                if found and isinstance(items, (list, tuple)):
                    for item in items:
                        sub_ctx = dict(context)
                        sub_ctx[var_name] = item
                        rendered = self._format_lines(trimmed_body, sub_ctx)
                        output.extend(rendered)
                else:
                    rendered = self._format_lines(trimmed_body, context)
                    output.extend(rendered)
                continue

            m_bif = BLOCK_IF_START.match(line)
            if m_bif:
                cond_key = m_bif.groups()[0]
                i += 1
                depth = 1
                body_lines = []
                while i < n:
                    if BLOCK_IF_START.match(lines[i]):
                        depth += 1
                    elif BLOCK_IF_END.match(lines[i]):
                        depth -= 1
                        if depth == 0:
                            i += 1
                            break
                    body_lines.append(lines[i])
                    i += 1

                trimmed_body = self._trim_extra_boundary_newlines(body_lines)
                found, cond_val = _resolve_lookup(cond_key, context)
                if found:
                    if bool(cond_val):
                        rendered = self._format_lines(trimmed_body, context)
                        output.extend(rendered)
                else:
                    rendered = self._format_lines(trimmed_body, context)
                    output.extend(rendered)
                continue

            output.append(_interpolate_vars(line, context))
            i += 1

        return output

    def _trim_extra_boundary_newlines(self, lines: list[str]) -> list[str]:
        res = list(lines)
        if res and res[0].strip() == "":
            res = res[1:]
        if res and res[-1].strip() == "":
            res = res[:-1]
        return res


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        TemplateFormatter,
        keys=[TemplateFormatter, template_format.TemplateFormatter],
        tier=agent_session,
    )
