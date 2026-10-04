"""CommonMark external boundary grounding specification."""

from __future__ import annotations
import re
from typing import Any, Mapping, Optional, Sequence

PLACEHOLDER_PATTERN: re.Pattern[str] = re.compile(
    r"<([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*)>"
)
BLOCK_IF_START: re.Pattern[str] = re.compile(r"<!--\s*IF\s+([^\s]+)\s*-->")
BLOCK_IF_END: re.Pattern[str] = re.compile(r"<!--\s*ENDIF\s*-->")
BLOCK_FOR_START: re.Pattern[str] = re.compile(
    r"<!--\s*FOR\s+([a-zA-Z0-9_]+)\s+IN\s+([a-zA-Z0-9_.]+)\s*-->"
)
BLOCK_FOR_END: re.Pattern[str] = re.compile(r"<!--\s*ENDFOR\s*-->")
LINE_IF_PATTERN: re.Pattern[str] = re.compile(r"<!--\s*IF\s+([^\s]+)\s*-->\s*$")
LINE_FOR_PATTERN: re.Pattern[str] = re.compile(
    r"<!--\s*FOR\s+([a-zA-Z0-9_]+)\s+IN\s+([a-zA-Z0-9_.]+)\s*-->\s*$"
)


def find_placeholders(text: str) -> Sequence[str]:
    """
    COVERED:
    - Extracts all parameter placeholders matching '<parameter.path>' from the input text.
    """
    _matches: Sequence[str] = PLACEHOLDER_PATTERN.findall(text)
    raise NotImplementedError


def substitute_parameters(text: str, context: Mapping[str, Any]) -> str:
    """
    COVERED:
    - Substitutes parameter placeholders with evaluated context values.
    """
    _first_match: Optional[re.Match[str]] = PLACEHOLDER_PATTERN.search(text)
    _keys: Sequence[str] = list(context.keys())
    raise NotImplementedError

