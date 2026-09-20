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
    # Requirement: Replaces parameter placeholder tokens matching dot-separated keys in the parameters with string representations of their resolved values.
    # Requirement: Retains parameter placeholder tokens whose keys do not resolve to values in the parameters without modification.
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        found, val = _resolve_lookup(key, context)
        return str(val) if found else match.group(0)

    return VAR_RE.sub(replace, text)


class TemplateFormatter(template_format.TemplateFormatter, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    def format_template(self, text: str, parameters: Mapping[str, Any]) -> str:
        # Requirement: [TemplateFormatter] The template formatter formats template text using parameters to produce formatted text.
        lines = text.splitlines()
        result_lines = self._format_lines(lines, parameters)
        return "\n".join(result_lines)

    def _format_lines(
        self, lines: Sequence[str], context: Mapping[str, Any]
    ) -> list[str]:
        output: list[str] = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]

            # 1. Single-line for suffix
            # Requirement: Identifies line-suffix loop comments matching collection iteration markers, repeating the preceding line content for each item in the resolved sequence with the item variable bound in the parameter context.
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
                    # Unbound: keep exemplar line with interpolated known context
                    output.append(_interpolate_vars(tmpl, context))
                i += 1
                continue

            # 2. Single-line if suffix
            # Requirement: Identifies line-suffix conditional comments matching conditional markers, retaining the preceding line content when the condition key evaluates to true and omitting the line when false.
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

            # 3. Block for
            # Requirement: Identifies block loop markers enclosing multi-line sections, repeating enclosed lines for each element in the resolved sequence with the loop variable bound in the parameter context.
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
                            i += 1  # consume endfor
                            break
                    body_lines.append(lines[i])
                    i += 1

                # Normalize formatting blank lines around comments
                # Requirement: Normalizes extraneous blank lines introduced around block directive comments by formatting tools to preserve tight list spacing.
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

            # 4. Block if
            # Requirement: Identifies block conditional markers enclosing multi-line sections, including enclosed lines when the condition key evaluates to true and omitting enclosed lines when false.
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
                            i += 1  # consume endif
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

            # Standard line
            output.append(_interpolate_vars(line, context))
            i += 1

        return output

    def _trim_extra_boundary_newlines(self, lines: list[str]) -> list[str]:
        # Prettier often inserts empty lines directly after opening comments and before closing comments
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
