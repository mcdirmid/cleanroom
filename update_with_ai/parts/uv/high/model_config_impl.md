<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-17T12:00:00Z
LAST_CHANGED: 2026-10-17T12:00:00Z
CHANGE: align model_config_impl with app_info_ext and credentials fallback
CODE_HASH: 65e1dfd3eade
-->

# model_config_impl implementation component

imports: filesystem_ext, app_info_ext
implements: agent_config, dag_config, openai_config

## Purpose

The model_config_impl implementation component realizes model configuration loading from declarative TOML configuration files, user credentials stores, and process environment variables.

Executing autonomous agent workflows under the native UV runtime requires loading model parameters, traversal bounds, and authentication credentials without introducing dependencies on Bazel build machinery or compiled runfiles artifacts. Rigid coupling to build system manifests forces non-Bazel execution environments to duplicate build trees or simulate runfiles layouts. The model_config_impl implementation component resolves execution settings and model parameters from declarative TOML configuration files, user configuration directories, or process environment variables, decoupling agent execution from build system artifacts while preserving consistent model configuration.

**Out of scope:** The model_config_impl implementation component does not transmit network requests to model providers, format conversation history, track loop repetition, or manage filesystem storage; these are handled by other components.

**Delegated:** Reading declarative configuration files from host filesystem paths is delegated to filesystem_ext; application identity constants and user configuration path resolution are delegated to app_info_ext.

## Types and Behavior

The openai config, agent config, and dag config resolve the active model configuration name in precedence order from the `--config` command-line argument, the application model environment variable, the model configuration target environment variable, or the default selection declared in the workspace configuration file.

The openai config, agent config, and dag config load execution parameters and authentication credentials for language model agent runs from a declarative TOML configuration file, discovered hierarchically by searching candidate configuration filenames from the current directory upward, falling back to the user global configuration directory.

The openai config provides model execution settings including target model name, base url, timeout duration, sampling temperature, and token generation limits when constrained. Authentication credentials are bound from designated environment variables specified in the configuration, falling back to the user credentials file or ambient process environment variables.

The agent config provides conversational turn limits and operational policies for agent execution, defaulting operational policies to active unless explicitly disabled.

The dag config provides node visit bounds and batching limits for graph execution.

When the configuration file or named model entry is absent, execution parameters and authentication credentials fall back to ambient environment variables (such as `OPENAI_MODEL`, `OPENAI_BASE_URL`, and `OPENAI_API_KEY`), the user credentials store, and standard defaults.
