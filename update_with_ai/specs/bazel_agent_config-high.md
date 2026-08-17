# bazel_agent_config

imports: agent_loop (agent-loop configuration)
terms (owned): agent configuration, config target, API key

## Purpose

Loads declarative agent/model configurations declared as Bazel targets (see
update_with_ai/agent_config.bzl) and combines them with an API key resolved
from the environment, providing the complete agent-loop configuration to the
caller. The component is deliberately Bazel-shaped: configs live in the Bazel
workspace, so selection and loading are expressed in Bazel terms (config
targets, runfiles, bazel-bin).

## Owned definitions

- Agent configuration: the full set of agent/model parameters — model
  identifier, base URL, iteration limit, temperature, timeout, and token
  limit — excluding the API key. An agent configuration may name the exact
  environment variable holding its API key (an API-key environment variable)
  and is identified by a config target.
- Config target: the Bazel label of an agent_config target whose generated
  module holds the agent configuration, in canonical form //pkg:name.
- API key: a secret credential for the language model service. An API key is
  never part of an agent configuration or a config target; it is provided by
  the caller through the environment.

## Observable dataflow

- Inputs: a config target (optional), a workspace root (optional), and the
  caller's environment (API key variables).
- Outputs: an agent-loop configuration combining the selected agent
  configuration with the resolved API key.
- Config-target selection: the explicit config target, when provided, wins;
  otherwise an environment variable selects the config target; otherwise the
  default config target //agent_configs:default applies.
- API-key resolution: an agent configuration may name the exact environment
  variable holding its API key; when it does, that variable alone supplies
  the key. When it does not, the plain AGENT_API_KEY variable supplies the
  key; absence of a key is an unexpected failure.
- The generated module for a config target is located in the runfiles tree
  first, then under bazel-bin in the workspace; when neither holds it, the
  failure is unexpected and is signaled with actionable guidance.

## Contract

**The component assumes:**

- A config target, when provided, is a canonical main-repo Bazel label.
- The config target's generated module exists in the runfiles tree or in
  bazel-bin under the workspace root.
- The environment provides an API key for the configuration: the pinned
  variable (when one is named) or AGENT_API_KEY.

**The component guarantees:**

- Provides an agent-loop configuration whose parameters match the selected
  agent configuration exactly, with the API key resolved from the
  environment.
- No API key is ever part of an agent configuration or a config target; the
  API key exists only in the resolved agent-loop configuration.
- When an agent configuration names an API-key environment variable, that
  variable alone supplies the API key; AGENT_API_KEY does not apply.
- Expected failures are provided as values; this component has none — every
  failure of this component is an unexpected failure.

**Unexpected failures (signaled as exceptions):**

- Config target's generated module missing: the config target is invalid or
  was not built, signaled with guidance to build it (ConfigNotFoundError).
- API key missing: the pinned API-key environment variable is unset (when
  the configuration names one), or AGENT_API_KEY is unset (when it does
  not), signaled with the exact variable names (ApiKeyNotFoundError).
- Config target label malformed: not a canonical main-repo label
  (ConfigNotFoundError).

## Non-concerns

- Where config targets are declared (which Bazel package): any package may
  declare agent_config targets; the convention is agent_configs/BUILD.bazel.
- How agent configurations are stored on disk (generated module format): the
  generated module and JSON forms are implementation-specific.
- The meaning of individual parameters (temperature, timeout, token limit):
  those parameters pass through unchanged to the agent-loop configuration.
