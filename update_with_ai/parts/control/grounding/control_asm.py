"""Assembly grounding specification for control_asm."""

from __future__ import annotations
from . import (
    control_coordinate_impl,
    control_verification_impl,
    control_work_scheduler_impl,
    control_submit_impl,
    control_attribution_impl,
)

CONSTITUENTS = (
    control_coordinate_impl,
    control_verification_impl,
    control_work_scheduler_impl,
    control_submit_impl,
    control_attribution_impl,
)


def __initialize__() -> None:
    """Initializes the control assembly component.

    CONSTITUENTS:
    - control_coordinate_impl
    - control_verification_impl
    - control_work_scheduler_impl
    - control_submit_impl
    - control_attribution_impl
    """
    pass
