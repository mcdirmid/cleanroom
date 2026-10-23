# dirtiness_impl implementation component

imports: session, src_metadata, role_registry
implements: dirtiness

## Purpose

The dirtiness_impl implementation component realizes unit dirtiness evaluation, companion specification contract resolution, and cross-unit dependency extraction.

Evaluating whether a target file in a role workspace is dirty requires deep semantic analysis of file modifications, in-band metadata timestamps, companion specifications, and implicit dependencies across producer and auditor roles. The dirtiness_impl implementation component inspects in-band source metadata, extracts contract definitions, detects unacted feedback, and identifies cross-unit dependencies.

**Out of scope:** The dirtiness_impl implementation component does not sort candidate queues topologically, persist pending work state, or execute test commands; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; role configuration lookups are delegated to role_registry; in-band source metadata extraction is delegated to src_metadata.

## Types and Behavior

The workspace dirtiness evaluator analyzes units in a designated directory scope.

When evaluating unit dirtiness:

- The dirtiness evaluator inspects the target file corresponding to the unit and role, resolving candidate files from the canonical repository root first when available to inspect authoritative lifecycle timestamps rather than local projected workspace files, determining whether the file is absent from disk, unparseable, or modified after its last cleaned timestamp, reporting uninitialized targets as requiring initial implementation rather than citing internal in-band metadata terminology.

- The dirtiness evaluator inspects the in-band metadata across every feedback role target configured for an active auditor role, evaluating the unit as dirty when a feedback target is missing, uninitialized, lacks the required role audit attribute, or has been modified after its audit timestamp.

- The dirtiness evaluator evaluates intra-unit upstream contract dependencies for producer roles from declared role dependencies, and evaluates cross-unit dependencies from declared star role dependencies, evaluating the target as dirty when an upstream dependency or a star role dependency has been modified more recently than the last cleaned timestamp of the target.

- The dirtiness evaluator resolves companion upstream specification contract files and interface definitions for candidate targets using dynamic role definitions, avoiding peer implementation file leakage.

- The dirtiness evaluator extracts cross-unit dependencies by filtering out silent cross-role dependencies and expanding star-role specification contracts dynamically defined for the active role.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-18T01:30:00Z
CHANGE: Report uninitialized targets as requiring initial implementation without exposing internal metadata terminology
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
