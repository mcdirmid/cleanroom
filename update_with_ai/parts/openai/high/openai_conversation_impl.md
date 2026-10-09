<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-05T05:11:14Z
CHANGE: Add delegated collaborator statement for imported external and peer components
CODE_HASH: bd167a457883
-->

# openai_conversation_impl implementation component

imports: agent_config, json_ext, openai_ext, tool_provider
implements: loop_conversation

## Purpose

The openai_conversation_impl implementation component realizes provider role formatting, response stubbing, and synthetic tool invocation injection for model conversation requests.

Language model APIs impose strict role alternation invariants and reject uncoordinated orchestration fields. The openai_conversation_impl implementation component formats messages according to provider role schemas, stubs superseded tool responses, preserves visible diagnostic notes, and pairs unprompted tool responses with antecedent synthetic assistant invocations to preserve API protocol compliance.

**Out of scope:** The openai_conversation_impl implementation component does not transmit network payloads to remote endpoints, enforce repetition guards, or record unbuffered log files; these are handled by other components.

**Delegated:** Wire payload schema definitions are delegated to openai_ext; JSON serialization mechanics are delegated to json_ext; tool response notes and reminders are delegated to tool_provider; session configuration is delegated to agent_config.

## Types and Behavior

The conversation formats messages in a model request according to OpenAI chat completion conventions for system, user, assistant, and tool messages.

A tool response's suppression key retains a buffer of up to three most recent responses sharing that key in the conversation, replacing older preceding responses beyond the buffer limit with stubs, while responses with unmatched keys are preserved intact. When a response is replaced with a stub, tool arguments in the correlating assistant invocation message retain their parameter keys, preserving file path parameters, preserving non-string values, and replacing other string values with a stub marker. A stub retains the reminder from the superseded tool response, which newly appended responses inherit when omitted.

When assembling a model request from messages in the conversation:

- Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.

- Each unprompted tool response presented at session start is preceded in the conversation by a synthetic assistant tool invocation message formatted according to OpenAI tool calling conventions, correlating with the response tool call identifier and ordering serialized argument parameters deterministically by parameter name, presenting the tool execution as if initiated by the model.
