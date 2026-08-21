# bazel_agent_config

imports: agent_loop (agent-loop configuration)
terms (owned): agent configuration, config target, API key

## Purpose

Loads declarative agent/model configurations declared as Bazel targets (see update_with_ai/agent_config.bzl) and combines them with an API key resolved from the environment, providing the complete agent-loop configuration to the caller. The component is deliberately Bazel-shaped: configs live in the Bazel workspace, so selection and loading are expressed in Bazel terms (config targets, runfiles, bazel-bin).

## Terms

- Agent configuration: the full set of agent/model parameters — model identifier, base URL, iteration limit, temperature, timeout, and token limit — excluding the API key. An agent configuration may name the exact environment variable holding its API key (an API-key environment variable) and is identified by a config target.
- Config target: the Bazel label of an agent_config target whose generated module holds the agent configuration, in canonical form //pkg:name.
- API key: a secret credential for the language model service. An API key is never part of an agent configuration or a config target; it is provided by the caller through the environment.

## Contract

**Inputs**

- A config target (optional; per call).
- A workspace root (optional).
- The caller's environment (API key variables).

**Operations**

- Select an agent configuration by providing a config target label (via a command-line flag, an environment variable, or a build setting), or rely on the default configuration when none is provided.

**Guarantees**

- Provides an agent-loop configuration whose parameters match the selected agent configuration exactly, with the API key resolved from the environment.
- Config-target selection: the explicit config target, when provided, wins; otherwise an environment variable selects the config target; otherwise the default config target //agent_configs:default applies.
- No API key is ever part of an agent configuration or a config target; the API key exists only in the resolved agent-loop configuration.
- When an agent configuration names an API-key environment variable, that variable alone supplies the API key; AGENT_API_KEY does not apply. When it names none, the plain AGENT_API_KEY variable supplies the key.
- Expected failures are provided as values; this component has none — every failure of this component is an unexpected failure.

**Assumptions**

- A config target, when provided, is a canonical main-repo Bazel label.
- The config target's generated module exists in the runfiles tree or in bazel-bin under the workspace root.
- The environment provides an API key for the configuration: the pinned variable (when one is named) or AGENT_API_KEY.

**Unexpected failures**

- Config target's generated module missing: the config target is invalid or was not built, signaled with guidance to build it (ConfigNotFoundError).
- API key missing: the pinned API-key environment variable is unset (when the configuration names one), or AGENT_API_KEY is unset (when it does not), signaled with the exact variable names (ApiKeyNotFoundError).
- Config target label malformed: not a canonical main-repo label (ConfigNotFoundError).

## Non-concerns

- Where config targets are declared (which Bazel package): any package may declare agent_config targets; the convention is agent_configs/BUILD.bazel.
- How agent configurations are stored on disk (generated module format): the generated module and JSON forms are implementation-specific.
- The meaning of individual parameters (temperature, timeout, token limit): those parameters pass through unchanged to the agent-loop configuration.
