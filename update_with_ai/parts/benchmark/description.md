# Benchmark Part (`update_with_ai/parts/benchmark`)

## Purpose

The **benchmark** part implements the empirical model efficiency benchmarking harness, financial rate cards, multi-harness execution adapters, telemetry log harvesting, two-pass verification gates, and flight trace reporting for Cleanroom.

Empirical evaluation of neural code compilation requires standardized measurement of token efficiency, KV prompt-caching economics, step latency, and contract compliance across a multi-tier model spectrum:
- **Tier 1 (Free Local)**: Qwen 3.6 35B MoE and Qwen 27B Dense running via `omlx` on Apple Silicon.
- **Tier 2 (Budget Cloud)**: DeepSeek V4.1 Flash and Gemini 3.8 Flash.
- **Tier 3 (Mid-Tier Reasoning)**: OpenAI o3-mini and Claude 3.7 Sonnet evaluated on premier anchor targets.
- **Tier 4 (Frontier Ceilings)**: Gemini 4 Argon, Claude Opus 5.5, OpenAI gpt-6.1-sol, and Meta Muse.

The benchmark part standardizes on five core empirical measurements:
1. Non-cached inbound tokens ($T_{\text{in}}^{\text{uncached}}$)
2. Cached inbound tokens ($T_{\text{in}}^{\text{cached}}$)
3. Outbound tokens ($T_{\text{out}}$, including reasoning tokens)
4. Financial cost ($USD) computed from published rate cards
5. Time (step latencies and total wall-clock duration)

## Key Components & Specifications

- [`benchmark.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/benchmark/high/benchmark.md): Defines the core data models for model specifications, financial rate cards, benchmark unit catalog, flight telemetry, verification outcomes, and the `BenchmarkEvaluator` interface.
- [`benchmark_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/benchmark/high/benchmark_impl.md): Realizes flight execution, telemetry harvesting from runner logs, two-pass verification gates (Spec Lint $\to$ Pyright $\to$ Pytest $\to$ Mutmut), JSON flight traces, and markdown/LaTeX reporting.
