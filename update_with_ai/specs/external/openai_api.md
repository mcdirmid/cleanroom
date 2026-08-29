# Using the OpenAI API

How a module depends on and uses the OpenAI API to make agent prompt calls.
This document describes the external OpenAI API usage conventions, message schemas, and client interaction mechanics.

## The dependency

The `openai` Python package provides the client and the chat types:

- Import the client: `from openai import OpenAI`.
- Import the chat types used for requests and responses from `openai.types.chat` and its submodules:
  - `ChatCompletionSystemMessageParam`, `ChatCompletionUserMessageParam`,
    `ChatCompletionAssistantMessageParam`, `ChatCompletionToolMessageParam` —
    the four message roles accepted by the completions endpoint.
  - `ChatCompletionMessage` — the response message (content and/or tool calls).
  - `ChatCompletionMessageFunctionToolCall` — a tool call within a response.
  - `ChatCompletionToolParam` — a tool definition sent with the request.

## Client construction

A client is constructed from the agent loop configuration: the service endpoint, credentials, and request timeout.

```python
self._client = OpenAI(
    base_url=config.base_url,
    api_key=config.api_key,
    timeout=config.timeout,
)
```

The client is reused for every request in the run; it holds no conversation
state (each request carries the full conversation).

## Conversation messages

The loop maintains the conversation history as dictionary entries
(`{"role": ..., "content": ...}` and, for assistant messages, `tool_calls`).
Before each request they are converted to the OpenAI message-param types:

- A `user`, `system`, or `tool` entry becomes `{"role": ..., "content": ...}`
  (a `tool` entry also carries the `tool_call_id` of the call it answers).
- An `assistant` entry becomes `{"role": "assistant", "content": ...}` plus
  its `tool_calls` when present.
- Internal metadata fields (`_-`-prefixed) are stripped from each entry
  before it is sent, so nothing internal reaches the service.
- The system prompt, when provided, is prepended as a `system` message.

The OpenAI response message is converted back into a conversation dictionary entry, so the loop's conversation stays in its own format end to end.

## Tool definitions

The loop's tool definitions (`{"type": "function", "function": {"name", "description", "parameters"}}`) are passed through as `ChatCompletionToolParam` values. When any tools are provided, the request also sets `tool_choice = "auto"` so the model may call any of them. The tool definitions are re-fetched before each request, accommodating tool definitions that change during a run.

## The prompt call

Each request is a single chat-completion call with the full conversation, model, and processing parameters:

```python
response = self._client.chat.completions.create(
    messages=openai_messages,        # system (optional) + converted history
    model=config.model,
    temperature=config.temperature,
    max_tokens=config.max_tokens,    # optional; None leaves the service default
    tools=current_tools or None,     # optional; tool_choice="auto" when present
)
```

An exception from the call is an API failure: the loop returns a failure result with the error text logged; no state is changed. There are no retries.

## The response

The response is consumed from `response.choices[0]`:

- `choice.message` — a `ChatCompletionMessage`:
  - `message.content` — the model's text (may be None).
  - `message.tool_calls` — a list of `ChatCompletionMessageFunctionToolCall`
    (each with `id`, `type: "function"`, and `function.name` /
    `function.arguments` as a JSON string).
- `choice.finish_reason` — `"stop"` (natural stop), `"length"` (the model
  stopped at the generation limit — the truncation signal), or other
  service-specific reasons.
- `response.usage` — per-request token counts (`prompt_tokens`,
  `completion_tokens`, `total_tokens`), prompt token details
  (`prompt_tokens_details.cached_tokens`), and completion token details
  (`completion_tokens_details.reasoning_tokens`); non-cached prompt tokens
  are computed as `prompt_tokens - cached_tokens`. The loop tracks these
  and the cumulative totals along with elapsed request duration (measured
  via `time.perf_counter()`) for its logger events.

An empty `response.choices` is an API failure, as is a `"stop"` response with no content.

## Consuming the response

- **Tool calls:** each tool call is converted to the loop's internal tool call representation and executed through the tool executor; the results are appended as `tool` messages, and the loop continues with a follow-up request.
- **`finish_reason == "stop"`:** the model stopped without signaling termination. Since there is no free-text final answer, a termination reminder is injected and the loop continues; the run completes only via a termination tool or the iteration limit.
- **`finish_reason == "length"`:** the response was truncated at the generation limit. Any tool calls in the truncated response are dropped (never executed), the truncated content is appended, and the loop resumes with a follow-up request after appending the continuation prompt. A truncated response whose content is a single repeated character (a degenerate response) signals a loop failure instead of resuming.
- **Stubbing and prefix caching:** when a tool result's supersedes flag is set, the earlier result for the same file or tool command is replaced in place with a static stub, so the conversation prefix up to the most recent live result stays byte-identical across requests, preserving the model service's prefix caching.

## Notes and non-goals

- The service endpoint, model, and credentials come from configuration; nothing is hardcoded in the calling module.
- Retry behavior is unspecified: any API exception is an unhandled failure.
- The call shape above is the current usage and may evolve with SDK versions.
