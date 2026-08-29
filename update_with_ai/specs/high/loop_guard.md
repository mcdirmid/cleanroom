# loop_guard

imports: tool_provider (tool results, tool definitions, tool call, session)
terms (from tool_provider): tool result, tool definition, tool call, session
terms (owned): loop repetition, range repetition, loop reminder, degenerate loop, degenerate response

## Purpose

Monitors tool calls and model responses during an agent session to guard against wasted cycles, infinite repetition loops, and stalled termination.

## Terms

- Loop repetition: consecutive execution of identical tool calls with identical arguments.
- Range repetition: consecutive line-range modifications targeting the same file path and line numbers.
- Loop reminder: a warning message injected into the conversation advising the agent to make progress or terminate.
- Degenerate loop: a failure condition triggered when repetition continues beyond the allowed threshold.
- Degenerate response: a truncated response whose content is a single character repeated.

## Contract

**Inputs**

- Per session: tool call names and arguments, response content, finish reasons, and an optional termination reminder generator.

**Operations**

- Evaluate a tool call for loop repetition and range repetition.
- Evaluate whether a truncated model response is degenerate.
- Provide a termination reminder when the model stops with content without requesting tool execution.
- Reset repetition tracking when a progress signal occurs.

**Guarantees**

- Consecutive identical tool calls trigger a loop reminder once per session after four repetitions; eight consecutive repetitions signal a degenerate loop failure.
- Consecutive file-editing tool calls targeting the same file path and line range trigger a range reminder once per session after four repetitions; eight consecutive repetitions signal a degenerate loop failure.
- The advance tool is exempt from repetition tracking and resets the repetition count.
- Truncated responses consisting of a single character repeated signal a degenerate response failure.
- When the model stops without requesting tool execution, provides a termination reminder.
- No tracking state persists across sessions.

**Assumptions**

- Tool calls provide valid tool names and argument mappings.

## Non-concerns

- Reminder wording: the exact text of reminder messages is unspecified.
