<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-11T03:12:27Z
CHANGE: Author openai openai_conversation_impl concrete scenarios
CODE_HASH: 9c6bf567dd0e
-->

# Concrete scenarios for `openai_conversation_impl` (implementation)

Scenarios 1 through 5 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 6
through 10 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Appending tool executions and correlating their responses

Given: the conversation for the agent session is empty, and the tool manager has installed
`read_file` and `edit_file`, where `read_file` produces output "42 lines" and `edit_file` produces
output "1 replacement".

1. The agent starts the session by initializing the conversation with the message whose role is
   user and whose content is "Please clean the widget contract in /ws/alpha_scope_a."
   Observed: the conversation holds that one message.
   Realized by: the component's own chronological message store, which the initialization at
   session start replaces with the supplied message.

2. The language model answers with an assistant message whose content is "I will inspect the
   contract first." and one tool call for `read_file` whose arguments serialize to
   `{"path": "/ws/alpha_scope_a/widget.md"}`.
   Observed: the assistant message is appended after the user message and carries the tool call
   identifier `call_01`.
   Realized by: the component's own append of the model answer into the chronological message
   store, and the provider role schema definitions through `openai_ext` that carry the tool call
   identifier `call_01`.

3. The tool manager returns the `read_file` response for `call_01` with output "42 lines".
   Observed: the append records that response with role tool, text content "42 lines", tool call
   identifier `call_01`, and tool name `read_file`, and the model request now holds the user
   message, the assistant message with its tool call, and that response, in that order.
   Realized by: tool response notes, content, and reminders through `tool_provider`; JSON
   serialization mechanics through `json_ext` for the serialized arguments; the component's own
   append of the response with the role, content, tool call identifier, and tool name it carries;
   and the component's own assembly of the model request from the chronological message store.

### Scenario 2 — Stubbing a superseded response in place

Given: the conversation holds an assistant message carrying the tool call identifier `call_02`
for `read_file` with arguments `{"path": "/ws/alpha_scope_a/widget.md"}`, the response for
`call_02` with output "42 lines", and a later response for `call_03` naming the tool `edit_file`
with output "1 replacement" and the suppression key `symbol_lookup`.

1. The tool manager returns a response that carries the suppression key `symbol_lookup` and the
   output "38 lines".
   Observed: the earlier response with suppression key `symbol_lookup` is replaced in place by a
   stub marking it superseded, the new response appears with output "38 lines", and the response
   for `call_02` still appears with its content "42 lines".
   Realized by: the suppression key the arriving response carries through `tool_provider`, and the
   component's own suppression-key buffer, which retains up to three most recent responses sharing
   `symbol_lookup` and replaces the older response in place through the component's own stub
   construction.

2. The agent asks the conversation for the model request.
   Observed: the stub appears at the position of the superseded response with the tool name
   `edit_file`, the serialized arguments `{"path": "/ws/alpha_scope_a/widget.md"}` of its
   correlating tool call are replaced together with it, and the text "1 replacement" appears
   nowhere in the request.
   Realized by: the component's own stub construction, which keeps the tool name and the reminder
   of the superseded response; the component's own argument replacement in the correlating
   assistant invocation, which keeps every parameter key and every non-string value, preserves
   file path parameters, and replaces every other string value with a stub marker retaining the
   trailing characters within the supersede arg keep limit that `agent_config` resolves from the
   agent session configuration; and JSON serialization mechanics through `json_ext`.

### Scenario 3 — Changing the initial messages before the session runs

Given: the conversation has been initialized with the messages "Obey the repository conventions."
and "Clean the unit widget in scope_a.".

1. The agent initializes the conversation again with the single message "Clean the unit widget in
   scope_a." and asks for the model request.
   Observed: the request holds exactly that one message, and neither "Obey the repository
   conventions." nor the earlier message "Clean the unit widget in scope_a." appears before it.
   Realized by: the component's own initialization, which replaces the held message sequence in
   the chronological message store rather than appending to it.

### Scenario 4 — A response for a tool call the conversation never saw

Given: the conversation holds the user message "Clean the unit widget in scope_a." and one
assistant message that carries the tool call identifier `call_07` for `read_file`.

1. The tool manager returns a response whose tool call identifier is `call_99` and whose output is
   "no such file".
   Observed: the request still holds the user message and the assistant message that carries
   `call_07`, the response for `call_99` is appended after them, and the conversation reports no
   second response correlated with `call_07`.
   Realized by: the component's own append, which files the response under the tool call
   identifier it carries and correlates responses only with the invocations that name them, so the
   response for `call_99` is not attributed to the invocation carrying `call_07`; and provider
   role formatting through `openai_ext`.

### Scenario 5 — Superseding when nothing is superseded yet

Given: the empty conversation has been initialized with the message "Clean the unit widget in
scope_a.".

1. The tool manager returns the first response of the session with the suppression key
   `workspace_scan` and the output "13 files".
   Observed: the conversation holds the user message and that one response with output "13 files",
   and no stub appears anywhere in the model request.
   Realized by: the component's own suppression-key buffer, which records the first response for
   `workspace_scan` without replacing any held response; the response fields through
   `tool_provider`; and JSON serialization mechanics through `json_ext` for the model request.

2. The tool manager returns a second response with the same suppression key `workspace_scan` and
   the output "0 files".
   Observed: the first response is replaced in place by a stub marking it superseded, and the only
   superseded entry in the request is that stub at the position of the first response.
   Realized by: the same suppression-key buffer for `workspace_scan`, which replaces the earlier
   response in place through the component's own stub construction and leaves that stub as the
   only superseded entry.

## Implementation-only

### Scenario 6 — The retention limit of a suppression key

Given: the empty conversation has been initialized with the user message "Clean the unit widget in
scope_a.", and the workspace scan tool declares the suppression key `workspace_scan` on every
response.

1. The tool manager returns four responses in order, each carrying the suppression key
   `workspace_scan`, with the outputs "13 files", "0 files", "7 files", and "2 files".
   Observed: the response with output "13 files" is replaced in place by a stub marking it
   superseded, the responses with outputs "0 files", "7 files", and "2 files" appear intact in the
   model request, and that stub is the only superseded entry.
   Realized by: the component's own suppression-key buffer, which retains the three most recent
   responses sharing `workspace_scan` and replaces every older response beyond that limit with a
   stub.

2. The tool manager returns a fifth response carrying the suppression key `workspace_scan` with
   the output "5 files".
   Observed: the responses with outputs "13 files" and "0 files" are both stubs marking them
   superseded, and the responses with outputs "7 files", "2 files", and "5 files" appear intact.
   Realized by: the same buffer, now holding the three most recent responses for `workspace_scan`
   and having superseded the two oldest.

### Scenario 7 — Preserving the shape of the superseded arguments

Given: the conversation holds an assistant message carrying the tool call identifier `call_31` for
`edit_file` with the serialized arguments
`{"path": "/ws/alpha_scope_a/widget.md", "old": "widget note alpha", "new": "widget note beta",
"replace_all": true, "count": 3}` and the response for `call_31` with output "1 replacement" and
the suppression key `widget_edit`, and the supersede arg keep limit of the agent session
configuration is 4.

1. The tool manager returns a response carrying the suppression key `widget_edit` with the output
   "0 replacements", and the agent asks the conversation for the model request.
   Observed: the stub replaces the superseded response; its correlating assistant invocation keeps
   the parameter names `path`, `old`, `new`, `replace_all`, and `count`; the parameter `path`
   still carries `/ws/alpha_scope_a/widget.md`; the parameter `replace_all` still carries the
   value true and the parameter `count` still carries the value 3; and the parameters `old` and
   `new` carry stub markers retaining the trailing 4 characters `lpha` and `beta`.
   Realized by: the component's own argument replacement over the correlating invocation, which
   keeps every parameter key and every non-string value, preserves file path parameters, and
   replaces each other string value with a stub marker retaining the trailing characters within
   the supersede arg keep limit that `agent_config` resolves from the agent session configuration;
   and JSON serialization mechanics through `json_ext`.

### Scenario 8 — Reminders carried by stubs and inherited by new responses

Given: the conversation has been initialized with the user message "Clean the unit widget in
scope_a.", and the tool manager returns a response carrying the suppression key `workspace_scan`,
the output "13 files", and the reminder "read the modified files before editing again".

1. That response is appended, a second response carrying the same suppression key
   `workspace_scan`, the output "0 files", and no reminder is appended, and the agent asks for the
   model request.
   Observed: the stub replacing the first response carries the reminder "read the modified files
   before editing again", the second response inherits that same reminder, and the assembled
   request formats the reminder on both the stub and the second response.
   Realized by: the component's own reminder retention on the superseded stub, its own inheritance
   of that reminder by a newly appended response that omits one, and the visible tool message
   content assembled from the notes, content, and reminders that `tool_provider` supplies.

### Scenario 9 — A synthetic invocation for an unprompted response

Given: at session start the conversation has been initialized with the user message "Clean the
unit widget in scope_a." and holds no assistant message, and the tool manager presents a response
carrying the tool call identifier `call_21`, the tool name `read_file`, the output "42 lines", and
wired arguments binding `path` to `/ws/alpha_scope_a/widget.md` and `encoding` to `utf-8`.

1. The agent asks the conversation for the model request.
   Observed: the request holds an assistant tool invocation before that response, the invocation
   correlates with the identifier `call_21`, and its serialized argument parameters appear in the
   order `encoding` then `path`.
   Realized by: the component's own injection of a synthetic assistant invocation for an
   unprompted tool response presented at session start, formatted according to the tool calling
   conventions of `openai_ext`, with its serialized argument parameters ordered deterministically
   by parameter name through `json_ext`.

### Scenario 10 — A response whose suppression key matches nothing held

Given: the conversation holds a response carrying the suppression key `symbol_lookup` with the
output "13 files", and the tool manager returns a response carrying the suppression key
`workspace_scan` with the output "7 files".

1. The agent appends that response and asks for the model request.
   Observed: the response carrying the suppression key `symbol_lookup` still appears with the
   output "13 files", the new response appears with the output "7 files", and no stub appears
   anywhere in the request.
   Realized by: the component's own suppression-key buffer, which supersedes only responses
   sharing the key of the arriving response and preserves responses with unmatched keys intact.
