<!-- Dependencies (md files to read alongside this one):
  - file_editor_impl.md
  - file_reader_impl.md
  - guide_delivery_impl.md
  - run_control_impl.md
  - change_summary_validator_impl.md
  - sandbox.md
  - sandbox_impl.md
-->

# Implementation LLS: sandbox_asm

## Data Types
```python
from sandbox_impl import SandboxFactoryImpl
from file_reader_impl import FileReaderFactoryImpl
from file_editor_impl import FileEditorFactoryImpl
from run_control_impl import RunControlFactoryImpl
from change_summary_validator_impl import ChangeValidatorImpl
from guide_delivery_impl import GuideDeliveryFactoryImpl

class SandboxAsm(SandboxFactoryImpl):
    def __init__(self) -> None: ...
```

## Composition

- FileReaderFactoryImpl
- FileEditorFactoryImpl
- RunControlFactoryImpl
- ChangeValidatorImpl
- GuideDeliveryFactoryImpl
- SandboxFactoryImpl

## Behavioral Description

- `SandboxAsm` constructs and wires `FileReaderFactoryImpl`, `FileEditorFactoryImpl`, `RunControlFactoryImpl` (configured with `ChangeValidatorImpl`), and `GuideDeliveryFactoryImpl` directly within `__init__` before delegating to `super().__init__()`.

## Invariants

- Sub-components are pre-wired hermetically per session.
