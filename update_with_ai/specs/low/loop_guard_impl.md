<!-- Dependencies (md files to read alongside this one):
  - loop_guard.md
  - agent_loop_config.md
-->

# Implementation LLS: loop_guard_impl

## Data Types
```python
from loop_guard import LoopGuard
from agent_loop_config import AgentLoopConfig

class LoopGuardImpl(LoopGuard):
    def __init__(self, config: AgentLoopConfig | None = None) -> None: ...
```

The implementation tracks loop signatures, file ranges, and repetition counts.

## Behavioral Description

`LoopGuardImpl` fulfills the `LoopGuard` Protocol by monitoring consecutive tool executions and response patterns.

- **Loop Repetition:** Tracks `(tool_name, sorted_json_arguments)`. When the tool is `advance`, resets the signature and count. Otherwise, increments consecutive repeats. At 4 repeats, if no reminder was injected yet, returns a reminder. At 8 repeats, returns degenerate loop failure with pinned error text `Degenerate loop: same tool call repeated 8 consecutive times`.
- **Range Repetition:** For `update_lines`, tracks `(file_path, start_line, end_line)`. At 4 repeats, if no reminder was injected yet, returns range-specific reminder text. At 8 repeats, returns degenerate loop failure with pinned error text `Degenerate loop: update_lines targeted the same file and line range 8 consecutive times`.
- **Degenerate Responses:** `check_degenerate_response` checks if `isinstance(content, str) and len(content) > 0 and len(set(content)) == 1`.
- **Termination Reminder:** `get_termination_reminder` invokes `config.termination_reminder_generator()` if available; otherwise returns pinned default text `You must signal termination by calling advance(), fail(), or blame() to end the run.`.

## Invariants

- At most one reminder injected per run
- The advance tool resets tracking
- Eight consecutive repetitions fail the run
- No state persists across runs

## Non-Concerns

- **Default termination reminder:** Pinned to `You must signal termination by calling advance(), fail(), or blame() to end the run.`
- **Degenerate error texts:** Pinned to `Degenerate loop: same tool call repeated 8 consecutive times` and `Degenerate loop: update_lines targeted the same file and line range 8 consecutive times`
