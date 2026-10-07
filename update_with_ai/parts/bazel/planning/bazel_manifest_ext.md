<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 20454ec65a89
-->

# bazel_manifest_ext external component

## Intent

Autonomous task execution and graph loading require reading build metadata produced by the build system. The Starlark build rules emit structured JSON manifests capturing unit declarations, role specifications, and monolithic target definitions.

The bazel_manifest_ext external component encapsulates the JSON formats and field structures for unit manifests, role manifests, and target manifests. By establishing a formal boundary for build system metadata schemas, the external boundary enables manifest loaders to decode build artifacts deterministically without coupling to Starlark implementation mechanics.

## Grounding

### Knowledge Provisions

- External parsing of unit manifest JSON into structured unit metadata. [unit_manifest_parsing]
- External parsing of role manifest JSON into structured role metadata. [role_manifest_parsing]
- External parsing of monolithic target manifest JSON into structured target metadata. [target_manifest_parsing]
