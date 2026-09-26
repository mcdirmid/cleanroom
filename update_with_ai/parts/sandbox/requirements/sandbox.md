# sandbox interface component

## Assumptions and Requirements

### Requirements

1. The sandbox exposes whether workspace file modifications occurred during the session.
2. Materializing startup templates populates missing read-write files without overwriting existing files.

## Grounding Facts

### Knowledge Needed

- Workspace file modifications status.
- Read-write file templates and existing files.

### Actions Needed

- Track workspace file modifications.
- Materialize missing files from templates.
