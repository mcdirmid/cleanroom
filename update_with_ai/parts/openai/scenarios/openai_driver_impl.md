<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T03:12:27Z
CHANGE: Author openai openai_driver_impl concrete scenarios
CODE_HASH: 1af31d618d94
-->

# Concrete scenarios for `openai_driver_impl` (implementation)

Scenarios 1 through 5 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 6
through 10 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — A response with no tool execution does not stop the run

Given: the conversation for the agent session holds one user message, "Clean the unit widget in
scope_a.", the loop driver has not yet run, and the conversation holds no loop reminder.

1. The agent runs the loop driver.
   Observed: one model request is sent for the agent session, and the model answers with an
   assistant message whose content is "Here is what I would do next." and no tool execution.
   Realized by: the component's own turn loop, which obtains the model request from
   `loop_conversation`; the completion request transmitted and its answer parsed through
   `openai_ext`, bound to the model name, base url, api key, timeout, temperature, and max tokens
   that `openai_config` supplies.

2. The model request for the next turn is sent.
   Observed: the conversation now holds a tool reminder stating that session progress and
   conclusion require executing tools, the reminder is appended after that assistant message, and
   the run has not concluded.
   Realized by: the component's own handling of a model answer with no tool execution, which
   appends the tool reminder through `loop_conversation` and continues the turn loop instead of
   concluding the run.

### Scenario 2 — One tool execution carrying a successful termination outcome

Given: the conversation holds one user message, "Clean the unit widget in scope_a.", the tool
manager has installed `read_file`, and the next model answer carries the tool call identifier
`call_11` for `read_file` with the serialized arguments
`{"path": "/ws/alpha_scope_a/widget.md"}`.

1. The agent runs the loop driver.
   Observed: the assistant message is appended to the conversation carrying `call_11`; the tool
   manager is asked to execute `read_file` with `{"path": "/ws/alpha_scope_a/widget.md"}` converted
   into actual values; and the response is appended to the conversation with the tool call
   identifier `call_11` and the tool name `read_file`.
   Realized by: the component's own append of the model answer through `loop_conversation`; the
   tool definition schemas and dispatch of `tool_provider`, which convert the serialized arguments
   into actual values; the completion response parsing and tool call extraction through `openai_ext`;
   and the component's own append of the resulting response through `loop_conversation`.

2. The response for `call_11` reports the output "42 lines" and a termination outcome that
   succeeds.
   Observed: the run concludes atomically once, the loop outcome carries a termination outcome that
   succeeds, and the final conversation in that outcome is the conversation above, with the user
   message, the assistant message, and the response in that order.
   Realized by: the component's own termination handling, which concludes the run exactly once and
   returns the loop outcome carrying the successful termination outcome of the tool response and
   the final conversation state held by `loop_conversation`.

### Scenario 3 — Several tool executions dispatched in one turn

Given: the next model answer carries the tool call identifiers `call_12` for `read_file` with
arguments `{"path": "/ws/alpha_scope_a/widget.md"}`, `call_13` for `read_file` with arguments
`{"path": "/ws/alpha_scope_a/gadget.md"}`, and `call_14` for `edit_file` with arguments
`{"path": "/ws/alpha_scope_a/widget.md", "old": "a", "new": "b"}`.

1. The agent runs the loop driver.
   Observed: the tool manager executes all three calls and three responses are appended to the
   conversation, correlated to `call_12`, `call_13`, and `call_14` respectively, each carrying the
   tool name it was executed for.
   Realized by: tool dispatch through `tool_provider` for every tool call the model answer carries,
   and the component's own append of each returned response through `loop_conversation`,
   correlated by the identifiers the calls carry.

2. The response for `call_13` reports that execution failed with the diagnostic feedback
   "no such file" and does not terminate the conversation.
   Observed: the failure does not conclude the run, the response for `call_13` is visible in the
   conversation with that diagnostic feedback, and the next model request holds the assistant
   message, all three responses, and a tool reminder.
   Realized by: the component's own handling of a response that reports failure without terminating,
   which appends the diagnostic feedback through `loop_conversation` and continues the turn loop;
   and the reminder that `tool_provider` attaches to its tool responses and that
   `loop_conversation` formats into the assembled request.

### Scenario 4 — A tool response that names the next tool to call

Given: the response for `call_11` designates a follow-up tool call of `edit_file` with the wired
parameter bindings `{"path": "/ws/alpha_scope_a/widget.md", "old": "42 lines", "new": "38 lines"}`
and the reasoning text "the contract still reports the stale line count".

1. The agent runs the loop driver.
   Observed: the model is not asked for a new answer before the follow-up call is executed, and the
   tool manager executes `edit_file` with those wired parameter bindings converted into actual
   values.
   Realized by: the component's own follow-up handling, gated by the follow-up injection policy from
   `agent_config`, and the dispatch of the designated call through `tool_provider`, which converts
   its wired parameter bindings into actual values.

2. The follow-up execution returns its response.
   Observed: the response is appended to the conversation correlated with the follow-up tool call,
   the conversation records the reasoning text "the contract still reports the stale line count",
   and the turn loop continues.
   Realized by: the component's own append through `loop_conversation` of a synthetic assistant
   invocation carrying the reasoning text as preceding thought, followed immediately by the
   response of the follow-up call, and the component's own continuation of the turn loop.

### Scenario 5 — Runaway repetition and the conversation limit

Given: the model request for the sixth turn carries `read_file` with the arguments
`{"path": "/ws/alpha_scope_a/widget.md"}` for the fourth consecutive time, the loop guard for the
session has already produced the loop reminder for `read_file` twice, the loop guard's fatal
threshold for the session is 4 consecutive executions, the conversation limit is 8 turns, and no
tool execution has terminated the conversation.

1. The agent runs the loop driver.
   Observed: the run halts with an unexpected failure whose message reports the repetition of
   `read_file`, and no loop outcome is produced for the agent session.
   Realized by: the repetitive execution evaluation through `loop_guard`, whose loop failure the
   component converts into an unexpected failure carrying the loop failure explanation, without
   returning a loop outcome.

2. The agent starts a second run whose conversation reaches the eighth turn without any tool
   execution producing a termination outcome.
   Observed: the second run halts with an unexpected failure naming the conversation limit of 8
   turns, and no loop outcome is produced for the second run.
   Realized by: the component's own turn count measured against the conversation limit that
   `agent_config` supplies, and its own halt without a loop outcome once that limit is reached.

## Implementation-only

### Scenario 6 — Binding the completion request from configuration

Given: the openai config supplies the model name `widget-4o`, the base url
`https://models.example.test/v1`, the api key `key-alpha-0001`, a timeout of 30 seconds, a
temperature of 0.2, and a max tokens upper bound of 4096; the agent configuration requests no
follow-up injection; and the tool manager has installed the tools `write_file` and `read_file`,
whose definitions carry the parameters `path`, `content`, and `encoding`.

1. The agent runs the loop driver for a conversation holding the user message "Clean the unit
   widget in scope_a.".
   Observed: the completion request is transmitted to `https://models.example.test/v1` carrying the
   model name `widget-4o` and the api key `key-alpha-0001`, with a timeout of 30 seconds, a
   temperature of 0.2, and a max tokens upper bound of 4096, and its tool definitions list
   `read_file` before `write_file`.
   Realized by: the component's own construction of the completion request from the model name,
   base url, api key, timeout, temperature, and max tokens that `openai_config` supplies; the
   request payload schema and transport through `openai_ext`; and the tool definition schemas of
   `tool_provider`, which the component orders deterministically by tool name.

2. The agent inspects the parameters of the `write_file` definition in that request.
   Observed: the parameters appear in the order `path`, `content`, `encoding`.
   Realized by: the tool definition schemas of `tool_provider`, whose parameters the component
   orders deterministically by parameter sequence.

### Scenario 7 — Repairing a truncated replace file content invocation

Given: the session truncation identifier is 0, and a model answer is truncated at the generation
limit while carrying an invocation of the tool `replace_file_content` whose target file is
`/ws/alpha_scope_a/widget.md`, whose target content is the two-line text "widget note" followed by
"    gadget note", and whose partial replacement content ends with the incomplete line
"    sprocket not".

1. The agent runs the loop driver and the truncated invocation is repaired.
   Observed: the incomplete trailing line is deleted and replaced by a sentinel raising a non
   implemented error that carries the session truncation identifier 1 and matches the indentation
   of the deleted line; the tool is executed so the partial modification is persisted; and an
   actionable notice directing the model to resume implementation targeting the sentinel is
   appended to the conversation.
   Realized by: the component's own truncation repair, which removes the trailing incomplete line
   and writes the sentinel, its own increment of the session truncation identifier, the argument
   repair of `json_ext` for the unclosed invocation arguments, and its own dispatch of the
   repaired invocation through `tool_provider`.

2. A second model answer is truncated while carrying a partial replacement content whose last line
   is complete, and the session truncation identifier is 1.
   Observed: the sentinel is appended on the next line, indented to match the last line, and
   carries the session truncation identifier 2.
   Realized by: the same repair, which appends the sentinel instead of replacing a line when the
   last line of the partial content is complete, and its own increment of the session truncation
   identifier.

### Scenario 8 — Other truncated invocations and incomplete tool call errors

Given: the tool `read_file` declares the suppression key `workspace_scan`, no truncation failure
has occurred yet in the session, and a model answer is truncated at the generation limit while
carrying an invocation of the tool `read_file` whose arguments are unclosed.

1. The agent runs the loop driver.
   Observed: a tool failure response carrying the suppression key `workspace_scan` is appended, and
   generation resumes with a continuation turn.
   Realized by: the component's own truncation handling for an invocation that is not a replace
   file content invocation, the argument repair of `json_ext`, and its own dispatch of a tool
   failure response carrying the suppression key that `tool_provider` supplies.

2. A model completion then fails with an incomplete tool call error.
   Observed: an actionable recovery notice directing smaller edits is appended to the conversation,
   and the turn loop continues.
   Realized by: the component's own recovery notice for an incomplete tool call error and its own
   continuation of the turn loop.

3. Two further consecutive completions fail with the same incomplete tool call error.
   Observed: the run halts with an unexpected failure naming the repeated truncation failures, and
   no loop outcome is produced.
   Realized by: the component's own count of consecutive truncation failures over the completion
   outcomes parsed by `openai_ext`, and its own halt without a loop outcome.

### Scenario 9 — Logging every turn request, completion, and tool result

Given: the conversation of the second turn holds 4200 tokens, the completion response of that turn
reports 1024 prompt tokens of which 512 are cached and 300 completion tokens, and its tool call is
`read_file` for the file `/ws/alpha_scope_a/widget.md`, whose execution returns the output
"42 lines" recorded at 2026-01-02T03:04:05Z.

1. The agent runs the loop driver for that turn.
   Observed: the runner logger receives one event for the turn request, one event for the
   completion, and one event for the tool result; the completion event's summary carries the turn
   identifier 2, a conversation token size of 4000 rounded to the nearest thousand, a cached
   percentage of 50 from the usage fields, and the tool call name `read_file` with its arguments;
   and the tool result event's summary names the file `/ws/alpha_scope_a/widget.md` with the
   timestamp 2026-01-02T03:04:05Z and does not inline the file content.
   Realized by: the component's own runner log events for every turn request, completion, and tool
   result, consumed by `runner_logger`; the compact summary built from the conversation size held
   by `loop_conversation`, the usage fields parsed by `openai_ext`, and the tool outcome from
   `tool_provider`; and the component's own inclusion of corrective reminders in the transcript
   when the loop guard supplies one.

### Scenario 10 — Repetition tracking cleared by productive execution

Given: the loop guard holds two consecutive executions of `read_file` for
`/ws/alpha_scope_a/widget.md` for the agent session, and the tool manager returns an `edit_file`
response that writes the workspace file `/ws/alpha_scope_a/widget.md`.

1. The agent runs the loop driver for that turn.
   Observed: the repetition tracking of the loop guard for the session is cleared, no loop reminder
   and no loop failure is produced, and the turn loop continues.
   Realized by: the component's own judgement that the execution modified a workspace file,
   followed by its own clearing of repetition tracking through `loop_guard`; the append of the
   response through `loop_conversation`; and the component's own continuation of the turn loop.
