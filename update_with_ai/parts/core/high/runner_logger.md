# runner_logger interface component

## Purpose

The runner_logger interface component captures observable execution events during runner passes, providing concise terminal output and unbuffered audit transcripts.

Running multi-turn agent passes without observable logging hides failures and complicates debugging. The runner_logger interface component consumes structured execution events across the system, formatting compact single-line summaries for live operator visibility while recording detailed unbuffered transcripts to disk for auditing and replay.

**Out of scope:** The runner_logger interface component does not orchestrate agent turn loops, format model request payloads, or evaluate build graph state; these are handled by other components.

## Types and Behavior

A *log event* is a record of an observable execution event that provides an *event name*, a single-line *summary*, and a verbose *transcript representation*.

The *runner logger* is a system service that formats and records log events. The runner logger:

- *Consumes* log events, writing compact single-line summaries to standard output and full verbose records to a transcript log file.
