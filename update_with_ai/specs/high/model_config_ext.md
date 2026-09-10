# model_config_ext external component

## Purpose

The model_config_ext external component defines the external build target model configuration JSON dictionary format emitted by the model_config Starlark build rule.

Configuring language model execution requires binding declarative build target parameters to runtime client settings. The model_config_ext external component specifies the external configuration dictionary emitted by the model_config rule, defining target labels, model identifiers, API endpoint URLs, designated credential environment variable names, request timeouts, iteration limits, temperature values, token limits, and agent execution preferences.

**Out of scope:** The model_config_ext external component does not transmit network requests, configure sandboxes, or enforce loop repetition; these are handled by other components.

## Grounding Gaps Covered

The model_config_ext component provides external serialization and discovery knowledge for model configuration files emitted by model_config.bzl:

- Model configuration JSON extraction: Extracts the model configuration dictionary schema emitted by model_config.bzl, defining mappings for target label, target name, model identifier, remote API base url endpoint, designated API key environment variable name, request timeout duration, maximum conversation turn limit, temperature, maximum token limit, guide step mode setting, and startup file inspection setting.

- Configuration file discovery: Locates target configuration JSON files in the workspace Bazel runfiles tree, build output directory, or directory adjacent to the running executable based on the parsed target package and target name.

- JSON text deserialization and credential binding: Decodes raw UTF-8 JSON text documents into structured in-memory records, validates configuration fields, extracts authentication credentials from the designated process environment variable, falls back to ambient environment credentials or standard defaults when configuration files are absent, and handles JSON parsing errors.
