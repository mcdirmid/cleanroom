# runner_logger

## Purpose

Captures observable execution events during runner passes, providing concise terminal output and unbuffered audit transcripts.

Running multi-turn agent passes without observable logging hides failures and complicates debugging. Runner logger consumes structured execution events across the system, formatting compact single-line summaries for live operator visibility while recording detailed unbuffered transcripts to disk for auditing and replay.

## Types

- A *log event* is a structured record of an observable execution event, produced by any component and consumed by a *runner logger*
- A *runner logger* is a service that formats and records *log events*

## Behavior

- A *log event* provides an event name and a single-line summary in support of logging by a *runner logger*.
- A *log event* provides a verbose transcript representation in support of logging by a *runner logger*.
- A *runner logger* consumes *log events*, writing summaries to standard output and full records to a transcript log.
