# conversation_impl implementation component

## Intent

Language model APIs impose strict role alternation invariants and reject uncoordinated orchestration fields. The conversation_impl implementation component formats messages according to provider role schemas, prunes superseded tool interactions, preserves visible diagnostic notes, and pairs unprompted tool responses with antecedent synthetic assistant invocations to preserve API protocol compliance.

By pruning redundant previous tool outputs, maintaining reminders, and ordering argument serialization deterministically, the implementation maximizes prompt cache reuse and adheres to OpenAI conversation schemas.

## Factored Contracts

### Contracts

- The conversation formats messages in a model request according to OpenAI chat completion conventions. [format_messages_to_openai_conventions]
- A tool response's suppression key retains a buffer of up to three most recent responses sharing that key. [retain_recent_responses_in_buffer]
- Older preceding responses sharing a suppression key beyond the buffer limit and their correlating assistant tool calls are deleted from the conversation. [delete_older_responses_and_tool_calls]
- Tool responses with unmatched suppression keys are preserved intact. [preserve_unmatched_responses_intact]
- When an older response is deleted, any reminder it carries is retained. [retain_reminder_from_deleted_response]
- Newly appended responses inherit the reminder from the superseded tool response when omitted. [inherit_reminder_when_omitted]
- Tool execution response notes, content, and reminders are included in visible tool message content. [include_notes_content_reminders_in_tool_messages]
- Active reminders on messages are formatted to remind the agent in the assembled model request. [format_active_reminders_in_request]
- Each unprompted tool response at session start is preceded by a synthetic assistant tool invocation message. [precede_unprompted_response_with_synthetic_invocation]
- The synthetic assistant invocation correlates with the response tool call identifier. [correlate_synthetic_invocation_tool_call_id]
- The synthetic assistant invocation orders serialized argument parameters deterministically by parameter name. [order_synthetic_invocation_arguments]

### Woven Contracts

- Messages are formatted to OpenAI system, user, assistant, and tool role conventions. [format_messages_to_openai_conventions, conversation: [provide_model_request]]
- Tool responses sharing a suppression key retain a rolling buffer of up to three recent responses while deleting older responses and their correlating assistant tool calls. [retain_recent_responses_in_buffer, delete_older_responses_and_tool_calls, preserve_unmatched_responses_intact, retain_reminder_from_deleted_response, inherit_reminder_when_omitted, conversation: [stub_previous_responses_by_key, stub_correlating_tool_args_by_key]]
- Assembled model requests bundle execution notes, content, and active reminders into tool messages. [include_notes_content_reminders_in_tool_messages, format_active_reminders_in_request, tool_provider: [call_by_name]]
- Unprompted starter responses are paired with synthetic antecedent assistant tool calls with sorted argument keys. [precede_unprompted_response_with_synthetic_invocation, correlate_synthetic_invocation_tool_call_id, order_synthetic_invocation_arguments, conversation: [initialize_with_initial_messages]]

## Grounding

### Knowledge Provisions

- Turn conversation history formatting, model request preparation, and tool output stubbing. [loop_conversation_service]

### Inherited Deferred Requirements

- Model message sequence encoding and suppression key stubbing.
  - Grounded: [loop_conversation_service, openai_ext: [openai_wire_operations]]

### Knowledge Requirements

- JSON parsing and serializing with sorted keys.
  - Grounded: [json_ext: [json_operations]]
- Formatting tool execution messages with notes, content, and active reminders.
  - Grounded: [loop_conversation_service]
- Synthetic assistant invocation pairing for unprompted starter tool responses.
  - Grounded: [loop_conversation_service, json_ext: [json_operations]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-21T12:45:00Z
CHANGE: Delete superseded tool calls and responses beyond buffer limit instead of stubbing arguments
SPEC_QA_AUDIT: 2026-10-21T12:45:00Z
-->
