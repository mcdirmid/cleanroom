# OpenAI Part (`update_with_ai/parts/openai`)

## Purpose

The **openai** part implements the model provider backend for OpenAI-compatible chat completion APIs (including OpenAI, OpenRouter, and local vLLM/Ollama endpoints).

Executing agent turns against remote language model endpoints requires converting internal conversation structures into provider-specific wire schemas, dispatching tool calls, capturing token metrics, handling rate limits and network timeouts, and recovering gracefully from generation limits. The openai part binds runtime configurations, formats requests according to OpenAI chat completion and tool-calling conventions, repairs truncated JSON payloads, and handles partial code edits by inserting continuation sentinels.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/openai/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/openai/high):

- [`openai_config.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/openai/high/openai_config.md): Manages runtime client settings for OpenAI-compatible endpoints, including model identifiers, API base URLs, API keys, request timeouts, temperatures, and maximum token budgets.
- [`openai_conversation_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/openai/high/openai_conversation_impl.md): Implements the `loop_conversation` interface for OpenAI chat completions. It formats internal messages into standard role sequences (`system`, `user`, `assistant` with tool calls, and `tool` result messages correlated by tool call ID), formats active reminders and notes in visible tool responses, and synthesizes assistant tool call stubs for unprompted startup tool executions.
- [`openai_driver_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/openai/high/openai_driver_impl.md): Implements the `loop_driver` interface. It dynamically rebuilds the tools payload on each turn from installed tools, dispatches model-invoked tool executions, and logs turn summaries to the runner logger (including turn ID, rounded token counts, cached token percentages, and execution status). When a completion is truncated by token exhaustion, it repairs arguments via `json_ext`; for truncated `replace_file_content` calls, it replaces incomplete lines with a `NotImplementedError` sentinel carrying a unique truncation ID and directs the model to resume targeting the sentinel.
- [`openai_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/openai/high/openai_ext.md): Defines the external wire protocol and network transport contracts for `/v1/chat/completions`. It handles HTTPS transport, bearer token authentication, HTTP error translation (401 auth, 429 rate limit, 5xx server errors, timeouts), and deserializes responses into tool calls and token consumption metrics (prompt, cached, completion tokens).

## How It Is Used by Other Parts

- **`loop`**: The `openai` part directly realizes the core abstractions of `loop`: `openai_driver_impl` implements `loop_driver`, and `openai_conversation_impl` implements `loop_conversation`.
- **`uv`**: `uv_model_config_impl` loads model configuration from build target manifests or environment variables and instantiates `openai_config`.
- **`systems`**: Aggregated into `uv_openai_loop_asm` to assemble the complete in-process Cleanroom loop runner.
- **`support` (`cleanroom_uv_runner`)**: When running `cleanroom-loop`, the runner executes with the OpenAI driver implementation wired into the loop cleaner.
