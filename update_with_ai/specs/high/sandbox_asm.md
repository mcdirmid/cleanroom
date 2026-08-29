# sandbox_asm

fulfills: sandbox
imports: sandbox_impl (sandbox), file_reader_impl (read machinery), file_editor_impl (write machinery), guide_delivery_impl (step-mode delivery), run_control_impl (verification and termination), change_summary_validator_impl (change validation)

## Deltas

- Assembles the concrete tool implementations into the sandbox implementation.
- Supplies the read machinery, write machinery, step-mode delivery, and verification and termination rules through factories to the sandbox.
- [boundary] The concrete tool implementations are selected here.
- [external] The concrete component implementations.

## Non-concerns

- Consumption: how the assembled sandbox is used is unspecified here.
- Selection policy: the concrete implementations wired here are a default assembly; other selections may differ.
- Testability: this assembly is never tested; it performs no functionality beyond configuration and assembly of other modules.
