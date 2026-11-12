"""
## External Mechanics & API Documentation

The `kahn_topology_ext` external component provides algorithmic reference knowledge for deterministic topological sorting via Kahn's algorithm with priority-ordered max-heap selection, cycle path reconstruction, and critical path dynamic programming. External boundary specifications define no standalone library files; dependent components implement these mechanics directly or import the documented patterns.

**Topological Sorting Mechanics & Invariants**

- **In-Degree Calculation**:
  - In-degree of each node is the count of its upstream prerequisites within the registered nodes set.
- **Priority Queue Initialization**:
  - All nodes possessing in-degree zero are enqueued into a max-heap keyed by `(-priority, node_id)`.
  - Ties in priority are resolved by lexicographically ascending node identifier.
- **Deterministic Extraction**:
  - The highest-priority (and lexicographically smallest) ready node is popped from the heap and appended to the topological order sequence.
  - For each downstream dependent, its pending in-degree count decrements by one.
  - When a dependent's in-degree reaches zero, it enters the priority queue.
- **Cycle Detection & Path Reconstruction**:
  - If the extracted topological order contains fewer elements than the total registered node count, a directed dependency cycle exists.
  - Unplaced nodes (`remaining = set(nodes) - set(order)`) are traversed using depth-first search to isolate a back-edge and reconstruct the cyclic node sequence `(v1, v2, ..., v1)` for diagnostic `CycleError` reporting.

**Critical Path Dynamic Programming Mechanics**

- **Earliest Completion Accumulation**:
  - Nodes are evaluated along the precomputed topological order.
  - For each node, its earliest completion time is its duration weight plus the maximum earliest completion time among its upstream prerequisites (or zero if the node has no prerequisites).
- **Backtrack Reconstruction**:
  - During forward accumulation, each node records the upstream predecessor that yielded its maximum completion time.
  - The leaf node exhibiting the maximal completion time serves as the termination point.
  - The critical path sequence is reconstructed by backtracking along recorded predecessor links from the maximal leaf to a root node.

## Build Dependencies

(none)

## Usage Snippets

### `Deterministic Kahn's Topological Sort with Priority Heap and Cycle Tracing`

```python
import heapq
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

def kahn_topological_sort(
    nodes: Collection[str],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    priorities: Mapping[str, float],
    cycle_error_cls: type[Exception],
) -> List[str]:
    \"\"\"Computes deterministic topological ordering using Kahn's algorithm with max-heap priority queue.\"\"\"
    node_set = set(nodes)
    in_degree: Dict[str, int] = {nid: len(upstream.get(nid, set()) & node_set) for nid in node_set}

    heap: List[Tuple[float, str]] = []
    for nid in node_set:
        if in_degree[nid] == 0:
            heapq.heappush(heap, (-priorities.get(nid, 0.0), nid))

    order: List[str] = []
    while heap:
        neg_pri, nid = heapq.heappop(heap)
        order.append(nid)
        for dep_id in downstream.get(nid, set()):
            if dep_id in in_degree:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    heapq.heappush(heap, (-priorities.get(dep_id, 0.0), dep_id))

    if len(order) != len(node_set):
        remaining = node_set - set(order)
        visited_state: Dict[str, int] = {nid: 0 for nid in remaining}
        cycle_path: List[str] = []

        def dfs(curr: str, stack: List[str]) -> bool:
            visited_state[curr] = 1
            stack.append(curr)
            for nxt in downstream.get(curr, set()):
                if nxt in remaining:
                    if visited_state[nxt] == 1:
                        idx = stack.index(nxt)
                        cycle_path.extend(stack[idx:] + [nxt])
                        return True
                    if visited_state[nxt] == 0:
                        if dfs(nxt, stack):
                            return True
            stack.pop()
            visited_state[curr] = 2
            return False

        for nid in sorted(remaining):
            if visited_state[nid] == 0:
                if dfs(nid, []):
                    break

        raise cycle_error_cls(
            message=\"Cycle detected in DAG\",
            cycle=tuple(cycle_path) if cycle_path else tuple(sorted(remaining)),
        )

    return order
```

### `Critical Path Analysis via Topological Dynamic Programming`

```python
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

def compute_critical_path_dp(
    topological_order: Sequence[str],
    upstream: Mapping[str, Set[str]],
    durations: Optional[Mapping[str, float]] = None,
) -> Tuple[List[str], float]:
    \"\"\"Computes the longest weighted critical path through a DAG.\"\"\"
    if not topological_order:
        return [], 0.0

    earliest_finish: Dict[str, float] = {}
    best_parent: Dict[str, Optional[str]] = {}

    for nid in topological_order:
        dur = durations.get(nid, 1.0) if durations is not None else 1.0
        preds = upstream.get(nid, set())
        if not preds:
            earliest_finish[nid] = dur
            best_parent[nid] = None
        else:
            best_p = max(preds, key=lambda p: (earliest_finish.get(p, 0.0), p))
            earliest_finish[nid] = earliest_finish.get(best_p, 0.0) + dur
            best_parent[nid] = best_p

    max_leaf = max(topological_order, key=lambda n: (earliest_finish[n], n))
    max_duration = earliest_finish[max_leaf]

    path: List[str] = []
    curr: Optional[str] = max_leaf
    while curr is not None:
        path.append(curr)
        curr = best_parent.get(curr)
    path.reverse()

    return path, max_duration
```
"""

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-11-11T20:41:00Z
# LAST_CHANGED: 2026-11-11T20:41:00Z
# CHANGE: Grounding specification alignment for Kahn's topological sorting and critical path
# CODE_HASH: 000000000000
# SPEC_QA_AUDIT: 2026-11-11T20:41:00Z
# --- END CLEANROOM METADATA ---
