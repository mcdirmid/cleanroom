<!-- Dependencies (md files to read alongside this one):
  - file_view.md
  - guide_delivery.md
  - run_control.md
  - sandbox.md
-->

# Implementation LLS: sandbox_impl

## Data Types
```python
from typing import Callable
from sandbox import Sandbox, SandboxConfig
from file_view import FileView, FileViewConfig
from guide_delivery import GuideDelivery, GuideDeliveryConfig
from run_control import RunControl, RunControlConfig, DiffSizeLimit

class SandboxImpl(Sandbox):
    def __init__(self, config: SandboxConfig, make_file_view: Callable[[FileViewConfig], FileView], make_guide_delivery: Callable[[GuideDeliveryConfig], GuideDelivery], make_run_control: Callable[[RunControlConfig, FileView, GuideDelivery], RunControl], diff_size_limit: DiffSizeLimit | None = None): ...
```

Constructed with the `sandbox` interface's aggregate `SandboxConfig`, factories that construct the file machinery, the step-mode delivery, and the verification and termination rules (the concrete implementations are supplied by the assembler), and an optional diff size limit — the maximum characters a verification diff may report (default 1000, see Non-Concerns); it bundles no imported capabilities. Implements the `Sandbox` Protocol, providing all operations: `get_tool_definitions`, `get_session_start_reads`, `read_file`, `edit_file`, `replace_lines`, `search_files`, `advance`, `fail`, `blame`, and `get_write_occurred`.

## Composition

The implementation composes the three components into a single tool surface; the components are supplied by the assembler through the construction factories (the dependency comment lists the interfaces only):

- File machinery (`file_view`): provides the file tools
- Step-mode delivery (`guide_delivery`): provides the step-mode delivery
- Verification and termination (`run_control`): provides the termination tools

**HLS Justification:** The facade composes the three components' operations into a single tool surface.

## Behavioral Description

The implementation:
- Constructs the three components through the supplied factories, deriving each component's config from the aggregate `SandboxConfig`:
  - the file machinery via `make_file_view(FileViewConfig(file_mappings=config.file_mappings, readable_paths=<config.readable_paths with the guide excluded when step mode is enabled>, writable_paths=config.writable_paths, templates=config.templates, search_result_limit=config.search_result_limit, session_start_reads_enabled=config.session_start_reads_enabled))`
  - the step-mode delivery via `make_guide_delivery(GuideDeliveryConfig(guide=<the guide's full path, resolved from the guide's virtual name via the file mappings; None when no guide is declared>, step_sections_enabled=config.step_sections_enabled))`
  - the verification and termination rules via `make_run_control(RunControlConfig(verification_callback=config.verification_callback, feedback_pending=config.feedback_pending, blame_targets=config.blame_targets, diff_size_limit=<diff_size_limit, or 1000 when None>), file_view, guide_delivery)`
- Provides the tool registry: `get_tool_definitions` composes the components' tools — the file tools (from file_view), the advance tool (from guide_delivery, its parameters per the step state), and the termination tools (from run_control: the failure tool always, the blame tool only when blame targets are configured); the composed tools are presented together.
- Dispatches tool calls to the owning component: the file tools to file_view; the advance, failure, and blame tools to run_control; the write-modified query and the session-start read request are delegated to file_view, and the guide's presentation at run start to guide_delivery.
- Sequences each advance: verification via run_control; on a failing verification, guide_delivery restates the guide summary (in step mode); on a passing verification, guide_delivery delivers the next step section while step sections remain, else termination via run_control; the run's diff is produced after verification passes and is reported within the termination machinery; the change-message requirement is evaluated against the changed set when advance would otherwise signal successful termination.
- In step mode, excludes the guide from the file machinery's readable paths: the derived file_view config leaves the guide out, so reads of the guide are rejected and the guide never appears among the session-start reads; the guide's content reaches the agent only through guide_delivery's outputs.
- Holds only per-run state, in the components: the file state (file_view), the step state (guide_delivery), and the verification state (run_control); nothing persists across runs.
- Categorizes errors: policy violations and validation errors signal failure, leaving the filesystem unchanged (per file_view and run_control); filesystem errors and callback errors are unhandled.

**HLS Justification:** Composes the three components: file_view provides the file tools, run_control provides the termination tools, and guide_delivery provides the step-mode delivery; the composed tools form the sandbox's tool registry.

## Invariants

- The tool surface composes the components' operations and the composed tools are presented together
- The blame tool is offered only when blame targets are configured
- In a single advance, verification precedes step delivery and termination
- A failing verification produces feedback and no step delivery, and never terminates the run
- A passing verification with step sections remaining delivers the next step section
- A passing verification with no step sections remaining proceeds to the termination machinery
- The change summary applies only when advance terminates: in step mode, an advance with step sections remaining carries no change summary
- The feedback obligation is not disclosed to the agent before advance is attempted without a change; it surfaces only through advance's rejection
- No state persists across runs

## Non-Concerns

- **Component internals:** how the components implement their contracts is governed by the components' own specs; the facade adds only composition.
- **Composition wiring:** the exact mechanism by which the components are composed is unspecified.
- **Error message wording:** error messages identify the violated policy or the failing operation; their exact wording is unspecified.
