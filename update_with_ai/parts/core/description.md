# Core Part (`update_with_ai/parts/core`)

## Purpose

The **core** part provides the fundamental domain utilities, filesystem primitives, external protocol knowledge, data repair routines, and observable logging infrastructure utilized across all Cleanroom packages.

Operating an autonomous pair-programming framework requires strict guarantees on path traversal safety, deterministic topological ordering, robust recovery from truncated language model JSON payloads, and unbuffered transcript persistence. The core part encapsulates these common capabilities into reusable, self-contained components so higher-level subsystems build upon standardized algorithms rather than ad-hoc implementations.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/core/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/high):

- [`file_paths.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/high/file_paths.md) & [`file_paths_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/high/file_paths_impl.md): Defines canonical `WorkspacePath` and relative path abstractions. It enforces path normalization and prevents path traversal attacks (such as directory walking using `..`), ensuring all file operations remain strictly anchored within designated workspace roots.
- [`topological_order_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/high/topological_order_ext.md): Formalizes deterministic, dependency-first topological sorting over declared graph items. It defines total-order linear extensions, lexical tie-breaking, transitive closure resolution, and safe cycle handling (cycles are broken deterministically so every item is emitted once without hanging).
- [`json_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/high/json_ext.md): Implements deterministic JSON serialization and robust token salvage for language model completions. When a streaming or generation-limited LLM response is truncated mid-stream, `json_ext` salvages valid data by balancing unclosed string quotes, resolving dangling escapes, stripping trailing commas, and closing unclosed braces/brackets in correct reverse nesting order.
- [`cleanroom_files_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/high/cleanroom_files_ext.md): Specifies the external structural conventions of Cleanroom repositories, including package directory patterns (`parts/`), role directory mappings (`high/`, `low/`, `lib/`, `tests/`, `guides/`), and component naming schemes (`*_impl.md`, `*_ext.md`).
- [`commonmark_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/high/commonmark_ext.md): Provides CommonMark-compliant markdown parsing and extraction knowledge for extracting sections, code blocks, lists, and metadata comments.
- [`filesystem_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/core/high/filesystem_ext.md): Encapsulates atomic filesystem operations, directory creation, safe file reading, and durable file writing.

## How It Is Used by Other Parts

As the foundation library of Cleanroom, `core` is imported and leveraged by nearly every part:

- **`agent`**: Uses `file_paths` to anchor file aliases to workspace roots.
- **`control`**: Uses `file_paths` and `topological_order_ext` to compute role tier depths and schedule task queues deterministically.
- **`dag`**: Uses `topological_order_ext` to index subgraphs in dependency-first order.
- **`metadata`**: Uses `file_paths`, `cleanroom_files_ext`, and `filesystem_ext` to resolve declared source files, locate metadata comment blocks, and write updated files atomically.
- **`sandbox`**: Uses `file_paths`, `filesystem_ext`, and `commonmark_ext` to load step guides and format templates.
- **`loop` & `openai`**: Use `json_ext` to salvage truncated model tool calls.
- **`workspace_cli`**: Uses `cleanroom_files_ext` and `file_paths` to resolve workspace paths and file conventions.
- **`uv`**: Uses `cleanroom_files_ext`, `file_paths`, and `topological_order_ext` to parse target labels, resolve package directories, and order manifest dependencies.
- **`workspace`**: Uses `file_paths`, `filesystem_ext`, and `cleanroom_files_ext` during role workspace provisioning, scaffolding, and file synchronization.
- **`systems`**: Aggregates `core` services (`file_paths_impl`, etc.) into the master assemblies.
