<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-10T19:00:00Z
CHANGE: evaluate producer dirtiness across implicit role deps and star role changes
CODE_HASH: 4e3847086b64
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# workspace_work_impl implementation component

imports: agent_session, workspace_registry, control_work_scheduler, src_metadata, dag_storage, cleanroom_files_ext
implements: workspace_work

## Purpose

The workspace_work_impl implementation component realizes work queue discovery across directory scopes by role tier depth, pending work tracking, and actionable diagnostic generation.

Guiding autonomous agents through multi-step pipeline tasks requires distinguishing ready targets from targets blocked on upstream artifacts while enforcing completion of pending work before starting new tasks. Without strict queue tracking, agents jump between disconnected files or exit before completing verification. The workspace_work_impl implementation component invokes directory-scoped work scheduling, filters candidates by active role, evaluates pending target dirtiness against local and main workspaces, persists pending target state in the pending work buffer file, and generates structured task outputs with actionable guidance.

**Out of scope:** The workspace_work_impl implementation component does not commission workspace directories, transfer source files, or execute test commands; these are handled by other components.

**Delegated:** Role configuration lookups and path resolution are delegated to workspace_registry; topological dependency scheduling and dirtiness evaluation across directory scopes are delegated to control_work_scheduler; in-band source metadata extraction is delegated to src_metadata; starter template materialization is delegated to dag_storage; workspace file conventions are delegated to cleanroom_files_ext.

## Types and Behavior

The workspace work manager discovers work items within a designated directory scope.

When managing pending target state:

- The work manager records assigned target paths to the pending work buffer file.

- The work manager removes a resolved target path from the pending work buffer file when submitted or blamed, matching target paths and unit stems strictly without clearing unmatched targets.

- The work manager evaluates whether a pending target remains dirty by checking in-band source metadata across local and canonical repositories, treating feedback role dependencies and star role dependencies as implicit role dependencies and evaluating targets as dirty when any star role dependency changes across same-unit, interface, or cross-unit dependencies, verifying all configured feedback role targets for auditor roles against required role audit timestamps and forward contracts, and materializing starter templates via graph storage for missing targets of roles with declared source patterns and upstream dependencies.

When evaluating work in a role workspace:

- The work manager inspects the in-band metadata across every feedback role target configured for the active auditor role when evaluating whether an auditor role unit is dirty, evaluating the unit as dirty when a feedback target is missing, is unparseable, lacks the required role audit attribute, or has been modified more recently than its audit timestamp, and when a non-silent upstream contract dependency has been modified after the audit timestamp of the feedback target.

- The work manager treats feedback role dependencies and star role dependencies as implicit role dependencies when evaluating whether a producer unit is dirty, evaluating the target as dirty when an upstream dependency or a star role dependency has been modified more recently than the last cleaned timestamp of the target.

- The work manager establishes whether the pending work buffer file exists, re-evaluates the dirty status of each pending target from in-band metadata when pending targets exist, and aborts work discovery with an error directing the agent to complete or blame the pending target when a target remains dirty and the request is not forced.

- The work manager clears the pending work buffer file when every previously pending target is clean.

- The work manager schedules work for the directory scope through the work scheduler without providing a subgraph, scanning the units in scope, checking dependency dirtiness, and sorting candidate tasks by role tier depth.

- The work manager inspects the build definitions when present, extracting the imported, implemented, and assembled dependencies from the High-Level Specifications of the unit, or derives dependencies from the filesystem component stems when discovering units and dependencies in a part directory.

- The work manager partitions candidate tasks into ready items whose forward dependencies are clean, and blocked items whose prerequisites remain dirty, bounding presented ready items by the requested batch size when positive and tracking the remaining unpresented ready count.

- The work manager materializes starter templates via graph storage for any ready tasks of roles with declared source patterns and upstream dependencies whose target source files do not exist on disk.

- If ready items exist and a role workspace is active, the manager records the bounded ready target file paths into the pending work buffer.

- The work manager resolves companion upstream specification contract files and interface definitions for candidate targets using dynamic role definitions, avoiding peer implementation file leakage.

- The work manager resolves cross-unit dependencies by filtering out silent cross-role dependencies and expanding star-role specification contracts dynamically defined for the active role.

- The work manager enforces fail-loud resolution for unknown roles or unmatched paths, raising explicit exceptions without synthetic fallbacks.

- The work manager compiles the results into a work queue summary detailing ready tasks, dirty reasons, dependency paths, companion contract files, blocked causes, and role-specific instructions.
