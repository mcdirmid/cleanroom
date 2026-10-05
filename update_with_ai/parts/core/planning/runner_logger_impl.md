<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T02:07:35Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 65ec5530fb76
-->

# runner_logger_impl implementation component

implements: runner_logger

## Intent

Unbuffered write guarantees ensure diagnostic logs are preserved even when processes encounter abrupt crashes or interrupts. The runner_logger_impl implementation component establishes safe initialization of transcript log destinations, formats timestamped terminal summaries, and streams verbose payloads without buffering.

By clearing prior run logs at startup and resolving output destinations from environment variables or standard fallbacks, the implementation ensures continuous audit trails across multi-turn runs.

## Factored Contracts

### Contracts

- The runner logger clears existing transcript log files at initialization. [clear_transcript_at_init]
- The runner logger defaults the transcript log file destination to `agent_loop.log`. [default_log_destination]
- The runner logger resolves the transcript log file destination from configured environment variables when present. [resolve_env_log_destination]
- Consuming runner log events writes unbuffered verbose entries to the transcript log file. [write_unbuffered_transcript]

## Woven Contracts

- At initialization, the runner logger resolves the transcript log file destination and clears any existing file. [clear_transcript_at_init, default_log_destination, resolve_env_log_destination]
- When consuming runner log events, single-line summaries are written to standard output and verbose entries are streamed unbuffered to disk. \[write_unbuffered_transcript, runner_logger: [supply_runner_log_event, consume_log_events, write_stdout_summary, write_transcript_log]\]
