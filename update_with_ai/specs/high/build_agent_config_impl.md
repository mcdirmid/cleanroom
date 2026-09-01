# build_agent_config_impl

imports: agent_runner, build_agent_config
types from agent_runner: iteration limit
types from build_agent_config: agent configuration, config target, build agent config resolver
implements: build agent config resolver

## Behavior

- An *agent configuration* is resolved from a target module in the workspace runfiles tree or build output directory.
- Authentication credentials are read from designated environment variables specified in the *agent configuration*.
