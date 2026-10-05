<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 3cba7a65f454
-->

# loop_driver interface component

imports: agent_config, loop_conversation, loop_guard, runner_logger, tool_provider

## Intent

Autonomous agent tasks require multi-turn interaction loops where model decisions trigger tool executions. The loop_driver interface component coordinates this turn lifecycle: sending formatted model requests from conversation, dispatching tool calls to the tool manager, evaluating loop guards, and recording audit events until an explicit termination outcome concludes the run.

By driving iterative turns, executing follow-up actions, dispatching runner log events, and enforcing turn caps, the driver maintains execution forward progress while preventing infinite conversational cycles.

## Factored Contracts

### Typing

- A loop outcome carries a termination outcome from tool execution.
- A loop outcome carries the final state of the conversation.

### Contracts

- The loop driver drives turns by sending a model request to a language model. [drive_turns_sending_model_request]
- The loop driver drives turns by executing requested tools. [drive_turns_executing_tools]
- The loop driver appends model responses to the conversation. [append_model_responses]
- The loop driver correlates tool execution responses with originating tool call identifiers in the conversation. [correlate_tool_responses]
- The loop driver dispatches follow-up tool calls specified by tool responses. [dispatch_followup_tool_calls]
- The loop driver records follow-up executions in the conversation. [record_followup_in_conversation]
- The loop driver records log events for interaction turns to the runner logger. [record_turn_events_to_logger]
- The loop driver records log events for tool executions to the runner logger. [record_tool_events_to_logger]
- The loop driver records log events for turn outcomes to the runner logger. [record_outcome_events_to_logger]
- The loop driver evaluates tool executions with the loop guard. [evaluate_tools_with_guard]
- The loop driver injects loop reminders into the conversation on detected repetition. [inject_reminders_on_repetition]
- The loop driver halts with an unexpected failure on runaway repetition. [halt_on_runaway_repetition]
- When a model response contains no tool executions, the loop driver injects a tool reminder into the conversation. [inject_reminder_when_no_tools_called]
- When a model response contains no tool executions, the loop driver continues the turn loop. [continue_loop_when_no_tools_called]
- When tool execution produces a termination outcome, the loop driver concludes atomically. [conclude_atomically_on_termination]
- When tool execution produces a termination outcome, the loop driver produces a loop outcome. [produce_loop_outcome_on_termination]
- When the termination outcome indicates a failing outcome, the loop driver halts with an unexpected failure. [halt_on_failing_termination]
- When the conversation limit is exceeded, the loop driver halts with an unexpected failure. [halt_when_conversation_limit_exceeded]

## Woven Contracts

- The driver orchestrates interaction turns by sending model requests, appending responses, correlating tool calls, and streaming log events. \[drive_turns_sending_model_request, drive_turns_executing_tools, append_model_responses, correlate_tool_responses, record_turn_events_to_logger, record_tool_events_to_logger, record_outcome_events_to_logger, loop_conversation: [provide_model_request, append_messages_to_conversation], runner_logger: [consume_log_events]\]
- Follow-up tool calls indicated in responses are executed automatically and recorded into the ongoing conversation. \[dispatch_followup_tool_calls, record_followup_in_conversation, loop_conversation: [append_tool_responses_to_conversation]\]
- Repetitive behaviors and missing tool calls trigger advisory reminders, while runaway repetition, fatal termination, or turn exhaustion aborts execution. \[evaluate_tools_with_guard, inject_reminders_on_repetition, halt_on_runaway_repetition, inject_reminder_when_no_tools_called, continue_loop_when_no_tools_called, halt_on_failing_termination, halt_when_conversation_limit_exceeded, loop_guard: [evaluate_consecutive_tools, evaluate_consecutive_edits], agent_config: [expose_execution_parameters]\]
- Successful tool termination concludes the loop atomically, returning the final conversation state and outcome record. \[conclude_atomically_on_termination, produce_loop_outcome_on_termination, tool_provider: [call_by_name]\]
