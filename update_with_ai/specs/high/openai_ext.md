# openai_ext external component

## Purpose

The openai_ext external component defines the external OpenAI chat completion service boundary for executing model requests with function calling.

Direct coupling between domain components and remote model API endpoints creates network fragility, vendor transport coupling, and inconsistent error handling. The openai_ext external component establishes an external boundary that encapsulates HTTP transport mechanics, request payload translation, and token usage accounting reported by OpenAI-compatible endpoints.

**Out of scope:** The openai_ext external component does not orchestrate agent turns, enforce loop guards, or manage persistent conversation history; these are handled by other components.

## Grounding Gaps Covered

The openai_ext component provides the external domain knowledge and protocol mechanics required to execute chat completions against remote OpenAI-compatible endpoints:

- Chat completion wire protocol: Defines the HTTP POST request payload format for the `/v1/chat/completions` endpoint, including model identifier strings, ordered message sequences adhering to OpenAI chat completion and tool calling conventions (system prompts, user inputs, assistant responses with function tool calls, and tool call results correlated by call identifier), tool definitions schema conforming to function-calling specifications, temperature parameters, and execution timeouts.

- Endpoint transport and communication mechanics: Establishes HTTPS transport handling, request header construction with bearer token authentication, request serialization, and response reading over network connections.

- HTTP error status translation: Translates standard HTTP response status codes into structured domain outcomes, mapping 401 unauthorized errors to authentication failures, 429 rate limit errors to throttling conditions, 5xx server errors to endpoint unavailability, and request timeouts to network deadline outcomes.

- Completion response parsing and token usage accounting: Deserializes endpoint response JSON payloads into model-generated message records, structured assistant tool calls containing function names and argument strings, completion finish reasons, and token consumption metrics covering prompt tokens, completion tokens, and total tokens.
