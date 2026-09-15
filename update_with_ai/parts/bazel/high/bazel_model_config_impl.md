# bazel_model_config_impl implementation component

imports: model_config_ext
implements: agent_config, dag_config, openai_config

## Purpose

The bazel_model_config_impl implementation component realizes model configuration loading from target modules in the Bazel runfiles tree and process environment credentials.

Connecting declarative build targets to concrete language model parameters requires loading configuration modules from workspace build artifacts and binding runtime environment secrets without hardcoding credentials into source code. The bazel_model_config_impl implementation component resolves execution settings from a target module in the workspace runfiles tree or build output directory and binds authentication credentials from designated process environment variables.

**Out of scope:** The bazel_model_config_impl implementation component does not transmit network requests to model providers, format conversation history, or track loop repetition; these are handled by other components.

## Types and Behavior

The openai config, agent config, and dag config resolve the target configuration from the `MODEL_CONFIG_TARGET` environment variable, the `AGENT_CONFIG_TARGET` environment variable, or the `--config` command-line argument, defaulting to the standard `//model_configs:default` target.

The openai config, agent config, and dag config load execution parameters and authentication credentials for language model agent runs from the target module.

The openai config provides:

- The model name designating the target model.

- The base url designating the remote model API endpoint address.

- The api key providing authentication credentials from the designated environment variable, or ambient environment credentials.

- The timeout specifying the maximum request duration in seconds.

- The temperature specifying the sampling temperature for model requests.

- The max tokens bound resolved from the target module when token generation is constrained.

The agent config provides:

- The conversation limit bounding interaction turns.

- Whether the agent should use step mode to communicate a guide to the agent progressively.

- Whether the agent should perform startup reads to inspect declared files at session start.

- Whether the agent should inject followups to execute follow-up tool calls specified by tool responses.

- Whether editing tools should execute a follow-up read on modified files.

- Whether editing tools should produce delta output.

The dag config provides:

- The node visit limit bounding node visits during graph cleaning.

When the target module is absent, execution parameters and authentication credentials fall back to ambient environment variables and standard defaults.
