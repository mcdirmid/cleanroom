"""
lib/sandbox_asm.py

Assembly of the sandbox component.

Performs configuration and assembly only: subclasses SandboxImpl and wires
the concrete tool implementations (FileViewImpl, GuideDeliveryImpl, RunControlImpl)
at construction. Implements no functionality beyond assembly, and is never tested.

Library usage:
    from update_with_ai.lib.sandbox_asm import SandboxAsm
    sandbox = SandboxAsm(config)
"""

from __future__ import annotations

from typing import Optional

from .sandbox import SandboxConfig
from .sandbox_impl import SandboxImpl
from .file_view_impl import FileViewImpl
from .guide_delivery_impl import GuideDeliveryImpl
from .run_control import DiffSizeLimit
from .run_control_impl import RunControlImpl


class SandboxAsm(SandboxImpl):
    """
    Assembles concrete tool implementations into SandboxImpl (configuration
    and assembly only; no other functionality).
    """

    def __init__(
        self,
        config: SandboxConfig,
        diff_size_limit: Optional[DiffSizeLimit] = None,
    ) -> None:
        super().__init__(
            config=config,
            make_file_view=lambda fvc: FileViewImpl(config=fvc),
            make_guide_delivery=lambda gdc: GuideDeliveryImpl(config=gdc),
            make_run_control=lambda rcc, fv, gd: RunControlImpl(
                rcc, file_view=fv, guide_delivery=gd
            ),
            diff_size_limit=diff_size_limit,
        )
