# openai_ext external component

## Intent

Direct coupling between domain components and remote model API endpoints creates network fragility, vendor transport coupling, and inconsistent error handling. The openai_ext external component establishes an external boundary that encapsulates HTTP transport mechanics, request payload translation, and token usage accounting reported by OpenAI-compatible endpoints.

By defining explicit payload schemas and mapping HTTP status codes to domain error representations, the external component insulates the system from network quirks and wire protocol details.

## Factored Contracts

### Contracts

- Chat completion wire protocol defines the HTTP POST payload for the /v1/chat/completions endpoint. [define_chat_completion_payload]
- Chat completion payload includes model identifier strings. [include_model_identifier]
- Chat completion payload includes ordered message sequences. [include_ordered_messages]
- Chat completion payload includes tool definitions schema. [include_tool_definitions_schema]
- Chat completion payload includes temperature parameters. [include_temperature_parameters]
- Chat completion payload includes execution timeouts. [include_execution_timeouts]
- Transport mechanics establish HTTPS transport handling. [establish_https_transport]
- Transport mechanics construct request headers with bearer token authentication. [construct_bearer_auth_headers]
- Transport mechanics serialize request payloads. [serialize_request_payloads]
- Transport mechanics read response payloads over network connections. [read_response_payloads]
- Error translation maps 401 unauthorized errors to authentication failures. [map_401_to_auth_failures]
- Error translation maps 429 rate limit errors to throttling conditions. [map_429_to_throttling]
- Error translation maps 5xx server errors to endpoint unavailability. [map_5xx_to_unavailability]
- Error translation maps request timeouts to network deadline outcomes. [map_timeouts_to_deadline_outcomes]
- Response parsing deserializes response JSON into model message records. [deserialize_model_messages]
- Response parsing deserializes structured assistant tool calls with function names. [deserialize_tool_call_names]
- Response parsing deserializes structured assistant tool calls with argument strings. [deserialize_tool_call_args]
- Response parsing extracts completion finish reasons. [extract_finish_reasons]
- Response parsing deserializes token consumption metrics. [deserialize_token_metrics]

## Woven Contracts

- Chat completion requests are serialized into JSON with auth headers and sent over HTTPS. [define_chat_completion_payload, include_model_identifier, include_ordered_messages, include_tool_definitions_schema, include_temperature_parameters, include_execution_timeouts, establish_https_transport, construct_bearer_auth_headers, serialize_request_payloads, read_response_payloads]
- HTTP error statuses are translated into structured domain outcomes for authentication, rate limits, unavailability, and timeouts. [map_401_to_auth_failures, map_429_to_throttling, map_5xx_to_unavailability, map_timeouts_to_deadline_outcomes]
- Response payloads are parsed into message records, function tool calls, finish reasons, and token usage accounting. [deserialize_model_messages, deserialize_tool_call_names, deserialize_tool_call_args, extract_finish_reasons, deserialize_token_metrics]
