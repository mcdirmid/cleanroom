# update_with_ai_proto_ext external component

## Purpose

The update_with_ai_proto_ext external component specifies the external protobuf text-format schema for storing package message data in `.update_with_ai.textproto` files.

Package directory message persistence uses a structured text format mapping node identifiers to their pending messages and known reverse dependencies. The update_with_ai_proto_ext external component encapsulates protobuf textproto record formats, kind annotations, and reverse dependency lists.

**Out of scope:** The update_with_ai_proto_ext external component does not resolve package directories, evaluate node dirty states, or execute cleaning passes; these are handled by other components.

## Grounding Gaps Covered

The update_with_ai_proto_ext component provides the external domain knowledge and protobuf serialization mechanics required to store and retrieve package-level message records:

- Protobuf text format schema: Defines the message record structure used in `.update_with_ai.textproto` files, organizing package data into node entries with node identifier strings, lists of pending messages carrying kind discriminators and payload text, and lists of reverse dependency target strings.

- Protobuf text serialization and deserialization: Parses human-readable protobuf textproto files into structured entries, formats structured entries back into canonical protobuf text representation, and ensures deterministic field ordering during serialization.

- Textproto file persistence and error tolerance: Reads and writes `.update_with_ai.textproto` files in package directories on the filesystem, treats missing textproto files as empty stores, and handles syntax errors or corrupted textproto records with safe recovery defaults.
