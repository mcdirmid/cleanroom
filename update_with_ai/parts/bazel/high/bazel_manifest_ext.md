<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-05T04:26:30Z
CHANGE: new file
CODE_HASH: ea7fb9830e22
-->

# bazel_manifest_ext external component

## Purpose

The bazel_manifest_ext external component defines the external JSON manifest schemas and file formats emitted by the update_with_ai Starlark build rules.

Autonomous task execution and graph loading require reading build metadata produced by the build system. The Starlark build rules emit structured JSON manifests capturing unit declarations, role specifications, and monolithic target definitions. The bazel_manifest_ext external component encapsulates the JSON formats and field structures for unit manifests, role manifests, and target manifests, providing external deserialization knowledge without coupling domain logic to Starlark rule internals.

**Out of scope:** The bazel_manifest_ext external component does not locate files across directory hierarchies, resolve dependency closures, or populate graph storage; these are handled by other components.

## Grounding Gaps Covered

The bazel_manifest_ext component provides external schema knowledge and deserialization mechanics for manifest JSON documents produced by the build system.

Grounding gaps covered include:

- Unit manifest deserialization: Parses unit manifest JSON files emitted by unit definition rules, exposing unit target labels, unit names, package directories, unit dependencies, and component type classifications.

- Role manifest deserialization: Parses role manifest JSON files emitted by role definition rules, exposing role target labels, role names, source path patterns, prompt templates, guide target labels, step mode permissions, node dependency lists, role dependency lists, star role dependency lists, silent cross-role dependency lists, feedback role dependency lists, active component types, and verification check templates.

- Target manifest deserialization: Parses monolithic target manifest JSON files, exposing target labels, names, prompts, tool labels, direct dependencies, silent dependencies, feedback dependencies, star dependencies, declared sources, templates, template parameters, guide labels, and verification checks.
