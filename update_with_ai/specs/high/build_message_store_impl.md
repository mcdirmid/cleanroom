# build_message_store_impl

fulfills: build_message_store
imports: dag_storage (node, message, message kind, pending message, reverse dependency), build_graph_storage (package directory)
terms (from build_message_store): package message data, textproto format
terms (from dag_storage): node, message, message kind, pending message, reverse dependency
terms (from build_graph_storage): package directory

## Deltas

- Serializes and deserializes the `.update_with_ai.textproto` file using standard protobuf text-format quoting and escaping.
- Manages in-package `.update_with_ai.textproto` files directly on disk.

## Non-concerns

- Serialization indentation spacing: implementation detail.
