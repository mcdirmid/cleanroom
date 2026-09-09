# bazel_model_config_impl implementation component

implements: model_config

## Purpose

The bazel_model_config_impl implementation component realizes model configuration loading from target modules in the Bazel runfiles tree and process environment credentials.

Connecting declarative build targets to concrete language model parameters requires loading configuration modules from workspace build artifacts and binding runtime environment secrets without hardcoding credentials into source code. The bazel_model_config_impl implementation component resolves execution settings from a target module in the workspace runfiles tree or build output directory and binds authentication credentials from designated process environment variables.

**Out of scope:** The bazel_model_config_impl implementation component does not transmit network requests to model providers, format conversation history, or track loop repetition; these are handled by other components.

## Types and Behavior

The model config resolves the target configuration from the `MODEL_CONFIG_TARGET` environment variable or the `--config` command-line argument, defaulting to the standard `//agent_configs:default` target.

The model config loads execution parameters and authentication credentials for language model agent runs from the target module located in the workspace runfiles tree or build output directory.

When loading the model config, authentication credentials are read from designated environment variables specified in the target configuration, providing the model name, base url, api key, timeout, conversation limit, whether the agent should use step mode to communicate a guide to the agent progressively, and whether the agent should perform startup reads to inspect declared files at session start.
