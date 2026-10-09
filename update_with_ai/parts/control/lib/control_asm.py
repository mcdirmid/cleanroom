# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T21:19:01Z
# CHANGE: new file
# CODE_HASH: ba9842ac9b23
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from . import (
    control_attribution,
    control_attribution_impl,
    control_coordinate,
    control_coordinate_impl,
    control_submit,
    control_submit_impl,
    control_verification,
    control_verification_impl,
    control_work_scheduler,
    control_work_scheduler_impl,
    src_metadata,
    src_metadata_impl,
    src_storage_impl,
)

CONSTITUENTS = (
    control_attribution_impl,
    control_coordinate_impl,
    control_submit_impl,
    control_verification_impl,
    control_work_scheduler_impl,
    src_metadata_impl,
    src_storage_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the control assembly component and registers its singletons."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        control_coordinate_impl.SessionCoordinator,
        keys=[control_coordinate.SessionCoordinator, control_coordinate_impl.SessionCoordinator],
    )
    reg.register_singleton(
        control_verification_impl.VerificationEvaluator,
        keys=[control_verification.VerificationEvaluator, control_verification_impl.VerificationEvaluator],
    )
    reg.register_singleton(
        control_work_scheduler_impl.WorkScheduler,
        keys=[control_work_scheduler.WorkScheduler, control_work_scheduler_impl.WorkScheduler],
    )
    reg.register_singleton(
        control_submit_impl.SubmissionCoordinator,
        keys=[control_submit.SubmissionCoordinator, control_submit_impl.SubmissionCoordinator],
    )
    reg.register_singleton(
        control_attribution_impl.AttributionCoordinator,
        keys=[control_attribution.AttributionCoordinator, control_attribution_impl.AttributionCoordinator],
    )
    reg.register_singleton(
        src_metadata_impl.SourceMetadataCoordinator,
        keys=[src_metadata.SourceMetadataCoordinator, src_metadata_impl.SourceMetadataCoordinator],
    )
    src_storage_impl.__initialize__(reg)

_initialize_ = __initialize__
