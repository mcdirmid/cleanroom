# file_reader

imports: tool_provider, virtual_file_name
types from tool_provider: tool, tool provider, tool result, tool failure
types from virtual_file_name: virtual file name

## Purpose

Provides safe, token-efficient workspace file inspection and path sanitization.

Agents require tools to locate and inspect files without exposing real host paths, leaking environment details, or making unanchored edits. File reader virtualizes file reading and pattern searching, sanitizing host paths in outputs into virtual file names. To ensure edit safety while conserving context, writable files are formatted with explicit line numbers for precise targeting, read-only references are presented plainly without formatting overhead, agents explicitly specify line-numbering intent when requesting file reads, and declared startup files are pre-injected to eliminate discovery turns.

## Types

- A *read-only file* is a file addressed by a *virtual file name* accessible for reading in plain content form
- A *read-write file* is a file addressed by a *virtual file name* accessible for reading in line-numbered form and modification
- A *file reader configuration* is a set of declared *read-only files*, *read-write files*, and host path mappings
- A *file read tool* is a *tool* that reads content from a *read-only file* or *read-write file* identified by a *virtual file name*
- A *file search tool* is a *tool* that searches file contents matching a pattern
- A *file reader* is a *tool provider* providing a *file read tool* and a *file search tool*
- A *file reader factory* is a provider that constructs *file readers* configured for specific sessions
- A *session-start read* is a *tool result* generated from a *read-only file* before the first agent turn

## Behavior

- A *file reader configuration* defines declared *read-only files*, declared *read-write files*, and mappings to host paths anchored to workspace roots.
- Creating a *file reader* through a *file reader factory* yields a *file reader* configured from a *file reader configuration*.
- A *file reader* provides a *file read tool* and a *file search tool* configured from a *file reader configuration*.
- Executing a *file read tool* with an unmapped or nonexistent *virtual file name* produces a *tool failure* listing all available *virtual file names*.
- Executing a *file read tool* on a guide configured for progressive step delivery produces a *tool failure* explaining that the guide is delivered progressively via advance execution.
- Executing a *file read tool* on a *read-write file* requires requesting line numbers and produces content with line numbers.
- Executing a *file read tool* on a *read-only file* requires omitting line numbers and produces plain content without line numbers.
- Executing a *file search tool* produces matching lines and locations within accessible files formatted with *virtual file names*.
- A *file reader* produces *session-start reads* for declared *read-only files*.
- Transforming text through a *file reader* replaces host paths with *virtual file names*.
