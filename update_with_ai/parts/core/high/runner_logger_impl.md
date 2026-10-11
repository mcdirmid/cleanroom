<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Decompose log destination and flush mechanics into declarative statements
CODE_HASH: 2e0ad35b5a16
SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
-->

# runner_logger_impl implementation component

implements: runner_logger

## Purpose

The runner_logger_impl implementation component realizes unbuffered file logging and live terminal output for execution events.

Unbuffered write guarantees preserve diagnostic logs even when processes encounter abrupt crashes or interrupts. The runner_logger_impl implementation component initializes the transcript log destination, formats timestamped terminal summaries, and streams verbose payloads without buffering.

**Out of scope:** The runner_logger_impl implementation component does not parse structured telemetry, filter event streams, or manage remote log aggregators; these are handled by other components.

## Types and Behavior

The transcript log destination resolves from a configured environment variable, defaulting to `agent_loop.log` when no destination is configured. The transcript log file is truncated at opening so that each execution session starts with a clean transcript log.

Standard output lines present single-line summaries with timestamps and event names for live terminal visibility. Transcript log entries append verbose records with immediate flushing after each write, preserving unbuffered persistence across unexpected crashes.
