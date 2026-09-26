# antigravity_run_logger interface component

## Purpose

The antigravity_run_logger interface component defines execution logging and transcript tracking for Antigravity subagent activity.

Multi-agent coordination across external workspace environments requires observability into worker spawns, tool gating denials, and file modifications. The antigravity_run_logger interface component defines services and data types for recording structured execution events and registering subagent transcripts.

**Out of scope:** The antigravity_run_logger interface component does not validate tool permissions, parse AST code, or execute build commands; these are handled by other components.

## Types and Behavior

An *antigravity log event* record represents a captured execution action, exposing an *event name*, a *source*, and a *summary*.

The *antigravity run logger* is a system service that records execution activity and maintains transcript associations. The antigravity run logger provides:

- A *log event* operation that records an event name, a source, and a summary for an execution action.

- A *register transcript* operation that associates a conversation *identifier* with a role *slug*.

- A *sanitize slug* operation that converts a role *label* into a safe identifier string.
