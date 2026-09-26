# dag_config interface component

## Assumptions and Requirements

### Requirements

1. A node visit limit bounds the maximum number of times any node can be visited during dag cleaning.
2. A batch size bounds the maximum number of dirty nodes of the same role processed together in an agent session.
3. The dag config provides the node visit limit bounding node visits during graph cleaning.
4. The dag config provides the batch size bounding dirty nodes processed together in an agent session.

## Grounding Facts

### Knowledge Needed

- Node visit limit.
- Batch size limit.

### Actions Needed

- Provide node visit limit.
- Provide batch size limit.
