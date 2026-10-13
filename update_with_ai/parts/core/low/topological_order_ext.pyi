# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:15Z
# LAST_CHANGED: 2026-10-10T19:16:19Z
# CHANGE: new file
# CODE_HASH: 7cae80fadeff
# --- END CLEANROOM METADATA ---

"""
## External Mechanics & API Documentation

The `topological_order_ext` external component specifies deterministic dependency-first ordering mechanics for declared dependency graphs. External boundary specifications define no standalone library files; dependent components implement the algorithm directly or import the external boundary implementation as documented here.

**Ordering Mechanics**

- **Input**: a set of items identified by name, and a mapping from each item name to the names of the items it depends on.
- **Traversal**: depth-first post-order. An item is emitted after the post-order visits of its dependencies.
- **Dependency Traversal Order**: the dependencies of an item are visited in lexical order of their names.
- **Root Order**: items are started in lexical order of their names.
- **Undeclared Dependencies**: a dependency naming an item outside the input set is ignored.
- **Cycle Rule**: a dependency naming an item currently on the traversal stack is not followed, so a cycle closes by omission of the closing edge; ordering terminates and each item is emitted exactly once.
- **Determinism**: the emitted sequence is a pure function of the item set and the dependency mapping.

## Build Dependencies

(none)

## Usage Snippets

### `Ordering items by their declared dependencies`

```python
def dependency_order(items, dependencies):
    \"\"\"Returns items in dependency-first order, lexical on ties.\"\"\"
    available = {name: item for name, item in items}
    visited, on_stack, order = set(), set(), []

    def visit(name):
        if name in visited or name in on_stack:
            return
        on_stack.add(name)
        for dep in sorted(dependencies.get(name, [])):
            if dep in available:
                visit(dep)
        on_stack.discard(name)
        visited.add(name)
        order.append(available[name])

    for name in sorted(available):
        visit(name)
    return order
```
"""
