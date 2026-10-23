# Concrete scenarios for `loop_guard_impl` (implementation)

Scenarios 1 through 5 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 6
through 10 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — New work produces no reminder

Given: the loop guard has no repetition tracking for the agent session, and the agent session is
editing the unit widget's contract at `/ws/alpha_scope_a/widget.md`.

1. The tool manager returns the `read_file` response for `/ws/alpha_scope_a/widget.md`.
   Observed: the guard reports that no warning threshold has been reached, produces no loop
   reminder, and does not report a loop failure.
   Realized by: the component's own repetition counters, which only a tool execution that the
   component judges a repetition advances, so a run of zero repetitions leaves every threshold
   comparison reporting that no threshold has been reached.

2. The tool manager returns the `edit_file` response for `/ws/alpha_scope_a/widget.md` at lines 4
   through 9, and then the `edit_file` response for `/ws/alpha_scope_a/gadget.md` at lines 4
   through 9.
   Observed: neither execution produces a loop reminder, and no loop failure is reported.
   Realized by: the component's own coordinate-span recording, which distinguishes the two edits by
   their file path, so neither execution continues the other's repetition run.

### Scenario 2 — Identical tool executions reaching the warning threshold

Given: the loop guard's warning threshold for an agent session is 2 consecutive repetitions, and
the tool manager has returned the `read_file` response for `/ws/alpha_scope_a/widget.md` exactly
once, producing no reminder because one execution is not a repetition.

1. The tool manager returns the `read_file` response for `/ws/alpha_scope_a/widget.md` again.
   Observed: the guard produces one loop reminder, and no loop failure is reported.
   Realized by: the component's own warning threshold of 2 repetitions over its consecutive
   identical-execution counter, the invocation signature it derives from the tool name and the
   serialized arguments of the `read_file` response through `tool_provider`, and the component's own
   reminder construction, whose advisory text directs the agent to modify files using the session's
   editing tool through `file_editor` or conclude the round with blame or fail, states that repeated
   tool execution will reveal no new information until session read-write files are updated, and
   warns that repeating the call without modifying files will trigger fatal loop termination.

### Scenario 3 — Identical tool executions reaching the fatal threshold

Given: the loop guard's warning threshold is 2 consecutive repetitions and its fatal threshold for
an agent session is 4 consecutive repetitions, and the tool manager has returned the `read_file`
response for `/ws/alpha_scope_a/widget.md` twice, having produced one loop reminder.

1. The tool manager returns the `read_file` response for `/ws/alpha_scope_a/widget.md` a third
   time.
   Observed: the guard produces a second loop reminder.
   Realized by: the component's own warning threshold comparison over the same consecutive
   identical-execution counter, and the component's own reminder construction.

2. The tool manager returns the `read_file` response for `/ws/alpha_scope_a/widget.md` a fourth
   time.
   Observed: the guard produces a loop failure whose explanation communicates that the agent
   session has terminated, and no further loop reminder is produced for that execution.
   Realized by: the component's own fatal threshold comparison over the same consecutive
   identical-execution counter, and the component's own loop failure construction through
   `loop_guard`, which carries the explanation naming the repeated `read_file` invocation.

### Scenario 4 — Edits to the same file and line range

Given: the loop guard's warning threshold is 2 consecutive repetitions and its fatal threshold is
4 consecutive repetitions, and the agent session is editing the unit widget's contract with the
`edit_file` tool.

1. The tool manager returns the `edit_file` response for `/ws/alpha_scope_a/widget.md` at lines 12
   through 18.
   Observed: the guard produces no loop reminder and reports no loop failure.
   Realized by: the component's own coordinate-span counter, which begins a new run of one
   repetition for the file-and-line-range span recorded from the response's tool call arguments
   through `tool_provider` and identified using the session's editing tool through `file_editor`.

2. The tool manager returns the `edit_file` response for the same file at the same line range 12
   through 18.
   Observed: the guard produces one loop reminder.
   Realized by: the component's own warning threshold comparison over that coordinate-span counter,
   and the component's own reminder construction.

3. The tool manager returns the `edit_file` response for the same file at the same line range 12
   through 18 a third time.
   Observed: the guard produces a second loop reminder.
   Realized by: the component's own warning threshold comparison over that coordinate-span counter,
   and the component's own reminder construction.

4. The tool manager returns the `edit_file` response for the same file at the same line range 12
   through 18 a fourth time.
   Observed: the guard produces a loop failure whose explanation communicates that the agent
   session has terminated.
   Realized by: the component's own fatal threshold comparison over the coordinate-span counter, and
   the component's own loop failure construction through `loop_guard`.

### Scenario 5 — Forward progress clears the repetition tracking

Given: the loop guard's warning threshold is 2 consecutive repetitions and its fatal threshold is
4 consecutive repetitions, and the tool manager has returned the `read_file` response for
`/ws/alpha_scope_a/widget.md` twice, having produced one loop reminder.

1. The tool manager returns the `read_file` response for `/ws/alpha_scope_a/gadget.md`, which
   demonstrates forward progress.
   Observed: the repetition tracking for consecutive executions of `read_file` is cleared, the
   execution produces no loop reminder, and no loop failure is reported.
   Realized by: the component's own forward-progress test over the tool name and serialized
   arguments of the `gadget.md` response through `tool_provider`, and the component's own reset of
   both repetition counters, which is the write that the later threshold comparisons read.

2. The tool manager returns the `read_file` response for `/ws/alpha_scope_a/widget.md` once more.
   Observed: no warning threshold has been reached, so the guard produces no loop reminder and no
   loop failure.
   Realized by: the component's own counters, now holding a run of one repetition because the reset
   cleared the earlier run.

## Implementation-only

### Scenario 6 — Forward progress that continues a repetition run

Given: the loop guard's counters hold two consecutive executions of `read_file` for
`/ws/alpha_scope_a/widget.md`, and the tool manager returns a third `read_file` response for
`/ws/alpha_scope_a/widget.md` whose output is "42 lines".

1. The guard evaluates that third response.
   Observed: the counters hold three consecutive executions of the same invocation, and the guard
   does not treat the execution as forward progress.
   Realized by: the component's own invocation-signature comparison, which treats two executions as
   identical when their tool names and serialized arguments match and therefore leaves the counters
   advanced rather than reset.

2. The tool manager returns a `read_file` response for `/ws/alpha_scope_a/gadget.md` with output
   "7 lines", and the guard evaluates it.
   Observed: the counters hold one repetition of the `gadget.md` invocation, and the execution is
   treated as forward progress.
   Realized by: the component's own invocation-signature comparison, which finds a different path
   argument and therefore resets both counters.

### Scenario 7 — The two repetition kinds do not share a counter

Given: the loop guard's warning threshold is 2 consecutive repetitions, and the agent session
alternates between executing `read_file` for `/ws/alpha_scope_a/widget.md` and editing
`/ws/alpha_scope_a/widget.md` at lines 4 through 9.

1. The tool manager returns the `read_file` response, then the `edit_file` response at lines 4
   through 9, then the `read_file` response again.
   Observed: the guard produces no loop reminder, because neither the identical-execution counter
   nor the coordinate-span counter has reached two.
   Realized by: the component's own separate counters for identical executions and for coordinate
   spans, where an execution of one kind leaves the other kind's counter at one.

2. The tool manager returns the `edit_file` response at lines 4 through 9 once more.
   Observed: the guard produces one loop reminder for the repeated coordinate span alone.
   Realized by: the component's own coordinate-span counter, now reaching the warning threshold of
   2 repetitions, and the component's own reminder construction.

### Scenario 8 — Edits to the same file at different line ranges

Given: the loop guard's warning threshold is 2 consecutive repetitions, and the agent session
edits the unit widget's contract with `edit_file` at lines 4 through 9 and then at lines 30
through 36.

1. The guard evaluates the second edit.
   Observed: the coordinate-span counter holds one repetition for lines 30 through 36, and no loop
   reminder is produced.
   Realized by: the component's own coordinate-span recording, which compares the file together
   with the line range and therefore does not continue the run of the earlier span.

2. The tool manager returns a third `edit_file` response for the same file at lines 4 through 9.
   Observed: the guard produces no loop reminder.
   Realized by: the same coordinate-span recording, which now holds one repetition for the lines 4
   through 9 span.

### Scenario 9 — Whether the reminder's advisory text is repeated

Given: the loop guard's warning threshold is 2 consecutive repetitions and its fatal threshold is
4 consecutive repetitions, and the counters hold two consecutive executions of `read_file` for
`/ws/alpha_scope_a/widget.md`, for which the guard has already produced one loop reminder.

1. The tool manager returns the same `read_file` response twice more.
   Observed: the guard produces a second loop reminder when the third execution reaches the warning
   threshold again, and then produces the loop failure on the fourth execution, with the advisory
   text attached to the reminders and the explanation attached to the failure.
   Realized by: the component's own warning and fatal threshold comparisons over the single
   consecutive-execution counter, plus the component's own reminder construction and loop failure
   construction through `loop_guard`.

### Scenario 10 — Two sessions tracked at once

Given: the loop guard holds repetition tracking for the agent session alpha and for the agent
session beta, and the session alpha counters hold two consecutive executions of `read_file` for
`/ws/alpha_scope_a/widget.md` while the session beta counters are empty.

1. The guard evaluates a `read_file` response for `/ws/alpha_scope_a/widget.md` belonging to
   session beta.
   Observed: the session beta counters hold one repetition, the session alpha counters are
   unchanged at two consecutive executions, and the guard produces no loop reminder for either
   session.
   Realized by: the component's own per-session repeated-execution state, addressed by the agent
   session tier that bounds the execution, conversation, and ephemeral state of an agent.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-21T20:00:00Z
LAST_CHANGED: 2026-10-21T20:00:00Z
CHANGE: Reflect directive to modify files or conclude round in reminder realization
-->
