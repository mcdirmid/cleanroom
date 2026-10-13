<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Group the configuration field inventory by concern and name the serialized schema
CODE_HASH: dd9f70cef89c
-->

# model_config_ext external component

## Purpose

The model_config_ext external component defines the external build target model configuration JSON dictionary format emitted by the model_config Starlark build rule.

Configuring language model execution requires binding declarative build target parameters to runtime client settings. The model_config_ext external component specifies the external configuration dictionary emitted by the model_config rule, covering build target identity, model endpoint and credential binding, request limits and sampling settings, and agent execution preferences.

**Out of scope:** The model_config_ext external component does not transmit network requests, configure sandboxes, or enforce loop repetition; these are handled by other components.

## Grounding Gaps Covered

The model_config_ext component provides external serialization and discovery knowledge for model configuration files emitted by model_config.bzl.

Grounding gaps covered include:

- Model configuration JSON extraction: Extracts the model configuration dictionary schema emitted by model_config.bzl, covering target label and target name, model identifier, remote API base url endpoint, designated API key environment variable name, request timeout duration, maximum conversation turn limit, temperature, maximum token limit, and the guide step mode, startup file inspection, follow-up tool call injection, node visit limit, and batch size settings.

- Configuration file discovery: Locates target configuration JSON files in the workspace runfiles tree, the build output directory, or the directory adjacent to the running executable, resolved from the target package and target name.

- JSON text deserialization and credential binding: Decodes raw UTF-8 JSON text documents into structured in-memory records, validates configuration fields, extracts authentication credentials from the designated process environment variable, falls back to ambient environment credentials or standard defaults when no configuration file is present, and reports JSON parsing errors.
