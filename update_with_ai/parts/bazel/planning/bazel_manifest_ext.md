<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:28:01Z
LAST_CHANGED: 2026-10-05T04:26:30Z
CHANGE: new file
CODE_HASH: 982dda01b72a
-->

# bazel_manifest_ext external component

## Intent

Autonomous task execution and graph loading require reading build metadata produced by the build system. The Starlark build rules emit structured JSON manifests capturing unit declarations, role specifications, and monolithic target definitions.

The bazel_manifest_ext external component encapsulates the JSON formats and field structures for unit manifests, role manifests, and target manifests. By establishing a formal boundary for build system metadata schemas, the external boundary enables manifest loaders to decode build artifacts deterministically without coupling to Starlark implementation mechanics.

## Factored Contracts

### Contracts

- A caller supplies unit manifest JSON text when parsing a unit manifest. [unit_manifest_text_supplied]
- A caller supplies role manifest JSON text when parsing a role manifest. [role_manifest_text_supplied]
- A caller supplies target manifest JSON text when parsing a target manifest. [target_manifest_text_supplied]
- Parsing a unit manifest extracts the unit target label. [parse_unit_label]
- Parsing a unit manifest extracts the unit directory path. [parse_unit_dir]
- Parsing a unit manifest extracts the unit name. [parse_unit_name]
- Parsing a unit manifest extracts the unit dependencies sequence. [parse_unit_deps]
- Parsing a unit manifest extracts the component type classification. [parse_component_type]
- Parsing a role manifest extracts the role target label. [parse_role_label]
- Parsing a role manifest extracts the role name. [parse_role_name]
- Parsing a role manifest extracts the source path pattern template. [parse_src_pattern]
- Parsing a role manifest extracts the task prompt template. [parse_prompt_template]
- Parsing a role manifest extracts the verification check template. [parse_verify_template]
- Parsing a role manifest extracts the active component types sequence. [parse_active_component_types]
- Parsing a role manifest extracts the node dependencies sequence. [parse_node_deps]
- Parsing a role manifest extracts the role dependencies sequence. [parse_role_deps]
- Parsing a role manifest extracts the star role dependencies sequence. [parse_star_role_deps]
- Parsing a role manifest extracts the silent cross-role dependencies sequence. [parse_silent_cross_role_deps]
- Parsing a role manifest extracts the feedback role dependencies sequence. [parse_feedback_role_deps]
- Parsing a role manifest extracts the guide target label. [parse_role_guide_label]
- Parsing a role manifest extracts the step mode permission. [parse_allows_step_mode]
- Parsing a target manifest extracts the monolithic target fields. [parse_monolithic_target_fields]

## Woven Contracts

- When parsing unit manifest JSON text, unit target label, directory path, unit name, dependencies sequence, and component type classification are extracted into structured unit metadata. [unit_manifest_text_supplied, parse_unit_label, parse_unit_dir, parse_unit_name, parse_unit_deps, parse_component_type]
- When parsing role manifest JSON text, role metadata, path patterns, prompt templates, dependency sequences, and active component types are extracted into structured role metadata. [role_manifest_text_supplied, parse_role_label, parse_role_name, parse_src_pattern, parse_prompt_template, parse_verify_template, parse_active_component_types, parse_node_deps, parse_role_deps, parse_star_role_deps, parse_silent_cross_role_deps, parse_feedback_role_deps, parse_role_guide_label, parse_allows_step_mode]
- When parsing monolithic target manifest JSON text, target fields are extracted into structured target metadata. [target_manifest_text_supplied, parse_monolithic_target_fields]
