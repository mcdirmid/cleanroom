<!-- Dependencies (md files to read alongside this one):
  - sandbox_impl.md
  - file_view_impl.md
  - guide_delivery_impl.md
  - run_control_impl.md
  - sandbox.md
  - run_control.md
-->

# Implementation LLS: sandbox_asm

## Data Types
```python
from typing import Optional
from sandbox_impl import SandboxImpl
from sandbox import SandboxConfig
from run_control import DiffSizeLimit

class SandboxAsm(SandboxImpl):
    def __init__(self, config: SandboxConfig, diff_size_limit: Optional[DiffSizeLimit] = None) -> None: ...
```

Subclasses `SandboxImpl` with pre-wired tool implementations: supplies the file machinery (`FileViewImpl`), step-mode delivery (`GuideDeliveryImpl`), and verification and termination rules (`RunControlImpl`) at construction. Fulfills the `Sandbox` protocol via `SandboxImpl`. This assembly performs configuration and assembly only and is never tested.

## Composition

- SandboxImpl (sandbox)
- FileViewImpl (file machinery)
- GuideDeliveryImpl (step-mode delivery)
- RunControlImpl (verification and termination)

## Behavioral Description

- Assembles the concrete tool implementations at construction: supplies factories wrapping `FileViewImpl` (file machinery), `GuideDeliveryImpl` (step-mode delivery), and `RunControlImpl` (verification and termination) to `super().__init__`.
- Inherits and implements the `Sandbox` protocol through `SandboxImpl`.
- No functionality beyond configuration and assembly is performed; this assembly is never tested.

## Invariants

- The concrete implementations are selected here, at construction; operations never select components.
- No persistent state is held across calls: each instance is a fresh sandbox.

## Non-Concerns

- **Consumption:** how the assembled sandbox is used is unspecified here.
- **Selection policy:** the concrete implementations wired here are a default assembly; other selections may differ.
