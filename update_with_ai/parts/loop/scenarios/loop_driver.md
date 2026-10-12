<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T03:09:19Z
CHANGE: Author loop-phase loop_driver concrete scenarios
CODE_HASH: dadb52c87ed3
-->

# Concrete scenarios for `loop_driver` (interface)

## Scenario 1 — A response with no tool execution does not stop the run

Given: the conversation for the agent session holds one user message, "Clean the unit widget in
scope_a.", the loop driver has not yet run, and the conversation holds no loop reminder.

1. The agent runs the loop driver.
   Observed: one model request is sent for the agent session, and the model answers with an
   assistant message whose content is "Here is what I would do next." and no tool execution.

2. The model request for the next turn is sent.
   Observed: the conversation now holds a tool reminder stating that session progress and
   conclusion require executing tools, the reminder is appended after that assistant message, and
   the run has not concluded.

## Scenario 2 — One tool execution carrying a successful termination outcome

Given: the conversation holds one user message, "Clean the unit widget in scope_a.", the tool
manager has installed `read_file`, and the next model answer carries the tool call identifier
`call_11` for `read_file` with the serialized arguments
`{"path": "/ws/alpha_scope_a/widget.md"}`.

1. The agent runs the loop driver.
   Observed: the assistant message is appended to the conversation carrying `call_11`; the tool
   manager is asked to execute `read_file` with `{"path": "/ws/alpha_scope_a/widget.md"}` converted
   into actual values; and the response is appended to the conversation with the tool call
   identifier `call_11` and the tool name `read_file`.

2. The response for `call_11` reports the output "42 lines" and a termination outcome that
   succeeds.
   Observed: the run concludes atomically once, the loop outcome carries a termination outcome that
   succeeds, and the final conversation in that outcome is the conversation above, with the user
   message, the assistant message, and the response in that order.

## Scenario 3 — Several tool executions dispatched in one turn

Given: the next model answer carries the tool call identifiers `call_12` for `read_file` with
arguments `{"path": "/ws/alpha_scope_a/widget.md"}`, `call_13` for `read_file` with arguments
`{"path": "/ws/alpha_scope_a/gadget.md"}`, and `call_14` for `edit_file` with arguments
`{"path": "/ws/alpha_scope_a/widget.md", "old": "a", "new": "b"}`.

1. The agent runs the loop driver.
   Observed: the tool manager executes all three calls and three responses are appended to the
   conversation, correlated to `call_12`, `call_13`, and `call_14` respectively, each carrying the
   tool name it was executed for.

2. The response for `call_13` reports that execution failed with the diagnostic feedback
   "no such file" and does not terminate the conversation.
   Observed: the failure does not conclude the run, the response for `call_13` is visible in the
   conversation with that diagnostic feedback, and the next model request holds the assistant
   message, all three responses, and a tool reminder.

## Scenario 4 — A tool response that names the next tool to call

Given: the response for `call_11` designates a follow-up tool call of `edit_file` with the wired
parameter bindings `{"path": "/ws/alpha_scope_a/widget.md", "old": "42 lines", "new": "38 lines"}`
and the reasoning text "the contract still reports the stale line count".

1. The agent runs the loop driver.
   Observed: the model is not asked for a new answer before the follow-up call is executed, and the
   tool manager executes `edit_file` with those wired parameter bindings converted into actual
   values.

2. The follow-up execution returns its response.
   Observed: the response is appended to the conversation correlated with the follow-up tool call,
   the conversation records the reasoning text "the contract still reports the stale line count",
   and the turn loop continues.

## Scenario 5 — Runaway repetition and the conversation limit

Given: the model request for the sixth turn carries `read_file` with the arguments
`{"path": "/ws/alpha_scope_a/widget.md"}` for the fourth consecutive time, the loop guard for the
session has already produced the loop reminder for `read_file` twice, the loop guard's fatal
threshold for the session is 4 consecutive executions, the conversation limit is 8 turns, and no
tool execution has terminated the conversation.

1. The agent runs the loop driver.
   Observed: the run halts with an unexpected failure whose message reports the repetition of
   `read_file`, and no loop outcome is produced for the agent session.

2. The agent starts a second run whose conversation reaches the eighth turn without any tool
   execution producing a termination outcome.
   Observed: the second run halts with an unexpected failure naming the conversation limit of 8
   turns, and no loop outcome is produced for the second run.
