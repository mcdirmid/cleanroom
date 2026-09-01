# runner_logger_impl

imports: runner_logger
types from runner_logger: runner logger, log event
implements: runner logger

## Behavior

- A *runner logger* clears any existing transcript log file at initialization.
- A *runner logger* writes single-line compact summaries of *log events* to standard output.
- A *runner logger* writes unbuffered verbose entries of *log events* to a transcript log file.
- The transcript log file destination defaults to "agent_loop.log" or is resolved by a *runner logger* from configured environment variables.
- A *runner logger* intercepts termination signals to ensure transcript log files are flushed and closed.
