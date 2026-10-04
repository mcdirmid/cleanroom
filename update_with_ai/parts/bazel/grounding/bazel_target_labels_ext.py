"""Bazel target labels external boundary grounding specification module."""

from __future__ import annotations
from typing import Tuple


def parse_and_normalize_label(raw_label: str) -> Tuple[str, str]:
    """
    COVERED:
    - Parses a raw Bazel label into canonical package and target components.
    """
    _raw: str = raw_label
    _result: Tuple[str, str] = ("//pkg", "target")
    raise NotImplementedError


def package_dir_from_label(raw_label: str) -> str:
    """
    COVERED:
    - Extracts package directory path relative to workspace root.
    """
    _raw: str = raw_label
    _dir: str = "pkg"
    raise NotImplementedError
