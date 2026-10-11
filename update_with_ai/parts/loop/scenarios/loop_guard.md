<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:09:20Z
CHANGE: Author loop-phase loop_guard concrete scenarios
CODE_HASH: 92dc54ae9d9c
-->

# Concrete scenarios for `loop_guard` (interface)

## Scenario 1 — New work produces no reminder

Given: the loop guard has no repetition tracking for the agent session, and the agent session is
editing the unit widget's contract at `/ws/alpha_scope_a/widget.md`.

1. The tool manager returns the `read_file` response for `/ws/alpha_scope_a/widget.md`.
   Observed: the guard reports that no warning threshold has been reached, produces no loop
   reminder, and does not report a loop failure.

2. The tool manager returns the `edit_file` response for `/ws/alpha_scope_a/widget.md` at lines 4
   through 9, and then the `edit_file` response for `/ws/alpha_scope_a/gadget.md` at lines 4
   through 9.
   Observed: neither execution produces a loop reminder, and no loop failure is reported.

## Scenario 2 — Identical tool executions reaching the warning threshold

Given: the loop guard's warning threshold for an agent session is 2 consecutive repetitions, and
the tool manager has returned the `read_file` response for `/ws/alpha_scope_a/widget.md` exactly
once, producing no reminder because one execution is not a repetition.

1. The tool manager returns the `read_file` response for `/ws/alpha_scope_a/widget.md` again.
   Observed: the guard produces one loop reminder, and no loop failure is reported.

## Scenario 3 — Identical tool executions reaching the fatal threshold

Given: the loop guard's warning threshold is 2 consecutive repetitions and its fatal threshold for
an agent session is 3 consecutive repetitions, and the tool manager has returned the `read_file`
response for `/ws/alpha_scope_a/widget.md` twice, having produced one loop reminder.

1. The tool manager returns the `read_file` response for `/ws/alpha_scope_a/widget.md` a third
   time.
   Observed: the guard produces a loop failure whose explanation communicates that the agent
   session has terminated, and no further loop reminder is produced for that execution.

## Scenario 4 — Edits to the same file and line range

Given: the loop guard's warning threshold is 2 consecutive repetitions and its fatal threshold is
3 consecutive repetitions, and the agent session is editing the unit widget's contract with the
`edit_file` tool.

1. The tool manager returns the `edit_file` response for `/ws/alpha_scope_a/widget.md` at lines 12
   through 18.
   Observed: the guard produces no loop reminder and reports no loop failure.

2. The tool manager returns the `edit_file` response for the same file at the same line range 12
   through 18.
   Observed: the guard produces one loop reminder.

3. The tool manager returns the `edit_file` response for the same file at the same line range 12
   through 18 a third time.
   Observed: the guard produces a loop failure whose explanation communicates that the agent
   session has terminated.

## Scenario 5 — Forward progress clears the repetition tracking

Given: the loop guard's warning threshold is 2 consecutive repetitions and its fatal threshold is
3 consecutive repetitions, and the tool manager has returned the `read_file` response for
`/ws/alpha_scope_a/widget.md` twice, having produced one loop reminder.

1. The tool manager returns the `read_file` response for `/ws/alpha_scope_a/gadget.md`, which
   demonstrates forward progress.
   Observed: the repetition tracking for consecutive executions of `read_file` is cleared, the
   execution produces no loop reminder, and no loop failure is reported.

2. The tool manager returns the `read_file` response for `/ws/alpha_scope_a/widget.md` once more.
   Observed: no warning threshold has been reached, so the guard produces no loop reminder and no
   loop failure.
