# sandbox_impl

fulfills: sandbox
imports: file_reader (read machinery), file_editor (write machinery), guide_delivery (step mode), run_control (verification and termination)
terms (from file_reader): virtual name, line-numbered view, session-start read
terms (from file_editor): file write, injected read, template
terms (from guide_delivery): guide, guide summary, step section, step mode
terms (from run_control): blame, blame target, soft length bound, hard length bound

## Deltas

- Composes the components: file_reader and file_editor provide the file tools, run_control provides the termination tools, and guide_delivery provides the step-mode delivery; the composed tools form the sandbox's tool registry.
- Provides the tool registry: the file tools, the advance tool, the failure tool, and the blame tool, each as a fixed function; the blame tool is included only when blame targets are configured and non-empty; the advance tool is always included.
- The write-modified query is delegated to file_editor; the session-start read request is delegated to file_reader.
- [ordering] Tool calls are dispatched to the owning component: read and search tools to file_reader; edit tools to file_editor; the advance, failure, and blame tools to run_control.
- [ordering] Each advance is sequenced: a failing verification produces feedback and no step delivery; a passing verification with step sections remaining produces the next step section; a passing verification with no step sections remaining produces the termination machinery.
- [ordering] In step mode, the step-section pointer gates advance's outputs between the next step section, the restated guide summary, and the termination machinery.
- [ordering] The diff is produced after verification passes and is reported within the termination machinery.
- [ordering] The change-description requirement is evaluated against the changed set when advance would otherwise signal successful termination: when files were modified, a description of the change is required; when no files were modified, none is required.
- [state] Only per-run state is held — the file reader and editor state (file_reader, file_editor), the step state (guide_delivery), and the verification state (run_control) — and nothing persists across runs.
- [external] The composed components' externals: the filesystem (file_reader, file_editor), and the injected verification callback and the diff size limit (run_control).
- [failure] Errors are categorized as policy violations, validation errors, filesystem errors, or callback errors.
- [failure] Policy violations and validation errors signal failure, leaving the filesystem unchanged; filesystem and callback errors are unhandled.

## Non-concerns

- Composition wiring: the exact mechanism by which the components are composed is unspecified.
