# change_summary_validator_impl

fulfills: change_summary_validator
imports: file_editor (file write), change_summary_validator (change validation, diff summary, net change), run_control (soft length bound, hard length bound), tool_provider (tool failure, tool result)
terms (from file_editor): file write
terms (from change_summary_validator): change validation, diff summary, net change
terms (from run_control): soft length bound, hard length bound
terms (from tool_provider): tool failure, tool result

## Deltas

- Implements change_summary_validator over a collaborator file_editor and configured diff size limit.
- Checks that claimed change summaries name each net-changed file and no net-unchanged files.
- Rejects missing, malformed, or fabricated change summaries with tool failures.
- Maintains a grace counter per session for change summaries exceeding the soft length bound or hard length bound.
- Formats diff summaries with line-by-line differences up to the configured diff size limit.

## Non-concerns

- Verification callback execution: handled by run_control.
- Tool delivery: handled by tool_provider.
