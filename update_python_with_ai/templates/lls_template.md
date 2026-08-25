<!-- Dependencies (md files to read alongside this one):
  - <dep>-low.md
-->

# Interface LLS: <name>

## Data Types
```python
<TODO: imports, type aliases, and classes; the interface's Protocol class last>
```

<TODO: prose explaining each type follows the block>

## Component-Provided Operations

### `operation_name`

```python
def operation_name(self, param: Type) -> ReturnType: ...
```

**Purpose:** <TODO: what the operation does.>
**Preconditions:** <TODO: conditions that must be true before calling.>
**Postconditions:** <TODO: state changes, return semantics, ordering, routing, guarantees — declarative.>
**Failure Handling:** <TODO: expected failures as return-value signals; unexpected failures not documented.>
**HLS Justification:** <TODO: brief phrase traceable to the HLS closure.>

## Invariants

- <TODO: properties that hold across all operations>

# Implementation LLS: <name>      # only when an implementation HLS exists

## Data Types
```python
class <Name>Impl(<Name>): ...
```

<TODO: implementation class; configuration as __init__ parameters>

## Composition            # only for assembler implementations

- <TODO: wired concrete implementations, names only>

## Behavioral Description

- <TODO: how the implementation fulfills the interface contract; outcomes, not mechanisms>

## Invariants

- <TODO: implementation-wide invariants>

## Non-Concerns

- **<Aspect>:** <TODO: pinned choice — justification.>

<!--
TODO: work through this template section by section per update_python_with_ai/guides/high_to_low.md:
  - the LLS inlines the full HLS closure; every statement traces to the HLS
  - replace every TODO marker; keep the template's required structure
  - remove this comment block when the document is complete
-->
