# loop_conversation interface component

imports: tool_provider

## Purpose

The loop_conversation interface component maintains chronological conversation state for an agent session, generating model-ready request messages and stubbing superseded results.

Repeated tool executions cause message context to explode and degrade model performance. The loop_conversation interface component manages message accumulation across turns, formatting model-ready request sequences while replacing superseded tool results with compact stubs in place to preserve prompt caching and bound token growth.

**Out of scope:** The loop_conversation interface component does not transmit network requests to model providers, dispatch tool calls, or manage agent termination outcomes; these are handled by other components.

## Types and Behavior

A *message* is an entry in an agent conversation, having a *role*, text *content*, a *tool call id* when correlating tool invocations and responses, a *tool name* associated with a tool invocation or response, a *reminder* advising the agent on future actions and constraints, serialized *tool arguments*, and whether the message is a *stub* replacing superseded content in a conversation.

A *model request* is a formatted sequence of messages prepared for transmission to a language model.

The *conversation* is an agent session service that maintains chronological messages for an agent run.

The conversation:

- Can be initialized with initial messages, including task instructions.

- Can *append* messages and tool responses produced by tool execution.

- Stubs previous responses and correlating tool arguments identified by a suppression key.

- Provides a model request for transmission to a language model.
