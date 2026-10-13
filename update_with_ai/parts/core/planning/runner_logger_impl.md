<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-12T12:35:00Z
CHANGE: Present single-line event summaries to standard output without timestamps or event names
CODE_HASH: 7681b35984eb
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# runner_logger_impl implementation component

## Intent

Unbuffered write guarantees ensure diagnostic logs are preserved even when processes encounter abrupt crashes or interrupts. The runner_logger_impl implementation component establishes safe initialization of transcript log destinations, emits terminal summaries, and streams verbose payloads without buffering.

By clearing prior run logs at startup and resolving output destinations from environment variables or standard fallbacks, the implementation ensures continuous audit trails across multi-turn runs.

## Factored Contracts

### Contracts

- The transcript log file is truncated at opening. [truncate_transcript_at_opening]
- The runner logger defaults the transcript log file destination to `agent_loop.log`. [default_log_destination]
- The runner logger resolves the transcript log file destination from configured environment variables when present. [resolve_env_log_destination]
- Standard output lines present single-line event summaries without timestamps or event names. [format_stdout_summaries]
- Transcript log entries append verbose records. [append_verbose_records]
- Transcript log entries flush immediately after each write. [flush_immediately_after_write]
- Immediate flushing guarantees unbuffered persistence across unexpected crashes. [guarantee_unbuffered_persistence]

### Woven Contracts

- At opening, the runner logger resolves the transcript log file destination and truncates the transcript file. [truncate_transcript_at_opening, default_log_destination, resolve_env_log_destination]
- When consuming runner log events, single-line event summaries are written to standard output for live terminal visibility without timestamps or event names. [format_stdout_summaries, runner_logger: [supply_runner_log_event, consume_log_events, write_stdout_summary]]
- When consuming runner log events, verbose records are appended to disk with immediate flushing guaranteeing unbuffered persistence. [append_verbose_records, flush_immediately_after_write, guarantee_unbuffered_persistence, runner_logger: [supply_runner_log_event, consume_log_events, write_transcript_log]]

## Grounding

### Knowledge Provisions

- Single-line summary formatting and unbuffered terminal emission. [stdout_log_emission]
- Transcript log file writing with resolved destinations and startup truncation. [transcript_log_writing]

### Inherited Deferred Requirements

- Formatting and terminal emission of event summaries.
  - Grounded: [stdout_log_emission, runner_logger: [runner_logging_service]]
- Persistent file recording of verbose event transcripts with immediate flush.
  - Grounded: [transcript_log_writing]

### Knowledge Requirements

- Log destination resolution from environment variables and startup file truncation.
  - Grounded: [transcript_log_writing]
