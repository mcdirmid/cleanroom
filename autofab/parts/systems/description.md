# Systems Part (`autofab/parts/systems`)

## Purpose

The **systems** part defines the top-level architectural system assemblies for Autofab. It aggregates constituent packages, subsystems, and implementations into cohesive, fully closed runtime systems ready for end-to-end execution.

Building an autonomous software engineering platform involves many independent parts: DAG traversal, in-band storage, LLM loops, sandboxed tools, workspace isolation, coverage evaluation, and multi-agent coordination. If entrypoints must wire these components together imperatively, initialization order bugs and missing singleton bindings arise. The systems part solves this by providing declarative, recursive root assemblies that close all interface dependencies across lifecycle tiers.

## Key Components & Specifications

According to the high-level specifications in [`autofab/parts/systems/high/`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/systems/high):

- [`autofab_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/systems/high/autofab_asm.md): The master root system assembly for Autofab.
  - Assembles: `control_asm`, `file_paths_impl`, `metadata_asm`, `workspace_cli_asm`, `dag_asm`, `uv_asm`, and `workspace_asm`.
  - Implements and closes interface components across the application: agent session configuration, virtual file aliases, DAG storage and subgraphs, session control (scheduling, verification, attribution, submission), workspace provisioning, role management, file synchronization, statement coverage auditing, and workspace CLI tools.
  - Recursively registers every singleton service across the system and agent session lifecycle tiers.

## How It Is Used by Other Parts

The `systems` part sits at the top of the package dependency hierarchy:

- **Top-Level CLI (`support/lib/autofab_role_tool.py`)**: Initializes `autofab_asm` to run role commands (`clean`, `orchestrate`, `get-work`, `check-files`, `submit`, `blame`, `status`).
- It acts as the integration test and verification boundary ensuring all Autofab interface contracts have matching, properly wired implementation components.
