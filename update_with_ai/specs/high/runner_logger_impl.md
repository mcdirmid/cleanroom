# runner_logger_impl

fulfills: runner_logger
imports: agent_loop (run, cumulative usage)
terms (from runner_logger): transcript logging, compact log, verbose transcript, runner usage
terms (from agent_loop): run, cumulative usage

## Deltas

- Resolves log path priority: CLEANROOM_AGENT_LOG, BUILD_WORKSPACE_DIRECTORY, BUILD_WORKING_DIRECTORY, or current working directory.
- Filters out api_response events from compact stdout output.
- Captures SIGINT to ensure log files are properly closed upon interruption.

## Non-concerns

- Multi-process logging synchronization.
