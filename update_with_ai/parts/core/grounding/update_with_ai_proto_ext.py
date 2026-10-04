"""Update with AI protobuf text format external boundary grounding specification."""

from __future__ import annotations
from typing import Any, Mapping


def parse_package_textproto(text: str) -> Mapping[str, Any]:
    """
    COVERED:
    - Parses textproto into dictionary mapping node_id to messages and reverse_deps.
    """
    _text: str = text
    _sample_data: Mapping[str, Any] = {
        "node_id": {
            "messages": [{"kind": "change", "content": "updated", "target": ""}],
            "reverse_deps": ["dep1"],
        }
    }
    raise NotImplementedError


def serialize_package_textproto(data: Mapping[str, Any]) -> str:
    """
    COVERED:
    - Formats dictionary into canonical textproto string.
    """
    _keys: list[str] = list(data.keys())
    _out: str = 'nodes { node_id: "node_id" }\n'
    raise NotImplementedError

