# conversation_history

imports: tool_provider
types from tool_provider: tool result

## Purpose

Maintains chronological conversation state for an agent run, formatting model request messages and stubbing superseded results.

Repeated tool executions cause message context to explode and degrade model performance. Conversation history manages message accumulation, generating model-ready request messages while replacing superseded tool results with stubs in place to preserve prompt caching and bound token growth.

## Types

- A *conversation history* is a chronological sequence of *messages* for an agent run
- A *conversation history factory* is a provider that constructs fresh *conversation histories*
- A *message* is an entry in a *conversation history* (such as system instructions, a user prompt, or model responses)
- A *stub* is a placeholder *message* replacing superseded content in a *conversation history*
- A *model request* is a formatted sequence of *messages* prepared for transmission to a language model

## Behavior

- Creating a *conversation history* through a *conversation history factory* yields a fresh *conversation history*.
- Initial *messages* can initialize a *conversation history*.
- Appending *messages* and *tool results* adds them to a *conversation history* in chronological order.
- When an appended *tool result* supersedes an earlier result for the same resource, the earlier result is replaced in place with a *stub*.
- A *conversation history* provides a *model request* for a language model.
