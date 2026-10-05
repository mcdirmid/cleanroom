# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: b71c4640b6e9
# GROUNDING_QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

"""Bazel subsystem assembly grounding specification module."""

from __future__ import annotations
from parts.core.grounding import file_paths_impl
from parts.bazel.grounding import bazel_manifest_loader_impl
from parts.bazel.grounding import bazel_node_config_impl
from parts.bazel.grounding import bazel_storage_impl
from parts.bazel.grounding import bazel_target_impl

CONSTITUENTS = (
    bazel_manifest_loader_impl,
    bazel_node_config_impl,
    bazel_storage_impl,
    bazel_target_impl,
    file_paths_impl,
)


def __initialize__() -> None:
    """Aggregates workspace manifest loading, dependency graph storage, message persistence, target resolution, file paths resolution, and node configuration implementations into a unified Bazel workspace subsystem assembly.

    CONSTITUENTS:
    - bazel_manifest_loader_impl
    - bazel_node_config_impl
    - bazel_storage_impl
    - bazel_target_impl
    - file_paths_impl
    """
    bazel_manifest_loader_impl.__initialize__()
    bazel_node_config_impl.__initialize__()
    bazel_storage_impl.__initialize__()
    bazel_target_impl.__initialize__()
    file_paths_impl.__initialize__()
