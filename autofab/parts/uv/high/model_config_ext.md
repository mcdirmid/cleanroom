# model_config_ext external component

## Purpose

The model_config_ext external component defines the external declarative model configuration format, capability tier mappings, and token rate pricing schemas for Cleanroom language models.

Configuring language model execution and empirical benchmarking requires binding declarative model parameters, capability tiers, rate cards, and authentication settings to runtime client environments. The model_config_ext external component specifies the external configuration schema for declarative TOML model definition files and serialized configuration dictionaries, covering model identity, provider binding, capability tiers, token rate pricing, execution bounds, and agent preferences.

**Out of scope:** The model_config_ext external component does not transmit network requests, execute subagents, or enforce loop repetition; these are handled by other components.

## Grounding Gaps Covered

The model_config_ext component provides external serialization and discovery knowledge for declarative TOML model configuration files and build configuration dictionaries.

Grounding gaps covered include:

- Model configuration schema extraction: Extracts the model configuration schema from declarative TOML files and serialized JSON dictionaries, covering model identifiers, remote API base url endpoints, designated API key environment variables, request timeout durations, conversation turn limits, sampling temperatures, maximum token limits, capability tiers, tier labels, uncached input rates, cached input rates, output rates, quantization settings, default harnesses, batch sizes, conversation token bounds, test failure limits (max_failures), and unproductive turn limits.

- Configuration file discovery: Locates target configuration TOML and JSON files in repository roots, parent directories, build output trees, or the canonical user configuration directory.

- Text deserialization and credential binding: Decodes raw UTF-8 TOML or JSON text into structured in-memory records, validates configuration fields, extracts authentication credentials from designated environment variables or user credentials stores, falls back to ambient environment credentials or standard defaults when configuration files are absent, and reports parsing errors.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-19T18:45:00Z
LAST_CHANGED: 2026-10-19T18:45:00Z
CHANGE: Enhance model_config_ext with declarative TOML schema, capability tiers, and token rate pricing
-->
