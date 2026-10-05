<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 36acb2850a34
-->

# runner_logger interface component

## Intent

Running multi-turn agent passes without observable logging hides failures and complicates debugging. The runner_logger interface component consumes structured execution events across the system, formatting compact single-line summaries for live operator visibility while recording detailed unbuffered transcripts to disk for auditing and replay.

By centralizing event consumption within a system-level logging service, the component decouples individual event producers from terminal output formatting and filesystem persistence mechanics.

## Factored Contracts

### Typing

- A runner log event has an event name.
- A runner log event has a single-line summary.
- A runner log event has a transcript representation.

### Contracts

- A caller supplies a runner log event when logging execution events. [supply_runner_log_event]
- A system's runner logger consumes runner log events. [consume_log_events]
- The runner logger writes single-line summaries to standard output. [write_stdout_summary]
- The runner logger writes verbose transcript representations to a transcript log file. [write_transcript_log]

## Woven Contracts

- When consuming a runner log event, the runner logger writes a single-line summary to standard output and the verbose transcript representation to the transcript log file. [supply_runner_log_event, consume_log_events, write_stdout_summary, write_transcript_log]
