# loop_node_cleaner interface component

imports: dag_storage

## Assumptions and Requirements

### Requirements

1. A node cleaner can clean dirty nodes, communicating whether processing should continue.
2. Processing cannot continue only if a failure occurs while cleaning the nodes that cannot be handled by cleaning any other node; otherwise, processing continues.

## Grounding Facts

### Knowledge Needed

- Dirty nodes batch.
- Continuation outcome status.

### Actions Needed

- Clean dirty nodes.
- Communicate whether processing should continue.
