# Cleanroom Behavioral Constraints & Guide References

## Workspace Boundaries & File Locations
- **NEVER modify or rely on the `testing/` directory**: The `testing/` directory is an ephemeral test consumer directory that can be deleted or wiped at any time.
- **Canonical Codebase**: All production specifications, library implementations, and builds live exclusively in:
  - `update_with_ai/`
  - `update_python_with_ai/`

## Guide Editing & Meta-Rules
- **Editing Guides**: ALWAYS read and maintain in context `update_python_with_ai/guides/meta_guide.md` before creating, updating, or editing any guide.

## Required Guides for Alignments & Tasks
Always read and maintain in context the relevant guide from `update_python_with_ai/guides/` when modifying specs, implementations, tests, or doing alignments:
- **High-Level Specs (HLS)**: `update_python_with_ai/guides/high_level_spec.md`
- **HLS to Grounding Alignment**: `update_python_with_ai/guides/high_to_grounding.md`
- **Grounding to Library Code Alignment**: `update_python_with_ai/guides/grounding_to_lib.md`
- **Grounding to Unit Tests Alignment**: `update_python_with_ai/guides/grounding_to_test.md`
- **QA Verification**: `update_python_with_ai/guides/qa.md`

## Bazel Test Execution Flags
- **Required Flags**: When running tests via `bazel test`, ALWAYS include `--test_output=errors --test_timeout=100` and `--noshow_progress --noshow_loading_progress`.
