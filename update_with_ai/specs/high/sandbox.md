# sandbox

imports: tool_provider (tool definitions, results, signals, stubbing), dag_storage (dependency), dag_clean_logic (change message, feedback message), file_reader (read machinery), file_editor (write machinery), guide_delivery (step mode), run_control (verification and termination)
terms (from tool_provider): tool definition, tool result, tool failure, supersession flag, stub, termination result, signal, tool call
terms (from dag_storage): dependency
terms (from dag_clean_logic): change message, feedback message
terms (from file_reader): virtual name, session-start read
terms (from file_editor): template
terms (from guide_delivery): guide, step mode, step section
terms (from run_control): blame, blame target, soft length bound, hard length bound
terms (owned):

## Purpose

Provides a controlled environment for agents to read, write, search, and modify files within a virtual workspace, composing file machinery, step-mode guide delivery, and verification and termination into a single tool surface. Enforces per-run policies and signals termination when the agent completes its task.

## Contract

**Inputs**

- Configured: the aggregate sandbox configuration — file mappings (each file's virtual name to its full path), the readable and writable virtual names, the templates (a mapping from writable virtual names to their template content; may be empty), the search result limit (the maximum matches a single search may render), whether session-start reads are enabled, the blame targets (a mapping from each blameable artifact's virtual name to the node that owns it; may be empty), the guide (at most one, may be absent), whether step mode is enabled, whether the session's pending messages include a feedback message, and an optional verification callback.
- Per call: a tool call (tool name and arguments, per tool_provider).

**Operations**

- Request tool definitions (per tool_provider).
- Execute a tool call.
- Query whether the session modified the filesystem.
- Request the session-start reads.

**Guarantees**

- The tool surface composes the components' operations: file_view provides the file tools, run_control provides the termination tools, and guide_delivery provides the step-mode delivery; the composed tools are presented together.
- The blame tool is offered only when blame targets are configured and non-empty.
- In a single advance, verification precedes step delivery and termination.
- A failing verification produces feedback and no step delivery, and never terminates the session.
- A passing verification with step sections remaining delivers the next step section.
- A passing verification with no step sections remaining proceeds to the termination machinery.
- The change summary applies only when advance terminates: in step mode, an advance with step sections remaining carries no change summary.
- The feedback obligation is not disclosed to the agent before advance is attempted without a change; it surfaces only through advance's rejection.

**Assumptions**

- The agent loop handles free-text responses, routes termination signals, and stubs the earlier result when a result's flag is set, identifying it by the file's virtual name or the verification command.
- The verification callback, if provided, has no side effects on the sandbox's filesystem; it may only modify the node's lib/test BUILD file (maintained by the build linter), which is not among the sandbox's files.
- A session declares at most one guide.

## Non-concerns

- Component internals: how the components implement their contracts is governed by the components' own specs; the facade adds only composition.
