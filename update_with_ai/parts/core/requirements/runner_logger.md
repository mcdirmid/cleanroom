# runner_logger interface component

## Assumptions and Requirements

### Requirements

1. A runner log event is a record of an observable execution event that provides an event name, a single-line summary, and a verbose transcript representation.
2. The runner logger consumes runner log events, writing compact single-line summaries to standard output and full verbose records to a transcript log file.

## Grounding Facts

### Knowledge Needed

- Runner log event attributes (name, summary, verbose transcript).
- Output channels (standard output, transcript log file).

### Actions Needed

- Emit single-line summary to standard output.
- Write verbose transcript representation to transcript log file.
