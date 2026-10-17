<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:15:00Z
CHANGE: Define dirtiness_impl planning specification
CODE_HASH: 642d55e58899
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# dirtiness_impl implementation component

## Intent

Evaluating whether a target file in a role workspace is dirty requires deep semantic analysis of file modifications, in-band metadata timestamps, companion specifications, and implicit dependencies across producer and auditor roles. The dirtiness_impl implementation component inspects in-band source metadata, extracts contract definitions, detects unacted feedback, and identifies cross-unit dependencies.

## Factored Contracts

### Contracts

- The workspace dirtiness evaluator inspects the target file corresponding to the unit and role, determining whether the file is absent, unparseable, or modified after its last cleaned timestamp. [inspect_target_file_dirtiness]
- The workspace dirtiness evaluator inspects the in-band metadata across every feedback role target configured for an active auditor role, evaluating the unit as dirty when a feedback target is missing, lacks the required role audit attribute, or has been modified after its audit timestamp. [inspect_auditor_feedback_targets]
- The workspace dirtiness evaluator treats feedback role dependencies and star role dependencies as implicit role dependencies for producer roles, evaluating the target as dirty when an upstream dependency or a star role dependency has been modified more recently than the last cleaned timestamp of the target. [inspect_producer_implicit_and_star_deps]
- The workspace dirtiness evaluator resolves companion upstream specification contract files and interface definitions for candidate targets using dynamic role definitions, avoiding peer implementation file leakage. [discover_companion_contract_files]
- The workspace dirtiness evaluator extracts cross-unit dependencies by filtering out silent cross-role dependencies and expanding star-role specification contracts dynamically defined for the active role. [resolve_cross_unit_dependencies]

### Woven Contracts

- When evaluating unit status in a role workspace, the dirtiness evaluator inspects target files, evaluates auditor feedback targets or producer dependencies, and discovers companion contracts. [inspect_target_file_dirtiness, inspect_auditor_feedback_targets, inspect_producer_implicit_and_star_deps, discover_companion_contract_files, resolve_cross_unit_dependencies, dirtiness: [evaluate_unit_dirtiness, evaluate_implicit_and_star_dirtiness, evaluate_auditor_target_dirtiness, resolve_companion_contract_files, extract_cross_unit_dependencies], src_metadata: [extract_metadata_disk], role_registry: [resolve_role_definition]]

## Grounding

### Knowledge Provisions

- Target file and in-band metadata dirtiness inspection mechanics. [target_dirtiness_mechanics]
- Auditor feedback target and upstream contract verification mechanics. [auditor_dirtiness_mechanics]
- Producer implicit dependency and star role dependency checking mechanics. [producer_dirtiness_mechanics]
- Companion contract resolution and cross-unit dependency extraction logic. [companion_contract_resolution_logic]

### Inherited Deferred Requirements

- In-band source metadata extraction and evaluation.
  - Grounded: [target_dirtiness_mechanics, auditor_dirtiness_mechanics, producer_dirtiness_mechanics, src_metadata: [source_metadata_service]]
- Role definition resolution and pattern matching.
  - Grounded: [role_registry: [workspace_registry_service]]
- Scope file resolution and dirtiness evaluation mechanics.
  - Grounded: [target_dirtiness_mechanics, auditor_dirtiness_mechanics, producer_dirtiness_mechanics]

### Knowledge Requirements

- In-band source metadata extraction.
  - Grounded: [src_metadata: [source_metadata_service]]
- Role definition resolution and pattern matching.
  - Grounded: [role_registry: [workspace_registry_service]]
