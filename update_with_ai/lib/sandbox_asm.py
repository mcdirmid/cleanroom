# lib/sandbox_asm.py
"""
Assembly of the sandbox component.
"""

from __future__ import annotations

from typing import Optional

from .sandbox import SandboxConfig
from .sandbox_impl import SandboxImpl
from .file_reader_impl import FileReaderImpl
from .file_editor_impl import FileEditorImpl
from .guide_delivery_impl import GuideDeliveryImpl
from .change_summary_validator_impl import ChangeSummaryValidatorImpl
from .run_control import DiffSizeLimit
from .run_control_impl import RunControlImpl


class SandboxAsm(SandboxImpl):
    def __init__(
        self,
        config: SandboxConfig,
        diff_size_limit: Optional[DiffSizeLimit] = None,
    ) -> None:
        super().__init__(
            config=config,
            make_file_reader=lambda frc: FileReaderImpl(config=frc),
            make_file_editor=lambda fec, fr: FileEditorImpl(config=fec, file_reader=fr),
            make_guide_delivery=lambda gdc: GuideDeliveryImpl(config=gdc),
            make_run_control=lambda rcc, fr, fe, gd: RunControlImpl(
                rcc,
                file_reader=fr,
                file_editor=fe,
                guide_delivery=gd,
                validator=ChangeSummaryValidatorImpl(
                    file_editor=fe,
                    diff_size_limit=rcc.diff_size_limit,
                ),
            ),
            diff_size_limit=diff_size_limit,
        )
