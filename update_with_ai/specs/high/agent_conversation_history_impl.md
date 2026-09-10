# agent_conversation_history_impl implementation component

imports: tool_provider, openai_ext
implements: agent_conversation_history

## Purpose

The agent_conversation_history_impl implementation component realizes provider role formatting, response stubbing, and synthetic tool invocation injection for model conversation requests.

Language model APIs impose strict role alternation invariants and reject uncoordinated orchestration fields. The agent_conversation_history_impl implementation component formats messages according to provider role schemas, stubs superseded tool responses, preserves visible diagnostic notes, and pairs unprompted tool responses with antecedent synthetic assistant invocations to preserve API protocol compliance.

**Out of scope:** The agent_conversation_history_impl implementation component does not transmit network payloads to remote endpoints, enforce repetition guards, or record unbuffered log files; these are handled by other components.

## Types and Behavior

The conversation history formats messages in a model request according to OpenAI chat completion conventions for system, user, assistant, and tool messages.

A tool response's suppression key identifies the latest preceding response with the same key in the conversation history for replacement with a stub, while responses with unmatched keys are preserved intact. A stub retains the reminder from the superseded tool response, which the newly appended response inherits when omitted.

When assembling a model request from messages in the agent conversation history:

- Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.

- Each unprompted tool response presented at session start is preceded in the conversation history by a synthetic assistant tool invocation message formatted according to OpenAI tool calling conventions, correlating with the response tool call identifier and ordering serialized argument parameters deterministically by parameter name, presenting the tool execution as if initiated by the model.
