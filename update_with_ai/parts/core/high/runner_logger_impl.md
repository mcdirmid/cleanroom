# runner_logger_impl implementation component

implements: runner_logger

## Purpose

The runner_logger_impl implementation component realizes unbuffered file logging and live terminal output for execution events.

Unbuffered write guarantees ensure diagnostic logs are preserved even when processes encounter abrupt crashes or interrupts. The runner_logger_impl implementation component establishes safe initialization of transcript log destinations, formats timestamped terminal summaries, and streams verbose payloads without buffering.

**Out of scope:** The runner_logger_impl implementation component does not parse structured telemetry, filter event streams, or manage remote log aggregators; these are handled by other components.

## Types and Behavior

The runner logger clears any existing transcript log file at initialization. The transcript log file destination defaults to `agent_loop.log` or is resolved from configured environment variables.

When consuming runner log events, the runner logger writes single-line compact summaries to standard output and writes unbuffered verbose entries to the transcript log file.
