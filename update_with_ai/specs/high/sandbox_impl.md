# sandbox_impl

imports: tool_provider, virtual_file_name, file_reader, file_editor, guide_delivery, run_control, sandbox
types from tool_provider: tool metadata, tool result, tool failure, termination outcome
types from virtual_file_name: virtual file name
types from file_reader: file reader, file reader factory, read-only file, read-write file, session-start read
types from file_editor: file editor, file editor factory, template
types from guide_delivery: guide delivery, guide delivery factory, guide, step section, step delivery
types from run_control: run controller, run control factory, advance tool
types from sandbox: sandbox factory, sandbox, sandbox configuration, startup interaction
implements: sandbox factory

## Behavior

- Creating a *sandbox* through a *sandbox factory* yields a *sandbox* configured from a *sandbox configuration* using a *file reader factory*, a *file editor factory*, a *run control factory*, and an optional *guide delivery factory*.
- A *sandbox* composes all available tools provided by its *file reader*, *file editor*, *run controller*, and *guide delivery*.
- A *sandbox* produces a *startup interaction* combining `read_file` *tool results* from *session-start reads* and an initial `advance` *tool result* from *step delivery*.
- Tool executions in a *sandbox* are dispatched to the corresponding underlying component.
- In step mode, executing the *advance tool* delivers the next *step section* from *guide delivery* upon passing verification before termination.
