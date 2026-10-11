<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:09:19Z
CHANGE: Author loop-phase loop_conversation concrete scenarios
CODE_HASH: 6099dd1983b6
-->

# Concrete scenarios for `loop_conversation` (interface)

## Scenario 1 — Appending tool executions and correlating their responses

Given: the conversation for the agent session is empty, and the tool manager has installed
`read_file` and `edit_file`, where `read_file` produces output "42 lines" and `edit_file` produces
output "1 replacement".

1. The agent starts the session by initializing the conversation with the message whose role is
   user and whose content is "Please clean the widget contract in /ws/alpha_scope_a."
   Observed: the conversation holds that one message.

2. The language model answers with an assistant message whose content is "I will inspect the
   contract first." and one tool call for `read_file` whose arguments serialize to
   `{"path": "/ws/alpha_scope_a/widget.md"}`.
   Observed: the assistant message is appended after the user message and carries the tool call
   identifier `call_01`.

3. The tool manager returns the `read_file` response for `call_01` with output "42 lines".
   Observed: the append records that response with role tool, text content "42 lines", tool call
   identifier `call_01`, and tool name `read_file`, and the model request now holds the user
   message, the assistant message with its tool call, and that response, in that order.

## Scenario 2 — Stubbing a superseded response in place

Given: the conversation holds an assistant message carrying the tool call identifier `call_02`
for `read_file` with arguments `{"path": "/ws/alpha_scope_a/widget.md"}`, the response for
`call_02` with output "42 lines", and a later response for `call_03` naming the tool `edit_file`
with output "1 replacement" and the suppression key `symbol_lookup`.

1. The tool manager returns a response that carries the suppression key `symbol_lookup` and the
   output "38 lines".
   Observed: the earlier response with suppression key `symbol_lookup` is replaced in place by a
   stub marking it superseded, the new response appears with output "38 lines", and the response
   for `call_02` still appears with its content "42 lines".

2. The agent asks the conversation for the model request.
   Observed: the stub appears at the position of the superseded response with the tool name
   `edit_file`, the serialized arguments `{"path": "/ws/alpha_scope_a/widget.md"}` of its
   correlating tool call are replaced together with it, and the text "1 replacement" appears
   nowhere in the request.

## Scenario 3 — Changing the initial messages before the session runs

Given: the conversation has been initialized with the messages "Obey the repository conventions."
and "Clean the unit widget in scope_a.".

1. The agent initializes the conversation again with the single message "Clean the unit widget in
   scope_a." and asks for the model request.
   Observed: the request holds exactly that one message, and neither "Obey the repository
   conventions." nor the earlier message "Clean the unit widget in scope_a." appears before it.

## Scenario 4 — A response for a tool call the conversation never saw

Given: the conversation holds the user message "Clean the unit widget in scope_a." and one
assistant message that carries the tool call identifier `call_07` for `read_file`.

1. The tool manager returns a response whose tool call identifier is `call_99` and whose output is
   "no such file".
   Observed: the request still holds the user message and the assistant message that carries
   `call_07`, the response for `call_99` is appended after them, and the conversation reports no
   second response correlated with `call_07`.

## Scenario 5 — Superseding when nothing is superseded yet

Given: the empty conversation has been initialized with the message "Clean the unit widget in
scope_a.".

1. The tool manager returns the first response of the session with the suppression key
   `workspace_scan` and the output "13 files".
   Observed: the conversation holds the user message and that one response with output "13 files",
   and no stub appears anywhere in the model request.

2. The tool manager returns a second response with the same suppression key `workspace_scan` and
   the output "0 files".
   Observed: the first response is replaced in place by a stub marking it superseded, and the only
   superseded entry in the request is that stub at the position of the first response.
