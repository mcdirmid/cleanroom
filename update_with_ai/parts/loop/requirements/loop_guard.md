# loop_guard interface component

imports: tool_provider

## Assumptions and Requirements

### Requirements

1. A loop guard evaluates consecutive executions of identical tools and edits.
2. Consecutive repetitions reaching a warning threshold produce a loop reminder.
3. Consecutive repetitions reaching a fatal threshold produce a loop failure communicating session termination.
4. Executing a tool that demonstrates progress clears repetition tracking in the loop guard.

## Grounding Facts

### Knowledge Needed

- Tool execution signatures and edit hashes.
- Warning repetition threshold.
- Fatal repetition threshold.
- Progress indication signals.

### Actions Needed

- Evaluate consecutive executions against repetition thresholds.
- Produce loop reminder upon warning threshold.
- Produce loop failure upon fatal threshold.
- Reset repetition tracking when progress occurs.
