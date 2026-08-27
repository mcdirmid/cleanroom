# sandbox

imports: tool_provider (tool definitions, results, signals, stubbing), agent_loop (run), dag_storage (dependency), dag_clean_logic (change message, feedback message)
terms (from tool_provider): tool definition, tool result, supersession flag, stub, termination result, tool failure
terms (from agent_loop): run
terms (from dag_storage): dependency
terms (from dag_clean_logic): change message, feedback message
terms (owned): virtual name, file write, line-numbered view, injected read, session-start read, blame, blame target, soft length bound, hard length bound, template, guide, guide summary, step section, step mode

## Purpose

Provides a controlled environment for agents to read, write, search, and modify files within a virtual workspace: reading, writing, content-based editing, line-range editing, recursive searching, verification, and termination tools. Enforces per-run policies and signals termination when the agent completes its task.

## Terms

- Virtual name: the name the agent uses to refer to a file; it is the file's final path component when no other file in the sandbox shares that component, and otherwise the file's path with just enough leading components removed to be unique among the sandbox's files; the sandbox resolves the virtual name to the file's full filesystem path.
- File write: any successful operation that modifies the filesystem.
- Line-numbered view: a rendering of a file's content with each line prefixed by its 1-indexed line number; the line numbers are metadata, never file content.
- Injected read: the read provided for a file immediately after a successful file write of that file, presenting a read request with line numbers and the read result carrying the file's full current content; the agent did not request it, and to the agent it appears as a numbered read it requested.
- Session-start read: a read of a file the agent can read but not write, provided at the beginning of a run for rendering before the agent's first turn; it renders the file's content plain, never supersedes an earlier result, and is never stubbed.
- Template: a writable file's initial content, configured for the file; when the file does not exist when the sandbox is configured, the file is created with the template's content at run start; a file that exists when the sandbox is configured is never modified by its template.
- Guide: the run's declared guide input — a readable file the node declares separately from its dependencies, at most one per run, in the guide format: its first line is `# Guide: <title>` and its first `##` heading is `## Summary`.
- Guide summary: the guide's first part — the content from the guide's first line through the end of its `## Summary` section.
- Step section: a checklist section of the guide — a part of the guide after the guide summary, delimited by `## <name>` headings, delivered after an advance that passed verification.
- Step mode: a run configuration in which the guide is not readable and its content reaches the agent only through the advance operation: the guide summary at run start, then the step sections one at a time after successful advances.
- Blame: a termination outcome that attributes the task's incompleteness to one or more dependencies and provides feedback on how to correct their outputs; blame is not failure.
- Blame target: an artifact the agent may blame — a dependency's declared source file, addressed by its virtual name.
- Soft length bound: the preferred maximum length of a change summary; a summary exceeding it is rejected with shortening guidance up to a grace count, then accepted when within the hard length bound.
- Hard length bound: the maximum length a change summary may reach; a summary exceeding it is rejected with hard-bound guidance up to a grace count, and a summary still exceeding it after the grace count fails the run (success turns into failure).

## Contract

**Inputs**

- Configured: file mappings (virtual name to full path); readable and writable virtual names; blame targets (a mapping from each blameable artifact's virtual name to the node that owns it; may be empty); the search result limit (the maximum matches a single search may render); whether session-start reads are enabled; the guide (the run's declared guide, at most one, may be absent); whether step mode is enabled; whether the run's pending messages include a feedback message; the templates (a mapping from writable virtual names to their template content; may be empty); an optional verification callback.
- Per call: a tool call (tool name and arguments, per tool_provider).

**Operations**

- Request tool definitions (per tool_provider).
- Execute a tool call.
- Query whether the run has modified the filesystem.
- Request the session-start reads.

**Guarantees**

- Permissions are enforced for all operations.
- Signals whether any file write has occurred during the run.
- The run begins when the sandbox is configured and ends when the agent signals termination.
- A read provides the file's entire content; reads are not paginated and are not bounded by a size limit.
- Search results beyond the search result limit signal a tool failure advising offset/limit pagination; the limit bounds rendered matches only.
- Search results render matches only for files that are not writable; matches in writable files are reported as counts without content.
- An edit's replacement applies atomically (all or nothing).
- Error messages identify the violated policy or the failing operation; errors leave the filesystem unchanged.

**Assumptions**

- The agent loop handles free-text responses, routes termination signals, and stubs the earlier result when a result's flag is set, identifying it by the file's virtual name or the verification command.
- The verification callback, if provided, has no side effects on the sandbox's filesystem; it may only modify the node's lib/test BUILD file (maintained by the build linter), which is not among the sandbox's files.
- A run declares at most one guide.

**File addressing**

- Files are addressed to the agent by their virtual names, never by their paths.
- Files with the same final path component have distinct virtual names: each retains just enough of its path to differ from every other file's virtual name.
- Reads, writes, edits, searches, session-start reads, and error messages name files by their virtual names.
- Blame names the blamed artifact by its virtual name.

**File operations**

- Content-based editing: search-and-replace of short text, bounded in length; longer changes go through line-range editing.
- Line-range editing: replace, delete, insert.
- Recursive searching within a specified path.

**Views**

- Reads of writable files provide line numbers, enabling line-range edits; a plain read of an existing writable file is rejected; reads of non-writable files provide plain content.
- Line-range edits require a numbered read; attempting one without it signals a tool failure.
- Line-range edits accept 1-indexed line numbers within the file's current bounds.

**Stubbing**

- Stubbing replaces superseded tool results with placeholders, keeping the conversation focused on current state.

**Auto re-read**

- After a successful file write, the file's current content appears in the conversation.
- A write that fails does not provide the file's content.

**Session-start reads**

- When session-start reads are enabled, a session-start read is provided for every file that is readable but not writable; when disabled, none are provided.
- Session-start reads are provided in a deterministic order (sorted by virtual name).
- A session-start read renders the file's content plain and never supersedes an earlier result.

**Step mode**

- When step mode is disabled, the guide is provided whole at run start and is re-readable like other readable files.
- When step mode is enabled, the guide is not readable: its content reaches the agent only through the advance operation's outputs.
- In step mode, the guide is not presented among the readable files: file lists shown to the agent do not name the guide.
- In step mode, the guide is revealed incrementally: advance delivers one section at a time.
- The run cannot terminate until all guide sections are delivered and verification passes.
- A failing verification prevents progressing to the next section, requiring correction before continuing.
- A readable file that is not the guide is unaffected by step mode.

**Template initialization**

- Files with templates are initialized from their template content at run start.
- Template initialization is not a run write: it never signals that the run modified the filesystem and is never a changed file.

**Verification**

- Verification runs as part of the advance operation; verification passes when no verification callback is configured, and is delegated to the callback when one is configured.
- When verification fails, the session continues with feedback; advance never terminates on a failing verification.
- Verification may maintain the node's lib/test BUILD file through the configured build linter; the BUILD file is not among the sandbox's files, and such writes are not run writes and are not reported in change summaries.

**Termination**

- Termination tools: advance, failure, and blame. Advance signals successful termination; a valid blame signals successful termination; the failure operation ends the session in failure.
- The change summary applies only when advance terminates: in step mode, an advance with step sections remaining carries no change summary.
- Blame is offered only when blame targets are configured; each (target, feedback) pair is delivered as a feedback message to the blamed artifact's owning node.
- Termination is at the agent's judgment: the agent signals termination when it considers its task complete, or when it cannot be completed.
- Advance signals successful termination when verification passes; when files were modified, it requires a change summary naming what changed in each file, directing the next reader's attention to the changes.
- When the run's pending messages include a feedback message, advance that would otherwise signal successful termination without a change signals a tool failure with a reason directing the agent to change, blame, or fail; the session continues.
- The feedback obligation is not disclosed to the agent before advance is attempted without a change; it surfaces only through advance's rejection.
- When files were modified and the change summary is missing, malformed, or incomplete, advance signals a tool failure.
- Change summaries are bounded; a summary exceeding the bound is rejected with guidance; persistent rejection fails the run.

## Non-concerns

- Error message wording: error messages identify the violated policy or failing operation; their exact wording is unspecified.
- Session-start read size: session-start reads inherit the unbounded-read rule; the read-only files are assumed to be reasonably sized, so no separate size bound is introduced for session-start reads.
- Template size: templates are assumed to be reasonably sized, so no separate size bound is introduced for template content.
- Step section size: step sections are parts of the guide file, which is assumed reasonably sized; no separate size bound is introduced for step sections.
- Guide parsing: the exact rules for splitting the guide into its guide summary and step sections follow the guide format; section content is delivered in order without interpretation.
- Step presentation: the exact wording of the ensure instruction and the formatting of the summary and step sections within an advance output are unspecified; the intent is conveyed by the Step mode rules.
- Advance tool description: the advance tool's description wording is unspecified; the tool's contract is defined by the Verification, Termination, and Step mode rules.
- Virtual-name derivation: the exact procedure that selects the shortest unique suffix is unspecified; the resulting virtual names follow the virtual name definition.
