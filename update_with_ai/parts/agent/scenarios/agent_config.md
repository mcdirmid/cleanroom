<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:11:13Z
CHANGE: Author agent agent_config interface scenarios
CODE_HASH: aac149bd3deb
-->

# Concrete scenarios for `agent_config` (interface)

## Scenario 1 — Reading the execution parameters

Given: the active agent session configuration supplies a conversation limit of 12, a supersede arg
keep limit of 64, and the follow-up injection, step mode, startup read, and delta output policies
active.

1. The caller reads the conversation limit of the agent config.
   Observed: 12.

2. The caller reads the supersede arg keep limit of the agent config.
   Observed: 64, so at most the 64 trailing characters of a superseded string argument are retained
   as a recognizable hint.

3. The caller reads the supersede arg keep limit a second time.
   Observed: 64 again, unchanged by the preceding read.

## Scenario 2 — Reading the operational policies

Given: the same agent session configuration, in which the follow-up injection, step mode, startup
read, and delta output policies are all active.

1. The caller reads the follow-up injection, step mode, startup read, and delta output policies.
   Observed: each of the four policies is reported active, and no policy is reported inactive.

2. The caller reads the delta output policy of a second agent config whose session configuration
   supplies only the startup read policy.
   Observed: delta output is inactive, step mode is inactive, follow-up injection is inactive, and
   startup read is active; the reads report the remaining policies without failing.

## Scenario 3 — Stable parameters across repeated reads

Given: an agent config whose session configuration supplies a conversation limit of 3, a supersede
arg keep limit of 8, and the step mode policy active.

1. The caller reads all three values twice in succession.
   Observed: both reads report 3, 8, and an active step mode policy, and the reads alter neither
   limit nor the policy.

## Scenario 4 — Parameters recovered from the same session configuration

Given: the same session configuration, supplying a conversation limit of 7, a supersede arg keep
limit of 16, and the delta output policy active, is used to build a fresh agent config.

1. The caller reads the conversation limit of the fresh agent config.
   Observed: 7.

2. The caller reads the supersede arg keep limit of the fresh agent config.
   Observed: 16.

3. The caller reads the delta output policy of the fresh agent config.
   Observed: active, matching the policy the session configuration supplied.

## Scenario 5 — No ambient agent config

Given: no ambient agent config is active for the caller.

1. The caller reads the conversation limit.
   Observed: the read fails explicitly, and no conversation limit is reported.

2. The caller reads the supersede arg keep limit.
   Observed: the read fails explicitly, and no limit is reported.

3. The caller reads the follow-up injection policy.
   Observed: the read fails explicitly, and the policy is reported as neither active nor inactive.

## Scenario 6 — Following up an injected tool call

Given: the follow-up injection policy is active, and the last tool response designates a follow-up
tool call naming the tool `read_file` for the file `widget/notes/draft.md`.

1. The caller reads the follow-up injection policy of the agent config and the follow-up tool call
   of that tool response.
   Observed: the policy is active, and the designated call names `read_file` with the argument
   `widget/notes/draft.md`, so the agent executes it.

2. The caller reads the same tool response against a config whose follow-up injection policy is
   inactive.
   Observed: the policy is inactive, and although the response still designates the `read_file`
   follow-up call, the agent executes no tool call in response to it.

## Scenario 7 — Receiving a guide progressively

Given: the step mode policy is active, and the session guide holds the step section numbered 1
titled `Inspect the widget contract` and the step section numbered 2 titled
`Clean the widget source`.

1. The caller reads the step mode policy of the agent config.
   Observed: active, and the agent receives one step section of the guide at a time, beginning with
   step section 1.

2. The step section numbered 1 is reported complete, and the caller reads the step mode policy
   again.
   Observed: still active, and the agent now receives step section 2.

3. The caller reads the step mode policy of a second agent config whose session configuration
   supplies the startup read policy and leaves the step mode policy inactive.
   Observed: inactive, and the agent receives the guide as a whole rather than one step section at
   a time.

## Scenario 8 — Inspecting files at session start, and reporting edits as deltas

Given: the startup read and delta output policies are both active, the session declares the file
`widget/notes/draft.md`, and the caller runs an editing tool that replaces the line
`old widget note` with `new widget note` in that file.

1. The caller reads the startup read policy at session start and the files the policy names.
   Observed: active, and the file `widget/notes/draft.md` is inspected at session start.

2. The caller reads the delta output policy together with the reporting mode it selects for editing
   tools.
   Observed: the policy is active, and the selected mode reports the change replacing
   `old widget note` with `new widget note` rather than the complete file content of
   `widget/notes/draft.md`.

3. The caller reads the delta output policy of a config whose session configuration supplies the
   startup read policy and the follow-up injection policy and leaves the delta output policy
   inactive.
   Observed: inactive, so the selected mode reports the complete file content instead of the change.
