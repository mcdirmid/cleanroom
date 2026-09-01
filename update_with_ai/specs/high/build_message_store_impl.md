# build_message_store_impl

imports: dag_storage, node_id_utils, build_message_store, update_with_ai_proto_ext
types from dag_storage: dag storage, node, message, pending message, reverse dependency
types from node_id_utils: node identifier utility, node directory
types from build_message_store: build message store
types from update_with_ai_proto_ext: proto package store, proto node entry, proto message
implements: build message store

## Purpose

Persists node pending messages and reverse dependencies using per-package protobuf text-format files.

## Behavior

- A *build message store* serializes *pending messages* and *reverse dependencies* into protobuf text format files using *proto package store*.
- All *nodes* defined in the same package directory share a common package message file.
