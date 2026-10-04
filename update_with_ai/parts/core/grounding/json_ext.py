"""JSON external boundary grounding specification."""

from __future__ import annotations
from typing import Any, Mapping


def parse_json(text: str) -> Any:
    """
    COVERED:
    - Parses a JSON string into Python objects.
    """
    _text: str = text
    _sample: Mapping[str, Any] = {"key": "value"}
    raise NotImplementedError


def dump_json(obj: Any, sort_keys: bool = True) -> str:
    """
    COVERED:
    - Serializes Python objects into a JSON string with deterministic key order.
    """
    _obj: Any = obj
    _sort: bool = sort_keys
    _out: str = "{}"
    raise NotImplementedError


def repair_truncated_json(raw_json: str) -> str:
    """
    COVERED:
    - Repairs truncated JSON strings by balancing unclosed quotes and containers.
    """
    _raw: str = raw_json
    _out: str = "{}"
    raise NotImplementedError


def is_valid_json(text: str) -> bool:
    """
    COVERED:
    - Checks whether text is well-formed JSON.
    """
    _text: str = text
    _valid: bool = True
    raise NotImplementedError

