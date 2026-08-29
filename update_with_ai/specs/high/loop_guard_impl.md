# loop_guard_impl

fulfills: loop_guard
imports: tool_provider (tool call, session), agent_loop_config (agent-loop configuration)
terms (from tool_provider): tool call, session
terms (from agent_loop_config): agent-loop configuration
terms (from loop_guard): loop repetition, range repetition, loop reminder, degenerate loop

## Deltas

- [state] Tracks the signature of the last tool call, the consecutive repetition count, the last file range edited by update_lines, the consecutive range count, and whether a reminder was injected during the current session.
- Four consecutive identical tool calls inject a loop reminder warning; eight consecutive identical calls signal a degenerate loop failure.
- Four consecutive update_lines calls targeting the same file and line range inject a range-specific reminder; eight signal a degenerate loop failure.
- An advance tool call resets repetition counters and is exempt from tracking.
- Uses the configured termination reminder generator from agent-loop configuration when provided; falls back to default termination text when none is configured.
- [state] Resets repetition counters and reminder flags at the start of each session so no state persists across sessions.

## Non-concerns

- Reminder wording: the exact phrasing of reminder messages is an implementation detail.
