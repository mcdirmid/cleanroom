# agent_loop_config

imports: agent_loop (termination reminder generator, run)
terms (from agent_loop): run, continuation prompt
terms (owned): agent-loop configuration

## Purpose

Holds the agent-loop configuration: the complete set of connection and processing parameters supplied when an agent loop is constructed, exchanged between the components that produce it and the component that consumes it. The type lives in its own module so a producing component can name it without importing an implementation.

## Terms

- Agent-loop configuration: the connection and processing parameters of an agent run — the service endpoint, credentials, model, iteration limit, sampling temperature, request timeout, token limit, an optional termination reminder generator, and an optional continuation prompt.

## Contract

**Inputs**

- Per call: the connection and processing parameters of the configuration.

**Operations**

- Construct an agent-loop configuration.

**Guarantees**

- Construction provides an agent-loop configuration whose parameters are exactly the supplied values.
- An agent-loop configuration is consumed when an agent loop is constructed.
- Parameter values pass through unchanged from construction to consumption.

**Assumptions**

- The consuming component is constructed with the configuration.

## Non-concerns

- The meaning of individual parameters (temperature, timeout, token limit): they pass through unchanged to the agent loop construction.
- The selection and loading of configuration values (Bazel config targets, the environment): the concern of the producing component, not this module.
