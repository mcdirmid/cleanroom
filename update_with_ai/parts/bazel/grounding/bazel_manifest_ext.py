# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-05T04:26:30Z
# CHANGE: new file
# CODE_HASH: 1cc70cb0e5e6
# --- END CLEANROOM METADATA ---

"""Bazel manifest external boundary grounding specification."""

from __future__ import annotations
from typing import Any, Mapping


def load_unit_manifest(content: str) -> Mapping[str, Any]:
    """
    COVERED:
    - Deserializes unit manifest JSON text into a typed mapping.
    """
    _content: str = content
    sample: Mapping[str, Any] = {
        "label": "//pkg:sample",
        "name": "sample",
        "unit_name": "sample",
        "dir": "pkg",
        "unit_dir": "pkg",
        "unit_deps": ["//pkg:dep"],
        "deps": ["//pkg:dep"],
        "component_type": "implementation",
    }
    raise NotImplementedError


def load_role_manifest(content: str) -> Mapping[str, Any]:
    """
    COVERED:
    - Deserializes role manifest JSON text into a typed mapping.
    """
    _content: str = content
    sample: Mapping[str, Any] = {
        "label": "//update_python_with_ai:lib",
        "name": "lib",
        "role_name": "lib",
        "src_pattern": "update_with_ai/parts/{unit_dir}/lib/{unit_name}.py",
        "template": None,
        "prompt_template": "Implement {unit_name}",
        "guide": None,
        "allows_step_mode": False,
        "node_deps": [],
        "role_deps": [],
        "silent_role_deps": [],
        "stub_role_deps": [],
        "star_role_deps": [],
        "silent_cross_role_deps": [],
        "feedback_role_deps": [],
        "active_component_types": [
            "implementation",
            "assembly",
            "interface",
            "external",
        ],
        "verify_template": "",
        "verification_success_message": None,
        "silent_srcs": [],
    }
    raise NotImplementedError


def load_target_manifest(content: str) -> Mapping[str, Any]:
    """
    COVERED:
    - Deserializes monolithic target manifest JSON text into a typed mapping.
    """
    _content: str = content
    sample: Mapping[str, Any] = {
        "label": "//pkg:target",
        "name": "target",
        "prompt": "clean node",
        "task_prompt": "clean node",
        "tools": [],
        "deps": [],
        "silent_deps": [],
        "feedback_deps": [],
        "star_deps": [],
        "src": "sample.py",
        "template": None,
        "template_parameters": {},
        "guide": None,
        "verify": None,
        "verification_check": None,
        "silent_srcs": [],
    }
    raise NotImplementedError
