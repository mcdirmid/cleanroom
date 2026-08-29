# runner_logger

imports: agent_loop (run, cumulative usage)
terms (from agent_loop): run, cumulative usage
terms (owned): transcript logging, compact log, verbose transcript, runner usage

## Purpose

Provides transcript logging for build runner passes: formats compact stdout logs, records full verbose transcripts to unbuffered log files, resolves log file paths, and tracks runner usage across nodes.

## Terms

- Transcript logging: the recording and formatting of agent loop execution events during a build pass.
- Runner usage: the accumulated token counts, request counts, and execution duration across all agent sessions in a runner pass.
- Compact log: single-line formatted event summaries suitable for standard output.
- Verbose transcript: detailed event summaries written to an unbuffered log file.

## Contract

**Inputs**

- Per event: an event name and its associated payload dictionary.
- For session setup: an optional log file path override.

**Operations**

- Resolve the destination log file path from environment variables or default conventions.
- Create an agent logger callback and log-file closer for a runner pass.
- Format a compact log line for standard output.
- Format a verbose transcript line for file logging.

**Guarantees**

- Log writes to the transcript file are unbuffered and flushed immediately.
- Runner usage aggregates input tokens, cached input tokens, output tokens, total tokens, request count, and duration across all terminated sessions in the run.
- Unknown log events produce generic fallback formatting without raising exceptions.

**Assumptions**

- Filesystem directories for log file creation are writable.

## Non-concerns

- Terminal color codes: plain text formatting is used.
