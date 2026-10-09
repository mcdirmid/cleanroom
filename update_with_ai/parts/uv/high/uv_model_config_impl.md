<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: 61a3f04b613e
-->

# uv_model_config_impl implementation component

imports: filesystem_ext
implements: agent_config, dag_config, openai_config

## Purpose

The uv_model_config_impl implementation component realizes model configuration loading from declarative TOML configuration files and process environment credentials.

Executing autonomous agent workflows under the native UV runtime requires loading model parameters, traversal bounds, and authentication credentials without introducing dependencies on Bazel build machinery or compiled runfiles artifacts. Rigid coupling to build system manifests forces non-Bazel execution environments to duplicate build trees or simulate runfiles layouts. The uv_model_config_impl implementation component resolves execution settings and model parameters from declarative TOML configuration files or process environment variables, decoupling agent execution from build system artifacts while preserving consistent model configuration.

**Out of scope:** The uv_model_config_impl implementation component does not transmit network requests to model providers, format conversation history, track loop repetition, or manage filesystem storage; these are handled by other components.

**Delegated:** Reading declarative configuration files from host filesystem paths is delegated to filesystem_ext.

## Types and Behavior

The openai config, agent config, and dag config resolve the active model configuration name from the `--config` command-line argument, the `CLEANROOM_MODEL` environment variable, the `MODEL_CONFIG_TARGET` environment variable, or the default selection declared in the workspace configuration file.

The openai config, agent config, and dag config load execution parameters and authentication credentials for language model agent runs from a declarative TOML configuration file in the repository root (such as `model_configs.toml`) or user configuration directory.

The openai config provides model execution settings including target model name, base url, timeout duration, sampling temperature, and optional token generation limits. Authentication credentials are bound from designated environment variables specified in the configuration, defaulting to ambient process environment variables.

The agent config provides conversational turn limits and operational policies for agent execution.

The dag config provides node visit bounds and batching limits for graph execution.

When the configuration file or named model entry is absent, execution parameters and authentication credentials fall back to ambient environment variables (such as `OPENAI_MODEL`, `OPENAI_BASE_URL`, and `OPENAI_API_KEY`) and standard defaults.
