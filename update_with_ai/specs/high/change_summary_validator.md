# change_summary_validator

imports: file_editor (file write), run_control (soft length bound, hard length bound), tool_provider (tool failure, tool result)
terms (from file_editor): file write
terms (from run_control): soft length bound, hard length bound
terms (from tool_provider): tool failure, tool result
terms (owned): change validation, diff summary, net change

## Purpose

Validates file change claims against actual file modifications, computes diff summaries, detects net-zero file modifications, and enforces soft and hard length bounds on change summaries with a grace count.

## Terms

- Change validation: checking that claimed changed files match actual modified files whose current content differs from their initial run-start content.
- Diff summary: a formatted representation of line-by-line file changes across modified files.
- Net change: an effective modification where a file's current content differs from its initial content at run start; a file written back to its initial content is net-unchanged.

## Contract

**Inputs**

- Configured: diff size limit (maximum characters reported in a diff summary).
- Collaborators: file_editor (providing initial contents, current file contents, and modified file paths).
- Per validation: claimed change list (entries of file paths and short change summaries).

**Operations**

- Compute diff summary.
- Detect net-changed files.
- Validate change summaries.

**Guarantees**

- Validates that claimed change summaries name each net-changed file and no net-unchanged files.
- A write that nets out to no change is detected as net-unchanged and rejected if claimed as a change.
- Enforces the soft length bound and hard length bound with a grace count, providing shortening guidance when exceeded.
- Produces a formatted diff summary truncated at the configured diff size limit.

**Assumptions**

- The file_editor accurately records initial contents and modified file paths.

## Non-concerns

- Advance orchestration: triggering verification or signaling termination is handled by run_control.
- File editing operations: line replacements and content updates are performed by file_editor.
