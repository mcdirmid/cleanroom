<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Complete the conversation capability statements and name the stubbing operation consistently
CODE_HASH: 16660b052eb5
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# loop_conversation interface component

imports: tool_provider

## Purpose

The loop_conversation interface component maintains chronological conversation state for an agent session, generating model-ready request messages and stubbing superseded results.

Repeated tool executions cause message context to explode and degrade model performance. The loop_conversation interface component manages message accumulation across turns, formatting model-ready request sequences while replacing superseded tool results with compact stubs in place to preserve prompt caching and bound token growth.

**Out of scope:** The loop_conversation interface component does not transmit network requests to model providers, dispatch tool calls, or manage agent termination outcomes; these are handled by other components.

## Types and Behavior

A *conversation message* is an entry in an agent conversation, having a *role*, text *content*, a *tool call id* when correlating tool invocations and responses, a *tool name* associated with a tool invocation or response, a *reminder* advising the agent on future actions and constraints, serialized *tool arguments*, and whether the message is a *stub* replacing superseded content in a conversation.

A *model request* is a formatted sequence of messages prepared for transmission to a language model.

An agent session's *conversation* maintains the chronological messages of an agent run.

The conversation can be initialized with initial messages that include task instructions, and can *append* the messages and tool responses that tool execution produces.

The conversation *stubs* prior responses and their correlating tool arguments when a suppression key identifies them as superseded, and provides a model request for transmission to a language model.
