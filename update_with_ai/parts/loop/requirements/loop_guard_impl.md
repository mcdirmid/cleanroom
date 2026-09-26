# loop_guard_impl implementation component

imports: loop_guard, tool_provider
implements: loop_guard

## Assumptions and Requirements

### Requirements

1. Produces a loop reminder advising the agent that no new information will be revealed by repeated tool execution until session read-write files are updated and that repeating the tool call without modifying files will trigger fatal loop termination when consecutive identical tool executions reach the reminder threshold of two repetitions.
2. Produces a loop failure communicating session failure when consecutive identical tool executions reach the fatal threshold.
3. Produces a loop reminder at the reminder threshold of two repetitions when consecutive edits target the same file and line range.
4. Produces a loop failure at the fatal threshold when consecutive edits target the same file and line range.
5. A tool execution demonstrating forward progress resets repetition counters in the loop guard.

## Grounding Facts

### Knowledge Needed

- Tool execution name, target file, and arguments.
- Repetition reminder threshold.
- Fatal termination threshold.
- Repetition tracking counters.

### Actions Needed

- Track consecutive identical tool executions and file edits.
- Emit loop reminder at reminder threshold.
- Emit loop failure at fatal threshold.
- Reset tracking counters when tool execution demonstrates forward progress.
