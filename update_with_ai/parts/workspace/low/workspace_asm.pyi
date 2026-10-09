# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: core constituents
# CODE_HASH: 72d29f461e79
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Assembly specification for workspace_asm."""


def __initialize__() -> None:
    """Initializes the workspace assembly component.

    CONSTITUENTS:
    - workspace_registry_impl
    - workspace_provision_impl
    - workspace_sync_impl
    - workspace_work_impl
    """
    ...
