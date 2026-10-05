<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:45:49Z
LAST_CHANGED: 2026-10-05T04:45:49Z
CHANGE: Make log opening declarative and specify concrete unbuffered flush mechanics
CODE_HASH: 79be16ba3400
-->

# runner_logger_impl implementation component

implements: runner_logger

## Purpose

The runner_logger_impl implementation component realizes unbuffered file logging and live terminal output for execution events.

Unbuffered write guarantees ensure diagnostic logs are preserved even when processes encounter abrupt crashes or interrupts. The runner_logger_impl implementation component establishes safe initialization of transcript log destinations, formats timestamped terminal summaries, and streams verbose payloads without buffering.

**Out of scope:** The runner_logger_impl implementation component does not parse structured telemetry, filter event streams, or manage remote log aggregators; these are handled by other components.

## Types and Behavior

The transcript log file is truncated at opening so that each execution session starts with a clean transcript log. The transcript log file destination defaults to `agent_loop.log` or is resolved from configured environment variables.

Standard output lines format single-line summaries with timestamps and event names for live terminal visibility. Transcript log entries append verbose records with immediate flushing after each write, guaranteeing unbuffered persistence across unexpected crashes.
