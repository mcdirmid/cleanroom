# Antigravity Part (`update_with_ai/parts/antigravity`)

## Purpose

The **antigravity** part provides the integration bridge between Cleanroom and Google Antigravity (AGY). It enables Cleanroom to execute autonomous multi-agent pipelines and single-agent turns natively within Google Antigravity workspaces.

Autonomous agents operating inside complex coding projects risk inspecting un-blinded counterpart implementations, violating role boundaries, or running unmonitored. The antigravity part formalizes workspace isolation, non-blocking turn execution, transcript event parsing, token telemetry tracking, and coordinator directives specifically tailored to Antigravity's agent architecture, subagent invocation protocols, and execution logs.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/antigravity/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/antigravity/high):

- [`antigravity_coordinator.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/antigravity/high/antigravity_coordinator.md) & [`antigravity_coordinator_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/antigravity/high/antigravity_coordinator_impl.md): Defines the autonomous coordinator protocol for Antigravity. It formats coordinator directives (`AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE`), synthesizes coordinator skill definitions (`cleanroom-coordinate`), formats subagent task prompts, monitors multi-agent wave execution, and aggregates turn outcomes across isolated role workspaces.
- [`antigravity_harness.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/antigravity/high/antigravity_harness.md) & [`antigravity_harness_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/antigravity/high/antigravity_harness_impl.md): Implements the Cleanroom harness adapter for Google Antigravity. It dispatches role directives to isolated role workspaces, polls child processes non-blockingly, parses JSONL event streams from Antigravity execution transcripts (`.system_generated/logs/transcript.jsonl`), extracts prompt/cached/completion token usage, and calculates monetary costs using Gemini model rate cards (e.g. Gemini Flash and Gemini Pro).
- [`antigravity_workspace.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/antigravity/high/antigravity_workspace.md): Configures boundary constraints and isolation rules within provisioned role workspaces. It generates Antigravity markdown rule files (`.agents/rules/<rule_name>.md`) and role documentation (`AGENTS.md`) instructing agents never to access or modify paths outside their designated role workspace root, and produces a confinement report documenting boundary status.
- [`antigravity_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/antigravity/high/antigravity_ext.md): Specifies external platform format schemas for Google Antigravity, including workspace rule Markdown syntax, the JSON payload schema for `invoke_subagent`, and the JSONL event record schema in transcript logs.
- [`antigravity_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/antigravity/high/antigravity_asm.md): Assembles the Antigravity harness adapter, telemetry parser, coordinator, and workspace configurer into an operational service registered with the Cleanroom harness registry.

## How It Is Used by Other Parts

- **`subagent`**: Installs the Antigravity harness adapter into `subagent_harness`'s central `HarnessRegistry`. When the orchestrator selects the `antigravity` harness (`--harness antigravity`), the subagent coordinator resolves this adapter to dispatch turns and harvest token metrics and results.
- **`workspace`**: Collaborates with `antigravity_workspace` during role workspace provisioning so that newly created role directories receive Antigravity-specific rule files (`.agents/rules/*.md`) and role guidance before subagents are launched.
- **Top-Level CLI & Support (`cleanroom_role_tool`)**: The `cleanroom orchestrate` command detects when it is running under Antigravity or targeting `--harness antigravity`, generating the coordination directive to trigger the installed `cleanroom_coordinator` agent.
