<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:11:12Z
CHANGE: Author agent agent_session interface scenarios
CODE_HASH: 8e70c384d549
-->

# Concrete scenarios for `agent_session` (interface)

## Scenario 1 — Establishing one agent session

Given: agent alpha runs in the workspace directory `/ws/alpha_scope_a`, and no session is yet
established there.

1. The caller opens a session for agent alpha in `/ws/alpha_scope_a`.
   Observed: exactly one session exists for alpha, identified by the workspace directory
   `/ws/alpha_scope_a`, and it is the only session established for that agent.

## Scenario 2 — Two independent sessions

Given: agent alpha runs in `/ws/alpha_scope_a` and agent beta runs in `/ws/beta_scope_b`.

1. The caller opens a session for alpha in `/ws/alpha_scope_a` and a session for beta in
   `/ws/beta_scope_b`.
   Observed: two sessions exist, the first bounded to `/ws/alpha_scope_a` and the second bounded to
   `/ws/beta_scope_b`, and neither session reports the other's workspace directory.

## Scenario 3 — Ephemeral state stays inside its session

Given: the caller has opened one session for agent alpha in `/ws/alpha_scope_a` and a second
session for the same agent in the same workspace directory, and the first session has recorded the
conversation turn whose text is `clean the widget target` and one pending tool call for the unit
widget.

1. The caller reads the conversation recorded by the second session.
   Observed: no conversation turn is recorded there, and no conversation turn carries the text
   `clean the widget target`.

2. The caller reads the second session's pending tool calls.
   Observed: none are pending, and no pending call names the unit widget.

## Scenario 4 — No session has been established

Given: no agent is running in `/ws/alpha_scope_a`, and no session has been established there.

1. The caller reads the current session for `/ws/alpha_scope_a`.
   Observed: no session is current, and the read fails explicitly rather than supplying a session
   for the workspace directory.

## Scenario 5 — A session that has ended

Given: one session for agent alpha in `/ws/alpha_scope_a` is current, and it has recorded one
conversation turn.

1. The caller ends that session.
   Observed: no session for `/ws/alpha_scope_a` is current afterwards, and the conversation that
   session recorded is no longer reported.

2. The caller asks the ended session to record a further conversation turn.
   Observed: the request fails explicitly, and the ended session records no turn.

## Scenario 6 — The tier beneath the system environment

Given: one session for agent alpha in `/ws/alpha_scope_a` exists, and the system-wide environment
also holds the ambient setting whose name is `default persona`.

1. The caller reads the ambient setting from the system-wide environment while the session is
   established.
   Observed: `default persona` remains readable at the system level and is not reported as part of
   the alpha session.

2. The caller ends the alpha session and reads the ambient setting again.
   Observed: `default persona` is still readable and unchanged, so ending the session removed only
   state bounded by that session.
