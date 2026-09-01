# openai_ext

imports: conversation_history, tool_provider
types from conversation_history: model request, message
types from tool_provider: tool metadata

## Purpose

Specifies the external OpenAI chat completion service interface for executing model requests with function calling.

Agent turn execution requires transmitting conversation messages and tool schemas to a remote language model API. OpenAI service extension defines the external request payload structure, tool parameter schema formats, and token usage accounting returned by OpenAI-compatible endpoints.

## Types

- A *model name* is an identifier designating a target language model for completion requests
- A *completion request* is an external service payload containing a *model name*, a *model request*, and *tool metadata*
- A *completion response* is an external service outcome containing generated *messages* and token usage metrics

## Behavior

- A *completion request* transmits a *model name*, formatted *messages* with role schemas and tool call identifiers, and *tool metadata* to an OpenAI-compatible endpoint.
- A *completion response* provides model-generated text or tool calls and reports prompt and completion token usage.
