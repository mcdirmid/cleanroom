# json_manifest_ext external component

## Purpose

The json_manifest_ext external component defines the external build target manifest JSON dictionary format emitted by the update_with_ai Starlark build rule.

Target execution requires reading build metadata emitted by the build system. The json_manifest_ext external component specifies the external dictionary fields produced by the update_with_ai rule in the build configuration, capturing target labels, dependency relationships, prompt instructions, declared source files, templates, template parameters, guides, and verification commands.

**Out of scope:** The json_manifest_ext external component does not resolve package directories, construct dependency graphs, or configure sandboxes; these are handled by other components.

## Grounding Gaps Covered

The json_manifest_ext component provides external serialization knowledge for parsing target manifest files emitted by update_with_ai.bzl:

- Build manifest JSON extraction: Extracts the build manifest schema directly from update_with_ai.bzl, defining dictionary mappings for target label, target name, prompt text, tool labels, direct dependencies, silent dependencies, feedback dependencies, star dependencies, declared primary source path, template path, template parameters, guide target label, allowed step mode setting, silent source paths, verification command, and dependency file paths.

- JSON text deserialization: Decodes raw UTF-8 JSON text documents into structured in-memory records, validates required manifest fields, provides default collections for omitted dependency collections, and handles JSON parsing errors and structural malformations.

- Target and path string extraction: Extracts raw Bazel target coordinate strings and package-relative source file path strings from manifest fields for consumption by graph storage and loader services.
