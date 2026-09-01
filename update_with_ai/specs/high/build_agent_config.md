# build_agent_config

imports: agent_runner
types from agent_runner: iteration limit

## Purpose

Resolves declarative agent configuration targets and environment credentials into executable model settings.

Agent workflows require flexible selection of model parameters and secret API credentials across development and production runs. Build agent config loads declarative target configurations from the workspace and binds them with API keys resolved from the environment, providing complete model settings.

## Types

- An *agent configuration* is a set of model parameters, authentication environment variables, timeouts, and *iteration limits* for an agent run
- A *config target* is an identifier selecting an *agent configuration*
- A *build agent config resolver* is a resolver that resolves an *agent configuration* from a *config target*

## Behavior

- An *agent configuration* defines model identifiers, authentication environment variables, timeouts, and *iteration limits*.
- A *config target* selects an *agent configuration* from workspace targets.
- A *build agent config resolver* resolves an *agent configuration* from a *config target*.
- Resolving an *agent configuration* binds authentication credentials from the process environment.
