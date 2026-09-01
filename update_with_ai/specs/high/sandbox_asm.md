# sandbox_asm

imports: sandbox, file_reader, file_editor, guide_delivery, run_control, change_summary_validator
types from sandbox: sandbox factory, sandbox, sandbox configuration
types from file_reader: file reader factory
types from file_editor: file editor factory
types from guide_delivery: guide delivery factory
types from run_control: run control factory
types from change_summary_validator: change validator
implements: sandbox factory

## Behavior

- A *sandbox factory* is assembled from concrete implementations of *file reader factory*, *file editor factory*, *run control factory*, *change validator*, and optional *guide delivery factory*.
- The assembled *run control factory* is wired with the *change validator* to validate change summaries.
