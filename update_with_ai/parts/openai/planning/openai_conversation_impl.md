<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T05:33:59Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 1bcc929e9fe0
-->

# openai_conversation_impl implementation component

imports: agent_config, json_ext, openai_ext, tool_provider
implements: loop_conversation

## Intent

Language model APIs impose strict role alternation invariants and reject uncoordinated orchestration fields. The openai_conversation_impl implementation component formats messages according to provider role schemas, stubs superseded tool responses, preserves visible diagnostic notes, and pairs unprompted tool responses with antecedent synthetic assistant invocations to preserve API protocol compliance.

By pruning redundant previous tool outputs, maintaining reminders, and ordering argument serialization deterministically, the implementation maximizes prompt cache reuse and adheres to OpenAI conversation schemas.

## Factored Contracts

### Contracts

- The conversation formats messages in a model request according to OpenAI chat completion conventions. [format_messages_to_openai_conventions]
- A tool response's suppression key retains a buffer of up to three most recent responses sharing that key. [retain_recent_responses_in_buffer]
- Older preceding responses sharing a suppression key beyond the buffer limit are replaced with stubs. [replace_older_responses_with_stubs]
- Tool responses with unmatched suppression keys are preserved intact. [preserve_unmatched_responses_intact]
- When a response is replaced with a stub, tool arguments in the correlating assistant invocation retain parameter keys. [retain_parameter_keys_in_stub]
- When a response is replaced with a stub, non-string argument values are preserved. [preserve_non_string_values_in_stub]
- When a response is replaced with a stub, file path parameters are preserved intact. [preserve_file_path_parameters_in_stub]
- When a response is replaced with a stub, other string argument values are replaced with a stub marker. [stub_other_string_values_in_stub]
- A stub retains the reminder from the superseded tool response. [retain_reminder_in_stub]
- Newly appended responses inherit the reminder from the superseded tool response when omitted. [inherit_reminder_when_omitted]
- Tool execution response notes, content, and reminders are included in visible tool message content. [include_notes_content_reminders_in_tool_messages]
- Active reminders on messages and stubs are formatted to remind the agent in the assembled model request. [format_active_reminders_in_request]
- Each unprompted tool response at session start is preceded by a synthetic assistant tool invocation message. [precede_unprompted_response_with_synthetic_invocation]
- The synthetic assistant invocation correlates with the response tool call identifier. [correlate_synthetic_invocation_tool_call_id]
- The synthetic assistant invocation orders serialized argument parameters deterministically by parameter name. [order_synthetic_invocation_arguments]

## Woven Contracts

- Messages are formatted to OpenAI system, user, assistant, and tool role conventions. \[format_messages_to_openai_conventions, loop_conversation: [provide_model_request], openai_ext: [include_ordered_messages]\]
- Tool responses sharing a suppression key retain a rolling buffer of up to three recent responses while replacing older responses with stubs. \[retain_recent_responses_in_buffer, replace_older_responses_with_stubs, preserve_unmatched_responses_intact, retain_reminder_in_stub, inherit_reminder_when_omitted, loop_conversation: [stub_previous_responses_by_key]\]
- Superseded assistant invocations retain parameter keys, file paths, and non-string arguments while replacing other strings with a stub marker. \[retain_parameter_keys_in_stub, preserve_file_path_parameters_in_stub, preserve_non_string_values_in_stub, stub_other_string_values_in_stub, loop_conversation: [stub_correlating_tool_args_by_key], json_ext: [parse_valid_json, serialize_sorted_keys]\]
- Assembled model requests bundle execution notes, content, and active reminders into tool messages. \[include_notes_content_reminders_in_tool_messages, format_active_reminders_in_request, tool_provider: [call_by_name]\]
- Unprompted starter responses are paired with synthetic antecedent assistant tool calls with sorted argument keys. \[precede_unprompted_response_with_synthetic_invocation, correlate_synthetic_invocation_tool_call_id, order_synthetic_invocation_arguments, loop_conversation: [initialize_with_initial_messages], json_ext: [serialize_sorted_keys]\]
