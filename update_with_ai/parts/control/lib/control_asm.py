from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
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
        tier=agent_session.agent_session,
    )
    reg.register_singleton(
        control_verification_impl.VerificationEvaluator,
        keys=[control_verification.VerificationEvaluator, control_verification_impl.VerificationEvaluator],
        tier=agent_session.agent_session,
    )
    reg.register_singleton(
        control_work_scheduler_impl.WorkScheduler,
        keys=[control_work_scheduler.WorkScheduler, control_work_scheduler_impl.WorkScheduler],
        tier=agent_session.agent_session,
    )
    reg.register_singleton(
        control_submit_impl.SubmissionCoordinator,
        keys=[control_submit.SubmissionCoordinator, control_submit_impl.SubmissionCoordinator],
        tier=agent_session.agent_session,
    )
    reg.register_singleton(
        control_attribution_impl.AttributionCoordinator,
        keys=[control_attribution.AttributionCoordinator, control_attribution_impl.AttributionCoordinator],
        tier=agent_session.agent_session,
    )
    reg.register_singleton(
        src_metadata_impl.SourceMetadataCoordinator,
        keys=[src_metadata.SourceMetadataCoordinator, src_metadata_impl.SourceMetadataCoordinator],
        tier=agent_session.agent_session,
    )
    src_storage_impl.__initialize__(reg)

_initialize_ = __initialize__
