# antigravity_telemetry interface component

## Purpose

The antigravity_telemetry interface component defines token usage analytics, prompt cache efficiency measurement, and API cost calculation for Antigravity conversations.

Accurately evaluating agent efficiency and preventing context window overflows requires extracting token metrics directly from conversation databases and transcripts. The antigravity_telemetry interface component defines data types and services for measuring turn counts, evaluating prompt cache hit rates, computing API dollar costs, and enforcing context caps.

**Out of scope:** The antigravity_telemetry interface component does not orchestrate DAG nodes, modify source files, or execute sandbox commands; these are handled by other components.

## Types and Behavior

A *conversation stats* record encapsulates token usage metrics for a subagent conversation, exposing an *agent name*, a *turns* count, a *context tokens* size, a *fresh input tokens* count, a *cached input tokens* count, a *cache hit percentage*, an *output tokens* count, and an *estimated cost dollars*.

The *antigravity telemetry* is a system service that extracts token statistics and computes usage metrics across conversations. The antigravity telemetry provides:

- A *get conversation stats* operation that extracts a conversation stats record for a conversation *identifier*.

- A *get coordinator run stats* operation that extracts conversation stats across all worker conversations spawned by a coordinator *identifier*.

- A *check context cap* operation that evaluates whether the context tokens of a conversation identifier exceed a specified *threshold*.

- A *render stats table* operation that formats a collection of conversation stats records into a markdown table.

- A *calculate cost* operation that computes estimated cost dollars from fresh input tokens, cached input tokens, output tokens, and a pricing *model*.
