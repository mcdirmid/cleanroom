# UV Part (`update_with_ai/parts/uv`)

## Purpose

The **uv** part implements Python UV target manifest loading, target label canonicalization, build rule metadata parsing, and target-level session configuration for Cleanroom.

Cleanroom projects use UV-compatible build declarations and JSON target manifests to define source files, starter templates, direct dependencies, transitive star-role contracts, feedback blame targets, verification commands, and step guides. The uv part loads and validates these declarative manifests, converts diverse user-supplied target strings into canonical DAG nodes, configures active agent sessions from manifest metadata, and provides the entrypoint to run the Cleanroom loop over UV targets.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/uv/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high):

- [`target.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high/target.md) & [`target_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high/target_impl.md): Normalizes raw target identifier strings (e.g. package-qualified labels `//pkg/unit#role`, shorthand colon syntax, relative file paths) into canonical DAG nodes, strips repository prefixes, and resolves the package directory locations against workspace roots.
- [`target_labels_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high/target_labels_ext.md): Specifies the external grammar and syntax rules for Cleanroom target labels, validating package segments, unit names, and role qualifiers.
- [`manifest_loader.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high/manifest_loader.md) & [`manifest_loader_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high/manifest_loader_impl.md): Discovers and deserializes target JSON manifests from workspace runfiles, build outputs, or adjacent directories. Extracts declared source files, initial templates, direct dependencies, transitive star dependencies, feedback blame dependencies, verification commands, and success messages.
- [`manifest_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high/manifest_ext.md): Defines the external JSON schema for UV target manifests emitted by build rules.
- [`node_config_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high/node_config_impl.md): Realizes `node_config` from loaded target manifests. It maps manifest source files to session read-write files, direct and transitive star dependencies to read-only files (excluding silent dependencies and read-write files), feedback dependencies to blame targets, declared verification commands to subprocess checks with dynamically configured `PYTHONPATH`, and parses markdown guide targets into step sections and failure instructions.
- [`model_config_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high/model_config_impl.md): Loads language model configurations from target metadata or ambient environment variables, instantiating runtime model configurations for the session.
- [`loop_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high/loop_impl.md): Realizes the executable loop runner that binds target manifests and session configurations to the in-process cleanroom loop cleaner.
- [`model_config_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high/model_config_ext.md): Defines the external JSON dictionary schema for model configurations emitted by build rules, specifying target labels, model identifiers, API endpoint URLs, credential environment variable names, timeouts, turn limits, sampling temperatures, token bounds, and feature toggles.
- [`uv_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/uv/high/uv_asm.md): Assembles the UV target normalizer, manifest loader, node configurer, and loop runner into an operational subsystem.

## How It Is Used by Other Parts

- **`systems`**: Aggregated into `openai_loop_asm` and `cleanroom_asm` to supply manifest loading, target resolution, and node configuration to the root system assemblies.
- **`agent`**: `node_config_impl` provides the concrete implementation of `node_config` and `file_alias` when executing in UV/Python environments.
- **`loop` & `openai`**: `model_config_impl` configures the `openai_config` and session policies used by `driver` and `driver_impl`.
- **Support (`cleanroom_uv_runner.py`)**: Uses `uv` to normalize CLI target labels, load manifests, configure sessions, and execute cleaning loops via `loop_impl`.
