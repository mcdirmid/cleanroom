<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:28:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: a0358f79c7f5
-->

# sandbox interface component

## Intent

Agent sessions operate across heterogeneous tools spanning file inspection, editing, and outcome control. If these capabilities are exposed as disconnected services, orchestrators must duplicate initialization logic, manage race conditions during startup template creation, and manually track workspace mutations. The sandbox interface component establishes a unified session coordination boundary that ensures template materialization precedes agent execution and exposes session-wide file modification state.

By coordinating starter template instantiation for missing read-write files and exposing whether workspace file modifications occurred, the sandbox provides orchestrators with clear environment guarantees.

## Factored Contracts

### Contracts

- An agent session's sandbox coordinates starter template materialization. [sandbox_coordinates_template_materialization]
- An agent session's sandbox coordinates file modification tracking. [sandbox_coordinates_modification_tracking]
- The sandbox materializes startup templates into missing read-write files at session start. [materialize_startup_templates]
- Materializing startup templates preserves existing files without overwriting. [preserve_existing_files_during_materialization]
- The sandbox exposes whether workspace file modifications occurred during the session. [expose_modifications_occurred]

## Woven Contracts

- Materializing startup templates writes boilerplate into missing read-write files without overwriting existing workspace content. [sandbox_coordinates_template_materialization, materialize_startup_templates, preserve_existing_files_during_materialization]
- Workspace modification queries indicate whether files were changed during the active session. [sandbox_coordinates_modification_tracking, expose_modifications_occurred]
