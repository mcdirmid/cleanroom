# update_with_ai_proto_ext external component

## Intent

Package directory message persistence uses a structured text format mapping node identifiers to their pending messages and known reverse dependencies. The update_with_ai_proto_ext external component encapsulates protobuf textproto record formats, kind annotations, and reverse dependency lists.

By defining deterministic text serialization and schema conventions for package records, the external boundary allows storage managers to persist node messages and reverse dependencies with human-readable formatting and robust error recovery.

## Factored Contracts

### Contracts

- A caller supplies a protobuf textproto formatted string when parsing package message data. [supply_proto_text]
- Protobuf text format organizes package data into node entries with node identifier strings, lists of pending messages carrying kind discriminators and payload text, and lists of reverse dependency target strings. [proto_text_schema]
- Protobuf text parsing decodes textproto files into structured entries. [parse_proto_text]
- Protobuf text serialization formats structured entries into canonical protobuf text representation with deterministic field ordering. [serialize_proto_text]
- Reading a missing textproto file treats the store as empty. [missing_textproto_empty]
- Reading corrupted textproto records applies safe recovery defaults. [corrupted_textproto_recovery]

## Woven Contracts

- When decoding a package message file, protobuf text is parsed into structured node entries, treating missing files as empty and applying safe defaults on corruption. [supply_proto_text, proto_text_schema, parse_proto_text, missing_textproto_empty, corrupted_textproto_recovery]
- When serializing package message records, structured node entries are converted into canonical protobuf text with deterministic field ordering. [proto_text_schema, serialize_proto_text]
