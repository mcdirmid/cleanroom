<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:20:05Z
CHANGE: Author uv uv_model_config_impl concrete scenarios
CODE_HASH: 9136dedfb19b
-->

# Concrete scenarios for `uv_model_config_impl` (implementation)

Scenarios 1 through 18 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 19 through
23 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

The scenarios of the `agent_config`, `dag_config` and `openai_config` interfaces the component
implements come in that order. The `openai_config` interface has no written scenario file yet, so
its scenarios were derived from its high specification.

### Scenario 1 — Reading the execution parameters

Given: the active agent session configuration supplies a conversation limit of 12, a supersede arg
keep limit of 64, and the follow-up injection, step mode, startup read, and delta output policies
active.

1. The caller reads the conversation limit of the agent config. Observed: 12. Realized by: the
component's own conversational turn limits, which the component resolves from the model
configuration the caller's session configuration names through `filesystem_ext`.

2. The caller reads the supersede arg keep limit of the agent config.
   Observed: 64, so at most the 64 trailing characters of a superseded string argument are retained
   as a recognizable hint.
   Realized by: the component's own supersede arg keep limit, which the component resolves from the
   model configuration the caller's session configuration names through `filesystem_ext`.

3. The caller reads the supersede arg keep limit a second time.
   Observed: 64 again, unchanged by the preceding read.
   Realized by: the component's own supersede arg keep limit, which the component reads without
   re-resolving the model configuration.

### Scenario 2 — Reading the operational policies

Given: the same agent session configuration, in which the follow-up injection, step mode, startup
read, and delta output policies are all active.

1. The caller reads the follow-up injection, step mode, startup read, and delta output policies.
Observed: each of the four policies is reported active, and no policy is reported inactive. Realized
by: the component's own operational policies, which the component resolves from the named model
entry of the declarative TOML configuration file through `filesystem_ext`.

2. The caller reads the delta output policy of a second agent config whose session configuration
   supplies only the startup read policy.
   Observed: delta output is inactive, step mode is inactive, follow-up injection is inactive, and
   startup read is active; the reads report the remaining policies without failing.
   Realized by: the component's own operational policies, which fall back to the standard defaults
   when the configuration file or named model entry is absent.

### Scenario 3 — Stable parameters across repeated reads

Given: an agent config whose session configuration supplies a conversation limit of 3, a supersede
arg keep limit of 8, and the step mode policy active.

1. The caller reads all three values twice in succession.
   Observed: both reads report 3, 8, and an active step mode policy, and the reads alter neither
   limit nor the policy.
   Realized by: the component's own loaded execution parameters, which the component reads without
   re-reading the declarative TOML configuration file through `filesystem_ext`.

### Scenario 4 — Parameters recovered from the same session configuration

Given: the same session configuration, supplying a conversation limit of 7, a supersede arg keep
limit of 16, and the delta output policy active, is used to build a fresh agent config.

1. The caller reads the conversation limit of the fresh agent config.
   Observed: 7.
   Realized by: the component's own conversational turn limits, resolved again from the model
   configuration the session configuration names through `filesystem_ext`.

2. The caller reads the supersede arg keep limit of the fresh agent config.
   Observed: 16.
   Realized by: the component's own supersede arg keep limit, resolved again from the model
   configuration the session configuration names through `filesystem_ext`.

3. The caller reads the delta output policy of the fresh agent config.
   Observed: active, matching the policy the session configuration supplied.
   Realized by: the component's own operational policies, resolved again from the model
   configuration the session configuration names through `filesystem_ext`.

### Scenario 5 — No ambient agent config

Given: no ambient agent config is active for the caller.

1. The caller reads the conversation limit.
   Observed: the read fails explicitly, and no conversation limit is reported.
   Realized by: the component's own absence of a loaded model configuration, which the component
   reports rather than substituting a default limit.

2. The caller reads the supersede arg keep limit.
   Observed: the read fails explicitly, and no limit is reported.
   Realized by: the component's own absence of a loaded model configuration, which the component
   reports rather than substituting a default limit.

3. The caller reads the follow-up injection policy.
   Observed: the read fails explicitly, and the policy is reported as neither active nor inactive.
   Realized by: the component's own absence of a loaded model configuration, which the component
   reports rather than substituting a default policy.

### Scenario 6 — Following up an injected tool call

Given: the follow-up injection policy is active, and the last tool response designates a follow-up
tool call naming the tool `read_file` for the file `widget/notes/draft.md`.

1. The caller reads the follow-up injection policy of the agent config and the follow-up tool call
   of that tool response.
   Observed: the policy is active, and the designated call names `read_file` with the argument
   `widget/notes/draft.md`, so the agent executes it.
   Realized by: the component's own operational policies, whose follow-up injection flag the
   component resolves from the declarative TOML configuration file through `filesystem_ext`.

2. The caller reads the same tool response against a config whose follow-up injection policy is
   inactive.
   Observed: the policy is inactive, and although the response still designates the `read_file`
   follow-up call, the agent executes no tool call in response to it.
   Realized by: the component's own operational policies, whose inactive follow-up injection flag
   falls back to the standard defaults.

### Scenario 7 — Receiving a guide progressively

Given: the step mode policy is active, and the session guide holds the step section numbered 1
titled `Inspect the widget contract` and the step section numbered 2 titled
`Clean the widget source`.

1. The caller reads the step mode policy of the agent config.
   Observed: active, and the agent receives one step section of the guide at a time, beginning with
   step section 1.
   Realized by: the component's own operational policies, whose step mode flag the component
   resolves from the declarative TOML configuration file through `filesystem_ext`.

2. The step section numbered 1 is reported complete, and the caller reads the step mode policy
   again.
   Observed: still active, and the agent now receives step section 2.
   Realized by: the component's own operational policies, which the component reads without
   re-resolving the model configuration.

3. The caller reads the step mode policy of a second agent config whose session configuration
   supplies the startup read policy and leaves the step mode policy inactive.
   Observed: inactive, and the agent receives the guide as a whole rather than one step section at
   a time.
   Realized by: the component's own operational policies, whose inactive step mode flag falls back
   to the standard defaults.

### Scenario 8 — Inspecting files at session start, and reporting edits as deltas

Given: the startup read and delta output policies are both active, the session declares the file
`widget/notes/draft.md`, and the caller runs an editing tool that replaces the line
`old widget note` with `new widget note` in that file.

1. The caller reads the startup read policy at session start and the files the policy names.
   Observed: active, and the file `widget/notes/draft.md` is inspected at session start.
   Realized by: the component's own operational policies, whose startup read flag the component
   resolves from the declarative TOML configuration file through `filesystem_ext`.

2. The caller reads the delta output policy together with the reporting mode it selects for editing
   tools.
   Observed: the policy is active, and the selected mode reports the change replacing
   `old widget note` with `new widget note` rather than the complete file content of
   `widget/notes/draft.md`.
   Realized by: the component's own operational policies, whose delta output flag the component
   resolves from the declarative TOML configuration file through `filesystem_ext`.

3. The caller reads the delta output policy of a config whose session configuration supplies the
   startup read policy and the follow-up injection policy and leaves the delta output policy
   inactive.
   Observed: inactive, so the selected mode reports the complete file content instead of the change.
   Realized by: the component's own operational policies, whose inactive delta output flag falls
   back to the standard defaults.

### Scenario 9 — Reading the traversal limits

Given: the ambient configuration supplies a node visit limit of 3 and a batch size of 2 for the
dependency graph of the build named `nightly`.

1. The caller reads the node visit limit of the `nightly` build's dependency graph.
   Observed: 3.
   Realized by: the component's own node visit bound, which the component resolves from the
   declarative TOML configuration file through `filesystem_ext`.

2. The caller reads the batch size of that dependency graph.
   Observed: 2.
   Realized by: the component's own batching bound, which the component resolves from the
   declarative TOML configuration file through `filesystem_ext`.

### Scenario 10 — Stable limits across repeated reads

Given: the ambient configuration supplies a node visit limit of 10 and a batch size of 4.

1. The caller reads the node visit limit and the batch size twice in succession.
   Observed: both reads report 10 and 4, with no read altering the limit or the size.
   Realized by: the component's own loaded traversal bounds, which the component reads without
   re-reading the declarative TOML configuration file through `filesystem_ext`.

### Scenario 11 — Limits recovered from a fresh configuration

Given: the configuration is replayed from the same environment that supplied a node visit limit of
7 and a batch size of 1.

1. The caller reads the node visit limit of the fresh configuration.
   Observed: 7.
   Realized by: the component's own node visit bound, resolved again from the same environment
   through `filesystem_ext`.

2. The caller reads the batch size of the fresh configuration.
   Observed: 1.
   Realized by: the component's own batching bound, resolved again from the same environment through
   `filesystem_ext`.

### Scenario 12 — A system with no ambient configuration

Given: no ambient configuration is active.

1. The caller reads the node visit limit.
   Observed: the read fails explicitly rather than reporting a silent fallback limit.
   Realized by: the component's own absence of a loaded model configuration, which the component
   reports rather than substituting a default bound.

2. The caller reads the batch size.
   Observed: the read fails explicitly rather than reporting a silent fallback size.
   Realized by: the component's own absence of a loaded model configuration, which the component
   reports rather than substituting a default bound.

### Scenario 13 — Reading the connection coordinates from the ambient environment

Given: the process environment supplies `OPENAI_MODEL` as `widget-large`, `OPENAI_BASE_URL` as
`https://models.example.test/v1`, and `OPENAI_API_KEY` as `key_widget_ambient`.

1. The caller reads the model name of the openai config.
   Observed: `widget-large`.
   Realized by: the component's own fallback to ambient environment variables when the named model
   entry is absent, and reading the declarative configuration file through `filesystem_ext`.

2. The caller reads the base url of the openai config.
   Observed: `https://models.example.test/v1`.
   Realized by: the component's own fallback to ambient environment variables when the named model
   entry is absent, and reading the declarative configuration file through `filesystem_ext`.

3. The caller reads the api key of the openai config.
   Observed: `key_widget_ambient`.
   Realized by: the component's own binding of authentication credentials from the ambient process
   environment variables through `filesystem_ext`.

### Scenario 14 — Reading the model hyperparameters

Given: the openai config supplies a timeout of 45 seconds, a temperature of 0.25, and a max tokens
upper bound of 4096.

1. The caller reads the timeout of the openai config.
   Observed: 45 seconds, the maximum duration permitted for a model request.
   Realized by: the component's own model execution settings, which it resolves from the declarative
   TOML configuration file through `filesystem_ext`.

2. The caller reads the temperature of the openai config.
   Observed: 0.25.
   Realized by: the component's own model execution settings, which it resolves from the declarative
   TOML configuration file through `filesystem_ext`.

3. The caller reads the max tokens upper bound of the openai config.
   Observed: 4096, the maximum number of response tokens permitted per request while token
   generation is constrained.
   Realized by: the component's own model execution settings, which the component reads from the
   declarative TOML configuration file through `filesystem_ext` when token generation is
   constrained.

### Scenario 15 — Connection coordinates from a named model entry

Given: the declarative TOML configuration file `model_configs.toml` sits in the repository root and
holds the entry `fast` with the model name `widget-large`, the base url
`https://models.example.test/v1`, the timeout 45 seconds, the temperature 0.25, and the max tokens
upper bound 4096, and the active model configuration name is `fast`.

1. The caller reads the model name of the openai config.
   Observed: `widget-large`.
   Realized by: reading the declarative configuration file in the repository root through
   `filesystem_ext` and the component's own selection of the named model entry.

2. The caller reads the temperature of the openai config.
   Observed: 0.25.
   Realized by: reading the declarative configuration file in the repository root through
   `filesystem_ext` and the component's own selection of the named model entry.

### Scenario 16 — Credentials bound from the environment variable the entry designates

Given: the declarative TOML configuration file `model_configs.toml` holds the entry `fast` naming
the environment variable `WIDGET_API_KEY` as the credential source, the active model configuration
name is `fast`, and the process environment supplies `WIDGET_API_KEY` as `key_widget_entry`.

1. The caller reads the api key of the openai config.
   Observed: `key_widget_entry`, the credential the entry designates.
   Realized by: reading the declarative configuration file through `filesystem_ext` and the
   component's own binding of the designated environment variable rather than an ambient default.

### Scenario 17 — A model name that the configuration does not constrain

Given: the openai config resolves its model name from the default selection the workspace
configuration file declares, and the entry supplies no max tokens upper bound.

1. The caller reads the model name of the openai config.
   Observed: the model name the default selection declares.
   Realized by: reading the workspace configuration file through `filesystem_ext` and the
   component's own fallback to the default selection it declares.

2. The caller reads the max tokens upper bound of the openai config.
   Observed: no token bound is applied to a model request, because token generation is not
   constrained.
   Realized by: the component's own model execution settings, which apply a token bound only when
   the configuration constrains token generation.

### Scenario 18 — Reading the same coordinates twice

Given: the process environment supplies `OPENAI_MODEL` as `widget-large`, and the openai config
supplies a timeout of 45 seconds.

1. The caller reads the model name and the timeout twice in succession.
   Observed: both reads report `widget-large` and 45 seconds, and neither read alters the model name
   or the timeout.
   Realized by: the component's own loaded model parameters, which it reads without re-reading the
   configuration sources through `filesystem_ext`.

## Implementation-only

### Scenario 19 — The command-line argument names the active model configuration

Given: the repository root holds the declarative TOML configuration file `model_configs.toml` with
the entries `fast` and `careful`, the entry `fast` supplies the model name `widget-large` and the
entry `careful` supplies the model name `widget-small`, the process environment supplies
`CLEANROOM_MODEL` as `careful`, and the caller passes the `--config` command-line argument `fast`.

1. The caller runs a model request.
   Observed: the request names the model `widget-large`, because the command-line argument selects
   the entry `fast` ahead of the environment variable that selects `careful`.
   Realized by: reading the declarative configuration files from host filesystem paths through
   `filesystem_ext`, and the component's own resolution of the active model configuration name from
   the command-line argument ahead of the environment variables.

### Scenario 20 — The environment variables name the active model configuration

Given: the repository root holds the declarative TOML configuration file `model_configs.toml` with
the entries `fast` and `careful`, no command-line argument is supplied, and the process environment
supplies `CLEANROOM_MODEL` as `fast` and `MODEL_CONFIG_TARGET` as `careful`.

1. The caller runs a model request.
   Observed: the request names the model the entry `fast` supplies, because `CLEANROOM_MODEL` is
   consulted ahead of `MODEL_CONFIG_TARGET`.
   Realized by: the component's own resolution of the active model configuration name from the
   process environment, and reading the declarative configuration files through `filesystem_ext`.

### Scenario 21 — No argument and no environment variable leaves the default selection

Given: the repository root holds the declarative TOML configuration file `model_configs.toml` with
the entries `fast` and `careful`, the workspace configuration file declares `fast` as the default
selection, and the process environment supplies neither `CLEANROOM_MODEL` nor
`MODEL_CONFIG_TARGET`.

1. The caller runs a model request.
   Observed: the request names the model the entry `fast` supplies, being the default selection the
   workspace configuration file declares.
   Realized by: the component's own fallback to the default selection declared in the workspace
   configuration file and reading that file through `filesystem_ext`.

### Scenario 22 — A named entry that the configuration file does not hold

Given: the repository root holds the declarative TOML configuration file `model_configs.toml` with
the entry `fast` only, the active model configuration name is `careful`, and the process environment
supplies `OPENAI_MODEL` as `widget-fallback` and `OPENAI_API_KEY` as `key_widget_fallback`.

1. The caller runs a model request.
   Observed: the request names the model `widget-fallback` and presents the credential
   `key_widget_fallback`, because the absent entry `careful` falls back to the ambient environment.
   Realized by: the component's own fallback to ambient environment variables when the named model
   entry is absent, and reading the declarative configuration file through `filesystem_ext`, which
   reports the entry as absent rather than failing the run.

### Scenario 23 — A configuration file that cannot be decoded

Given: the repository root holds the file `model_configs.toml` whose text is
`[models.fast` with no closing bracket, and the active model configuration name is `fast`.

1. The caller runs a model request.
   Observed: the run fails explicitly, naming `model_configs.toml`, and no model request is sent
   with ambient credentials substituted for the malformed entry.
   Realized by: reading the declarative configuration files through `filesystem_ext`, whose
   structured failure the component's own propagation reports instead of falling back silently.
