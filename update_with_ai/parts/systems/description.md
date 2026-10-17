# Systems Part (`update_with_ai/parts/systems`)

## Purpose

The **systems** part defines the top-level architectural system assemblies for Cleanroom. It aggregates constituent packages, subsystems, and implementations into cohesive, fully closed runtime systems ready for end-to-end execution.

Building an autonomous software engineering platform involves many independent parts: DAG traversal, in-band storage, LLM loops, sandboxed tools, workspace isolation, coverage evaluation, and multi-agent coordination. If entrypoints must wire these components together imperatively, initialization order bugs and missing singleton bindings arise. The systems part solves this by providing declarative, recursive root assemblies that close all interface dependencies across lifecycle tiers.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/systems/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/systems/high):

- [`cleanroom_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/systems/high/cleanroom_asm.md): The master root system assembly for Cleanroom.
  - Assembles: `control_asm`, `file_paths_impl`, `metadata_asm`, `workspace_cli_asm`, `openai_loop_asm`, and `workspace_asm`.
  - Implements and closes interface components across the application: agent session configuration, virtual file aliases, DAG storage and subgraphs, session control (scheduling, verification, attribution, submission), workspace provisioning, role management, file synchronization, statement coverage auditing, and workspace CLI tools.
  - Recursively registers every singleton service across the system and agent session lifecycle tiers.
- [`openai_loop_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/systems/high/openai_loop_asm.md): The in-process OpenAI loop root assembly.
  - Assembles: `dag_asm`, `loop_asm`, `conversation_impl`, `driver_impl`, `logger_impl`, `sandbox_asm`, `uv_asm`, `loop_impl`, and `model_config_impl`.
  - Provides complete interface closure for running single-node or subgraph cleaning loops directly with OpenAI-compatible language model endpoints.

## How It Is Used by Other Parts

The `systems` part sits at the top of the package dependency hierarchy:

- **Top-Level CLI (`support/lib/cleanroom_role_tool.py`)**: Initializes `cleanroom_asm` to run role commands (`clean`, `orchestrate`, `get-work`, `check-files`, `submit`, `blame`, `status`).
- **Loop Runner (`support/lib/cleanroom_uv_runner.py`)**: Initializes `cleanroom_asm` or `openai_loop_asm` when executing `cleanroom-loop` for in-process cleaning passes.
- It acts as the integration test and verification boundary ensuring all Cleanroom interface contracts have matching, properly wired implementation components.
