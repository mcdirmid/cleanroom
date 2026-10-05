<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T02:07:35Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 14044c4c4925
-->

# openai_driver_impl implementation component

imports: agent_config, json_ext, loop_conversation, loop_guard, openai_config, openai_ext, runner_logger, tool_provider
implements: loop_driver

## Intent

Executing robust model loops requires managing protocol-level token limits, handling tool failures gracefully, and binding runtime parameters to API completion endpoints. The openai_driver_impl implementation component constructs completion requests using configuration parameters from openai config and agent config, dispatches model-invoked tool executions through the tool manager, injects recovery guidance on failures, and resumes truncated completions.

By repairing incomplete code edits using indented sentinel exceptions, supporting follow-up tool chains with prior-thought reasoning, and streaming audit summaries to runner loggers, the driver maintains resilient autonomous problem-solving loops.

## Factored Contracts

### Contracts

- The loop driver transmits a completion request following OpenAI chat completion conventions. [transmit_openai_completion_request]
- The loop driver binds model parameters from openai config. [bind_model_parameters]
- The loop driver orders tools deterministically by tool name. [order_tools_by_name]
- The loop driver orders tool parameters deterministically by parameter sequence. [order_tool_parameters_by_sequence]
- The loop driver correlates tool results with model invocations according to OpenAI tool calling conventions. [correlate_tool_results_with_invocations]
- When a model response is truncated at the generation limit, the loop driver recovers truncated tool invocations by repairing unclosed arguments into valid JSON. [recover_truncated_tool_invocations]
- When a replace file content invocation provides a target file, target content, and partial replacement content, any trailing incomplete line without a terminating newline is deleted and replaced with a raise NotImplementedError sentinel carrying an incrementing session truncation identifier matching indentation. [repair_replace_file_content_with_sentinel]
- When the last line is complete, the sentinel is appended on the next line matching indentation. [append_sentinel_on_next_line]
- Repairing executes the tool to persist partial modifications. [execute_repaired_tool_to_persist_mods]
- Repairing returns an actionable notice directing the model to resume implementation targeting the sentinel. [return_notice_targeting_sentinel]
- When truncation cannot be repaired, the loop driver terminates the truncated tool invocation by appending a tool failure response with the tool's suppression key. [terminate_unrepairable_truncated_tool]
- When a truncated tool invocation is handled, the loop driver resumes generation with a continuation turn. [resume_generation_with_continuation]
- When a model completion response fails with an incomplete tool call error, the loop driver appends an actionable recovery notice directing smaller edits. [append_recovery_notice_on_incomplete_tool_call]
- When handling an incomplete tool call error, the loop driver resumes generation with a continuation turn. [continue_turn_on_incomplete_tool_call]
- When repeated consecutive truncation failures occur, the loop driver halts execution with an unexpected failure. [halt_on_repeated_truncation_failures]
- The loop driver logs log events for turn requests, completions, and tool results to the runner logger. [log_turn_events_to_runner_logger]
- The loop driver formats compact summaries with turn identifiers, token size, percentage of cached tokens, tool names, arguments, and execution status without inlining file content. [format_compact_log_summaries]
- The loop driver includes corrective reminders in the transcript when present. [include_corrective_reminders_in_transcript]
- When the loop guard produces a loop failure, execution halts with an unexpected failure carrying the explanation. [halt_on_loop_guard_failure]
- When the loop guard produces a loop reminder, the loop driver appends the reminder to the conversation. [append_loop_guard_reminder]
- Productive tool executions that modify workspace files or advance the guide step clear repetition tracking in the loop guard. [clear_guard_tracking_on_progress]
- When tool execution produces a non-terminating failure response, the loop driver appends failure feedback to the conversation. [continue_on_non_terminating_failure]
- When tool execution produces a terminating failure response, the loop driver halts execution with an unexpected failure. [halt_on_terminating_failure]
- When tool execution produces a successful termination response, the loop driver returns a successful loop outcome. [conclude_on_successful_termination]
- When configured by agent config to inject followups, a response specifying a follow-up tool call prompts execution of the designated tool. [execute_designated_followup_tool]
- Follow-up execution appends a synthetic assistant invocation carrying reasoning text as prior thought. [append_synthetic_assistant_with_reasoning]
- Follow-up execution appends the follow-up response to conversation immediately following the originating response. [append_followup_response_immediately]
- When a model response produces no tool executions, the loop driver appends a prompt reminding that progress requires invoking tools. [prompt_tool_invocation_when_none_called]
- When interaction turns reach the conversation limit from agent config, the loop driver halts execution with an unexpected failure. [halt_when_turn_limit_reached]

## Woven Contracts

- Driving turns constructs OpenAI completion payloads with sorted tools and parameters, transmitting over HTTPS and correlating call results. \[transmit_openai_completion_request, bind_model_parameters, order_tools_by_name, order_tool_parameters_by_sequence, correlate_tool_results_with_invocations, openai_ext: [define_chat_completion_payload, establish_https_transport], openai_config: [provide_model_name, provide_timeout]\]
- Truncated generations are recovered by repairing partial replace file content payloads with indented NotImplementedError sentinels or terminated with failure responses before continuation. \[recover_truncated_tool_invocations, repair_replace_file_content_with_sentinel, append_sentinel_on_next_line, execute_repaired_tool_to_persist_mods, return_notice_targeting_sentinel, terminate_unrepairable_truncated_tool, resume_generation_with_continuation, json_ext: [repair_input_supplied, repair_strip_whitespace, repair_locate_opening_brace, repair_balance_string_quotes, repair_strip_trailing_commas, repair_close_nested_containers]\]
- Incomplete tool call errors prompt actionable recovery guidance for smaller edits across continuation turns or halt upon repeated failures. [append_recovery_notice_on_incomplete_tool_call, continue_turn_on_incomplete_tool_call, halt_on_repeated_truncation_failures]
- Execution events, token consumption metrics, and compact summaries stream to the runner logger. \[log_turn_events_to_runner_logger, format_compact_log_summaries, include_corrective_reminders_in_transcript, runner_logger: [consume_log_events]\]
- Repetition tracking halts on fatal loop failures or injects reminders, while productive modifications reset guard counters. \[halt_on_loop_guard_failure, append_loop_guard_reminder, clear_guard_tracking_on_progress, loop_guard: [evaluate_consecutive_tools, clear_repetition_on_progress]\]
- Follow-up tool specifications execute chained tool calls with synthetic prior thought reasoning. \[execute_designated_followup_tool, append_synthetic_assistant_with_reasoning, append_followup_response_immediately, tool_provider: [call_by_name]\]
- Tool outcomes govern loop continuation, halting on terminal failures, prompting on missing tool calls, and aborting upon turn limit exhaustion. \[continue_on_non_terminating_failure, halt_on_terminating_failure, conclude_on_successful_termination, prompt_tool_invocation_when_none_called, halt_when_turn_limit_reached, loop_driver: [conclude_atomically_on_termination, produce_loop_outcome_on_termination], agent_config: [expose_execution_parameters]\]
