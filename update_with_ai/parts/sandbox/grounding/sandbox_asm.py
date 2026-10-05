# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 2bab84e2d0a9
# GROUNDING_QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

"""Sandbox subsystem assembly grounding specification module."""

from __future__ import annotations

from parts.sandbox.grounding import (
    sandbox_file_editor_impl,
    sandbox_file_reader_impl,
    sandbox_guide_delivery_impl,
    sandbox_impl,
    sandbox_run_control_impl,
    template_format_impl,
    tool_provider_impl,
)

CONSTITUENTS = (
    sandbox_file_editor_impl,
    sandbox_file_reader_impl,
    sandbox_guide_delivery_impl,
    sandbox_impl,
    sandbox_run_control_impl,
    template_format_impl,
    tool_provider_impl,
)


def __initialize__() -> None:
    """Aggregates file inspection, guarded editing, execution control, guide delivery, and tool dispatch services into the sandbox subsystem assembly.

    CONSTITUENTS:
    - sandbox_file_editor_impl.
    - sandbox_file_reader_impl.
    - sandbox_guide_delivery_impl.
    - sandbox_impl.
    - sandbox_run_control_impl.
    - template_format_impl.
    - tool_provider_impl.
    """
    sandbox_file_editor_impl.__initialize__()
    sandbox_file_reader_impl.__initialize__()
    sandbox_guide_delivery_impl.__initialize__()
    sandbox_impl.__initialize__()
    sandbox_run_control_impl.__initialize__()
    template_format_impl.__initialize__()
    tool_provider_impl.__initialize__()
