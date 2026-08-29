<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - build_graph_storage.md
-->

# Interface LLS: build_message_store

## Data Types
```python
from typing import Dict, List, Optional, Protocol, Tuple, TypeAlias
from dag_storage import NodeId, NodeMessage, PendingMessages, KnownReverseDependencies
from build_graph_storage import PackageDirectory

PackageMessageData: TypeAlias = Dict[NodeId, Tuple[PendingMessages, KnownReverseDependencies]]

class BuildMessageStore(Protocol):
    def read_package_messages(self, package_dir: PackageDirectory) -> PackageMessageData: ...
    def write_package_messages(self, package_dir: PackageDirectory, data: PackageMessageData) -> None: ...
    def get_pending_messages(self, package_dir: PackageDirectory, node: NodeId) -> PendingMessages: ...
    def add_pending_message(self, package_dir: PackageDirectory, node: NodeId, message: NodeMessage) -> None: ...
    def set_pending_messages(self, package_dir: PackageDirectory, node: NodeId, messages: PendingMessages) -> None: ...
    def clear_pending_messages(self, package_dir: PackageDirectory, node: NodeId) -> None: ...
    def delete_node_messages(self, package_dir: PackageDirectory, node: NodeId) -> None: ...
    def get_known_reverse_dependencies(self, package_dir: PackageDirectory, node: NodeId) -> KnownReverseDependencies: ...
    def add_known_reverse_dependency(self, package_dir: PackageDirectory, node: NodeId, reverse_dep: NodeId) -> None: ...
    def clear_known_reverse_dependencies(self, package_dir: PackageDirectory, node: NodeId) -> None: ...
```

## Term definitions

- **package message data** → the `PackageMessageData` alias (definition in Data Types)
- **textproto format** → term definition: the serialized protobuf text format encoding package message data according to the update_with_ai schema
- **node** → the `NodeId` alias from dag_storage
- **message** → the `NodeMessage` dataclass from dag_storage
- **message kind** → the `MessageKind` alias from dag_storage
- **pending message** → the `PendingMessages` alias from dag_storage
- **reverse dependency** → the `KnownReverseDependencies` alias from dag_storage
- **package directory** → the `PackageDirectory` alias from build_graph_storage

## Component-Provided Operations

### `read_package_messages`

```python
def read_package_messages(self, package_dir: PackageDirectory) -> PackageMessageData
```

**Purpose:** Read the stored node message data from the package directory's message file.

**Preconditions:** None.

**Postconditions:**
- Returns the mapping of node IDs to their pending messages and known reverse dependencies.
- Missing files return an empty dictionary.

**Failure Handling:** Invalid or corrupt files return empty dictionary.

**HLS Justification:** "Read pending messages for a node from its package directory."

### `write_package_messages`

```python
def write_package_messages(self, package_dir: PackageDirectory, data: PackageMessageData) -> None
```

**Purpose:** Write the package message data to the package directory's message file.

**Preconditions:** None.

**Postconditions:**
- Serializes data into `.update_with_ai.textproto` in the package directory.

**Failure Handling:** Filesystem write errors are unhandled.

**HLS Justification:** "Add or set pending messages for a node."

### `get_pending_messages`

```python
def get_pending_messages(self, package_dir: PackageDirectory, node: NodeId) -> PendingMessages
```

**Purpose:** Retrieve the pending messages for a specific node in a package directory.

**Preconditions:** None.

**Postconditions:**
- Returns the list of pending `NodeMessage` objects for the node.

**Failure Handling:** Missing node entries return an empty list.

**HLS Justification:** "Read pending messages for a node from its package directory."

### `add_pending_message`

```python
def add_pending_message(self, package_dir: PackageDirectory, node: NodeId, message: NodeMessage) -> None
```

**Purpose:** Append a pending message to a node's entry in its package message file.

**Preconditions:** None.

**Postconditions:**
- The message is appended to the node's pending messages on disk.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Add or set pending messages for a node."

### `set_pending_messages`

```python
def set_pending_messages(self, package_dir: PackageDirectory, node: NodeId, messages: PendingMessages) -> None
```

**Purpose:** Replace a node's pending messages list on disk.

**Preconditions:** None.

**Postconditions:**
- The node's pending messages are replaced with the supplied list.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Add or set pending messages for a node."

### `clear_pending_messages`

```python
def clear_pending_messages(self, package_dir: PackageDirectory, node: NodeId) -> None
```

**Purpose:** Clear a node's pending messages list while preserving its reverse dependencies.

**Preconditions:** None.

**Postconditions:**
- The node's pending messages are emptied on disk.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Clear a node's pending messages or delete a node's entry."

### `delete_node_messages`

```python
def delete_node_messages(self, package_dir: PackageDirectory, node: NodeId) -> None
```

**Purpose:** Remove a node's entry completely from the package message file.

**Preconditions:** None.

**Postconditions:**
- The node's entry is removed from the file.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Clear a node's pending messages or delete a node's entry."

### `get_known_reverse_dependencies`

```python
def get_known_reverse_dependencies(self, package_dir: PackageDirectory, node: NodeId) -> KnownReverseDependencies
```

**Purpose:** Retrieve the known reverse dependencies recorded for a node.

**Preconditions:** None.

**Postconditions:**
- Returns the list of recorded reverse dependency node IDs.

**Failure Handling:** Missing node entries return an empty list.

**HLS Justification:** "Read, add, or clear known reverse dependencies for a node."

### `add_known_reverse_dependency`

```python
def add_known_reverse_dependency(self, package_dir: PackageDirectory, node: NodeId, reverse_dep: NodeId) -> None
```

**Purpose:** Record a reverse dependency for a node in its package message file.

**Preconditions:** None.

**Postconditions:**
- `reverse_dep` is added to the node's known reverse dependencies (deduped).

**Failure Handling:** Always succeeds.

**HLS Justification:** "Read, add, or clear known reverse dependencies for a node."

### `clear_known_reverse_dependencies`

```python
def clear_known_reverse_dependencies(self, package_dir: PackageDirectory, node: NodeId) -> None
```

**Purpose:** Clear all recorded reverse dependencies for a node.

**Preconditions:** None.

**Postconditions:**
- The node's known reverse dependencies list is emptied.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Read, add, or clear known reverse dependencies for a node."

## Invariants

- Message kinds are preserved across read and write.
- Atomic serialization ensures file integrity.

## Non-Concerns

- In-memory caching: the message store operates directly on filesystem package data.
