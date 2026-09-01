# sandbox

imports: tool_provider, virtual_file_name, file_reader, file_editor, guide_delivery, run_control
types from tool_provider: tool, tool provider, tool result, tool failure, termination outcome
types from virtual_file_name: virtual file name
types from file_reader: file reader, file reader factory, read-only file, read-write file, session-start read
types from file_editor: file editor, file editor factory, template
types from guide_delivery: guide delivery, guide delivery factory, guide, step section, step delivery
types from run_control: run controller, run control factory, advance tool

## Purpose

Provides a hermetic virtual workspace that isolates agents from host paths while coordinating progressive execution.

Direct filesystem access leaks host paths and invites out-of-scope edits, so the sandbox confines agents to virtual workspace files. Startup preparation populates missing files from templates and injects read-only context, while runtime coordination intercepts the advance tool to deliver guide steps before allowing final termination.

## Types

- A *sandbox* is a *tool provider* composing tools from a *file reader*, a *file editor*, a *run controller*, and an optional *guide delivery*
- A *sandbox configuration* is a set of parameters configuring file mappings, permissions, templates, search bounds, *guides*, verification checks, and blame targets for a *sandbox*
- A *sandbox factory* is a provider that constructs *sandboxes* configured from *sandbox configurations*
- A *startup interaction* is a collection of initial *tool results* (carrying *session-start reads* and an optional initial *step delivery*) provided at session start

## Behavior

- A *sandbox configuration* defines mappings from *virtual file names* to host paths, file permissions, optional search limits, optional *guides*, verification checks, and blame targets.
- Creating a *sandbox* through a *sandbox factory* yields a *sandbox* configured from a *sandbox configuration*.
- A *sandbox* provides tools composed from its *file reader*, *file editor*, *run controller*, and optional *guide delivery*.
- A *sandbox* produces a *startup interaction* carrying *session-start reads* for all declared *read-only files*, along with an initial *step delivery* when progressive guide delivery is configured.
- A *sandbox* materializes *templates* for missing *read-write files* at startup without overwriting existing files.
- Executing an *advance tool* within a *sandbox* with progressive guide delivery delivers the next *step section* via *step delivery* upon passing verification while sections remain.
- Executing an *advance tool* within a *sandbox* with no *step sections* remaining concludes with a *termination outcome* upon passing verification and change summary checks.
- A *sandbox* allows querying whether any workspace file modifications occurred during the run.
