# agent_storage interface component

imports: dag_storage

## Assumptions and Requirements

### Requirements

1. A task prompt is an instruction describing the work required to clean a node.
2. A node definition is metadata describing task prompts for a node.
3. The agent storage maintains nodes, dependencies, reverse dependencies, and pending messages from workspace targets.
4. The agent storage provides task prompts and node definitions for declared nodes.
5. Declared dependencies marked propagating mark dependent nodes dirty when changed.

## Grounding Facts

### Knowledge Needed

- Node definitions and task prompts.
- Propagating dependency relationships.
- Target nodes and pending messages.

### Actions Needed

- Maintain nodes, dependencies, and reverse dependencies.
- Provide task prompts for declared nodes.
- Mark dependent nodes dirty upon propagating dependency changes.
