# update_with_ai_proto_ext

imports: dag_storage
types from dag_storage: node, message, pending message, reverse dependency

## Purpose

Specifies the external protobuf text-format schema for storing package message data in .update_with_ai.textproto files.

Package directory message persistence uses a structured text format mapping node identifiers to their pending messages and known reverse dependencies. The external format defines message record fields, kind annotations, and reverse dependency lists.

## Types

- A *proto message* is an external textproto message record with a kind discriminator and text payload
- A *proto node entry* is an external textproto record containing pending *messages* and *reverse dependencies* for a *node*
- A *proto package store* is a collection of *proto node entries* serialized to a package textproto file

## Behavior

- A *proto package store* serializes *nodes*, *pending messages*, and *reverse dependencies* to protobuf text format.
- A *proto package store* deserializes protobuf text format into *nodes*, *pending messages*, and *reverse dependencies*.
