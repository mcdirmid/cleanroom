# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:03Z
# LAST_CHANGED: 2026-10-06T14:35:00Z
# CHANGE: new file
# CODE_HASH: bd890eb01a7e
# COVERAGE_AUDIT: 2026-10-11T22:09:03Z
# QA_AUDIT: 2026-10-11T22:09:03Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from support.lib.lifecycle import get_default_registry
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, Singleton
from update_with_ai.parts.agent.lib import agent_session
from . import src_metadata

current_utc_timestamp = src_metadata.current_utc_timestamp
_is_html_comment_format = src_metadata._is_html_comment_format
_find_header_insertion_index = src_metadata._find_header_insertion_index
_extract_block_boundaries = src_metadata._extract_block_boundaries
parse_metadata_content = src_metadata.parse_metadata_content
format_metadata_block = src_metadata.format_metadata_block


class SourceMetadataCoordinator(
    src_metadata._DefaultSourceMetadataCoordinator, Singleton
):
    """Realizes source metadata parsing, hashing, and in-place header rewriting."""

    tier = agent_session.agent_session


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        SourceMetadataCoordinator,
        keys=[src_metadata.SourceMetadataCoordinator, SourceMetadataCoordinator, src_metadata._DefaultSourceMetadataCoordinator],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
