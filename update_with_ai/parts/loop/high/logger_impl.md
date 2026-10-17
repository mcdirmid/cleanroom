<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T12:35:00Z
CHANGE: Present single-line event summaries to standard output without timestamps or event names
CODE_HASH: adde451fcaa5
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# logger_impl implementation component

implements: logger

## Purpose

The logger_impl implementation component realizes unbuffered file logging and live terminal output for execution events.

Unbuffered write guarantees preserve diagnostic logs even when processes encounter abrupt crashes or interrupts. The logger_impl implementation component initializes the transcript log destination, emits terminal summaries, and streams verbose payloads without buffering.

**Out of scope:** The logger_impl implementation component does not parse structured telemetry, filter event streams, or manage remote log aggregators; these are handled by other components.

## Types and Behavior

The transcript log destination resolves from a configured environment variable, defaulting to `agent_loop.log` when no destination is configured. The transcript log file is truncated at opening so that each execution session starts with a clean transcript log.

Standard output lines present single-line event summaries for live terminal visibility without timestamps or event names. Transcript log entries append verbose records with immediate flushing after each write, preserving unbuffered persistence across unexpected crashes.
