"""Sandbox assembler constructing hermetic sandbox instances."""

from .sandbox_impl import SandboxFactoryImpl
from .file_reader_impl import FileReaderFactoryImpl
from .file_editor_impl import FileEditorFactoryImpl
from .guide_delivery_impl import GuideDeliveryFactoryImpl
from .run_control_impl import RunControlFactoryImpl
from .change_summary_validator_impl import ChangeValidatorImpl


class SandboxAsm(SandboxFactoryImpl):
    def __init__(self) -> None:
        super().__init__(
            file_reader_factory=FileReaderFactoryImpl(),
            file_editor_factory=FileEditorFactoryImpl(),
            run_control_factory=RunControlFactoryImpl(change_validator=ChangeValidatorImpl()),
            guide_delivery_factory=GuideDeliveryFactoryImpl(),
        )

