# agent_conversation_history_impl implementation component

imports: tool_provider, openai_ext
implements: agent_conversation_history

## Purpose

The agent_conversation_history_impl implementation component realizes provider role formatting, metadata stripping, and synthetic tool invocation injection for model conversation requests.

Language model APIs impose strict role alternation invariants and reject internal orchestration fields. The agent_conversation_history_impl implementation component formats messages according to provider role schemas, strips internal metadata fields, preserves visible diagnostic notes, and pairs unprompted tool responses with antecedent synthetic assistant invocations to preserve API protocol compliance.

**Out of scope:** The agent_conversation_history_impl implementation component does not transmit network payloads to remote endpoints, enforce repetition guards, or record unbuffered log files; these are handled by other components.

## Types and Behavior

The conversation history formats messages in a model request according to OpenAI chat completion conventions for system, user, assistant, and tool messages.

When an appended tool result supersedes an earlier result for the same resource, earlier tool results matching the resource identifier—such as the target read-write file alias identified by internal metadata markers or single-instance tool executions—are replaced in place with a stub, while tool results for distinct resources and read-only files are preserved. A stub retains any reminder provided in the superseded tool response to remind the agent in subsequent turns, and when the newly appended tool result does not supply a reminder, it inherits the reminder from the superseded response.

When assembling a model request from messages in the agent conversation history:

- Messages omit internal metadata fields starting with an underscore.

- Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.

- Each unprompted tool response presented at session start is preceded in the conversation history by a synthetic assistant tool invocation message formatted according to OpenAI tool calling conventions, correlating with the response tool call identifier and ordering serialized argument parameters deterministically by parameter name, presenting the tool execution as if initiated by the model.
