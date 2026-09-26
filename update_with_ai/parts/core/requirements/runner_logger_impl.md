# runner_logger_impl implementation component

implements: runner_logger

## Assumptions and Requirements

### Requirements

1. The runner logger clears any existing transcript log file at initialization.
2. The transcript log file destination defaults to `agent_loop.log` or is resolved from configured environment variables.
3. Consuming a runner log event writes a single-line compact summary to standard output.
4. Consuming a runner log event writes an unbuffered verbose record to the transcript log file.

## Grounding Facts

### Knowledge Needed

- Transcript log file destination path.
- Standard output stream.
- Runner log event name, summary, and verbose record.

### Actions Needed

- Initialize or truncate transcript log file.
- Write summary line to standard output.
- Append verbose runner log event to transcript log file.
