# sandbox_impl implementation component

imports: sandbox_file_editor
implements: sandbox

## Assumptions and Requirements

### Requirements

1. Querying file modifications delegates to the edit manager.
2. Materializing startup templates delegates to the edit manager to write template content to missing read-write files without overwriting existing files.

## Grounding Facts

### Knowledge Needed

- Modification state from `sandbox_file_editor`.

### Actions Needed

- Query file modifications via `sandbox_file_editor`.
- Materialize templates via `sandbox_file_editor`.
