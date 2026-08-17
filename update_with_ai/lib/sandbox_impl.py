"""
Implementation of the LLS Sandbox interface.
"""

import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .sandbox import (
    VirtualName, Blame, SandboxConfig, WriteOccurred, Sandbox
)
from .tool_provider import (
    ToolDefinition,
    ToolResult,
    ToolCallOutcome,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
    ToolFailure,
)
from .dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult


# Stub replacement text
STUB_REPLACEMENT = "Content removed because newer version is available"


class SandboxImpl(Sandbox):
    """
    Implementation of the LLS Sandbox interface.
    
    Provides secure file system operations with stubbing semantics,
    policy enforcement, and state management per run.
    """
    
    def __init__(self, config: SandboxConfig):
        """
        Initialize the sandbox with configuration.
        
        Args:
            config: Configuration object containing file mappings, policies, etc.
        """
        self.config = config
        self.write_occurred: WriteOccurred = False
        
        # Precompute real->virtual path map so error messages can present
        # virtual names to the agent instead of absolute on-disk paths.
        self._real_to_virtual: Dict[str, str] = {}
        for virtual, real in self.config.file_mappings.items():
            if real:
                self._real_to_virtual.setdefault(real, virtual)
        # Longest paths first so a path that prefixes another is replaced
        # correctly (e.g. /pkg/foo.txt before /pkg/foo.txt.bak).
        self._real_paths_sorted: List[str] = sorted(
            self._real_to_virtual.keys(), key=len, reverse=True
        )
        
        # Per-run stubbing state
        self._read_regions: Dict[VirtualName, List[Tuple[int, int]]] = {}  # file -> [(offset, end)]
        self._chunk_reads: Dict[VirtualName, Set[int]] = {}  # file -> set of chunk indices
        self._searches: Set[Tuple[VirtualName, str]] = set()  # (path, pattern)
        
        # Validate Python accessibility
        self._python_accessible = self._check_python_access()
    
    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Return tool definitions based on configuration."""
        definitions = []
        
        # Always available
        definitions.extend([
            self._create_tool_definition(
                "read_file",
                "Read content from a file",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "offset": {"type": "integer", "description": "Starting position", "default": 0},
                    "limit": {"type": "integer", "description": "Maximum bytes to read"}
                }
            ),
            self._create_tool_definition(
                "write_file",
                "Write content to a file",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                }
            ),
            self._create_tool_definition(
                "search_files",
                "Search for a pattern in files",
                {
                    "path": {"type": "string", "description": "Virtual path to search"},
                    "pattern": {"type": "string", "description": "Regex pattern to search for"}
                }
            ),
            self._create_tool_definition(
                "succeed",
                "Signal successful termination",
                {}
            ),
            self._create_tool_definition(
                "fail",
                "Signal failed termination",
                {}
            )
        ])
        
        # Conditional: Python chunk tools
        if self._python_accessible:
            definitions.extend([
                self._create_tool_definition(
                    "read_chunks",
                    "Read semantic chunks from a Python file",
                    {
                        "file_path": {"type": "string", "description": "Virtual path to the Python file"},
                        "chunk_indices": {"type": "array", "items": {"type": "integer"}, "description": "Chunk indices to read"},
                        "include_adjacent": {"type": "boolean", "description": "Include neighboring chunks", "default": False}
                    }
                ),
                self._create_tool_definition(
                    "replace_chunks",
                    "Replace multiple chunks in a Python file atomically",
                    {
                        "file_path": {"type": "string", "description": "Virtual path to the Python file"},
                        "replacements": {"type": "array", "description": "List of replacements with 'index' and 'new_content'"},
                        "encoding": {"type": "string", "description": "Optional file encoding"}
                    }
                )
            ])
        
        # Conditional: verify
        if self.config.verification_callback is not None:
            definitions.append(
                self._create_tool_definition(
                    "verify",
                    "Run the verification callback",
                    {}
                )
            )
        
        # Conditional: blame
        if self.config.blame_targets:
            definitions.append(
                self._create_tool_definition(
                    "blame",
                    "Signal termination with blame: attribute the task's incompleteness to dependencies and provide feedback on how to correct their outputs",
                    {
                        "blames": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "target": {"type": "string", "description": "Target to blame (a dependency)"},
                                    "feedback": {"type": "string", "description": "Feedback on how to correct the target's output"}
                                },
                                "required": ["target", "feedback"],
                                "additionalProperties": False
                            },
                            "description": "Blame pairs (target, feedback), each delivered as a feedback message to its target"
                        }
                    }
                )
            )
        
        return definitions
    
    def read_file(self, file_path: VirtualName, offset: Optional[int] = None, 
                  limit: Optional[int] = None) -> ToolCallOutcome:
        """Read content from a file."""
        # Check if path exists in mappings first
        if file_path not in self.config.file_mappings:
            return self._error_response(
                f"File path '{file_path}' not found in mappings. "
                f"Files you can read: {self._readable_list()}"
            )
        
        # Then check readability
        if file_path not in self.config.readable_paths:
            return self._error_response(
                f"File path '{file_path}' is not readable. "
                f"Files you can read: {self._readable_list()}"
            )
        
        # Validate parameters
        if offset is not None and offset < 0:
            return self._error_response("Offset must be non-negative")
        if limit is not None and limit <= 0:
            return self._error_response("Limit must be positive")
        
        # Resolve path
        real_path = self.config.file_mappings[file_path]
        if not os.path.exists(real_path):
            return self._error_response(f"File '{real_path}' does not exist")
        if not os.path.isfile(real_path):
            return self._error_response(f"Path '{real_path}' is not a file")
        
        # Read file
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                if offset is None:
                    offset = 0
                f.seek(offset)
                if limit is None:
                    limit = self.config.read_size_limit
                content = f.read(limit)
        except Exception as e:
            return self._error_response(f"Error reading file: {str(e)}")
        
        # Determine stubbing
        end = offset + len(content)
        should_stub = self._should_stub_read(file_path, offset, end)
        if should_stub:
            content = STUB_REPLACEMENT
        
        # Update state
        if not should_stub:
            self._read_regions.setdefault(file_path, []).append((offset, end))
        
        result = ToolResult(
            content=content,
            content_id=file_path,
            stub_previous=should_stub
        )
        return result
    
    def write_file(self, file_path: VirtualName, content: str) -> ToolCallOutcome:
        """Write content to a file."""
        # Check if path exists in mappings first
        if file_path not in self.config.file_mappings:
            return self._error_response(
                f"File path '{file_path}' not found in mappings. "
                f"Files you can write: {self._writable_list()}"
            )
        
        # Then check writability
        if file_path not in self.config.writable_paths:
            return self._error_response(
                f"File path '{file_path}' is not writable. "
                f"Files you can write: {self._writable_list()}"
            )
        
        if not content:
            return self._error_response("Content must be non-empty")
        
        # Resolve path
        real_path = self.config.file_mappings[file_path]
        
        # Ensure directory exists (skip for bare filenames with no directory)
        parent_dir = os.path.dirname(real_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        
        # Write file
        try:
            with open(real_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            return self._error_response(f"Error writing file: {str(e)}")
        
        # Update state
        self.write_occurred = True
        # Clear read regions for this file since it was modified
        self._read_regions.pop(file_path, None)
        self._chunk_reads.pop(file_path, None)
        # Clear search deduplication for this file
        self._searches = {(p, pat) for (p, pat) in self._searches if p != file_path}
        
        result = ToolResult(
            content="",
            content_id=file_path,
            stub_previous=True
        )
        return result
    
    def search_files(self, path: VirtualName, pattern: str) -> ToolCallOutcome:
        """Search for a pattern in files."""
        # Check if path exists in mappings first
        if path not in self.config.file_mappings:
            return self._error_response(
                f"File path '{path}' not found in mappings. "
                f"Files you can read: {self._readable_list()}"
            )
        
        # Then check readability
        if path not in self.config.readable_paths:
            return self._error_response(
                f"Path '{path}' is not readable. "
                f"Files you can read: {self._readable_list()}"
            )
        
        try:
            re.compile(pattern)
        except re.error as e:
            return self._error_response(f"Invalid regex pattern: {str(e)}")
        
        # Resolve path
        real_path = self.config.file_mappings[path]
        if not os.path.exists(real_path):
            return self._error_response(f"Path '{real_path}' does not exist")
        
        # Determine stubbing
        search_key = (path, pattern)
        should_stub = search_key in self._searches
        
        # Perform search
        if should_stub:
            content = STUB_REPLACEMENT
        else:
            try:
                results = self._perform_search(real_path, pattern)
                # Limit results
                if len(results) > self.config.search_result_limit:
                    results = results[:self.config.search_result_limit]
                content = "\n".join(results)
            except Exception as e:
                return self._error_response(f"Error searching: {str(e)}")
        
        # Update state
        if not should_stub:
            self._searches.add(search_key)
        
        result = ToolResult(
            content=content,
            content_id=path,
            stub_previous=should_stub
        )
        return result
    
    def read_chunks(self, file_path: VirtualName, 
                    chunk_indices: Optional[List[int]] = None,
                    include_adjacent: bool = False) -> ToolCallOutcome:
        """Read semantic chunks from a Python file."""
        # Validate Python accessibility
        if not self._python_accessible:
            return self._error_response("Python files are not accessible")
        
        # Validate file
        if file_path not in self.config.file_mappings:
            return self._error_response(
                f"File path '{file_path}' not found in mappings. "
                f"Files you can read: {self._readable_list()}"
            )
        if file_path not in self.config.readable_paths:
            return self._error_response(
                f"File path '{file_path}' is not readable. "
                f"Files you can read: {self._readable_list()}"
            )
        
        real_path = self.config.file_mappings[file_path]
        if not real_path.endswith('.py'):
            return self._error_response(f"File '{file_path}' is not a Python file")
        if not os.path.exists(real_path):
            return self._error_response(f"File '{real_path}' does not exist")

        # Parse Python file into chunks
        try:
            chunks = self._parse_python_chunks(real_path)
        except Exception as e:
            return self._error_response(f"Error parsing Python file: {str(e)}")

        # Validate requested chunk indices: per the sandbox LLS they must be
        # valid non-negative indices; an out-of-range index is a parameter
        # error (unlike replace_chunks' neighbors, no index is silently dropped).
        if chunk_indices is not None:
            for idx in chunk_indices:
                if idx < 0 or idx >= len(chunks):
                    return self._error_response(
                        f"Chunk index {idx} out of range (max: {len(chunks)-1})"
                    )

        if not chunks:
            # Empty file returns empty content
            result = ToolResult(
                content="",
                content_id=file_path,
                stub_previous=False
            )
            return result
        
        # Determine which chunks to return
        if chunk_indices is None:
            indices_to_read = set(range(len(chunks)))
        else:
            indices_to_read = set(chunk_indices)
            if include_adjacent:
                for idx in chunk_indices:
                    if idx > 0:
                        indices_to_read.add(idx - 1)
                    if idx < len(chunks) - 1:
                        indices_to_read.add(idx + 1)
        
        # Determine stubbing
        should_stub = self._should_stub_chunks(file_path, indices_to_read)
        
        if should_stub:
            content = STUB_REPLACEMENT
        else:
            # Build result
            result_lines = []
            for idx in sorted(indices_to_read):
                if idx < len(chunks):
                    result_lines.append(f"--- Chunk {idx} ---")
                    result_lines.append(chunks[idx])
            content = "\n".join(result_lines)
            
            # Update state
            self._chunk_reads.setdefault(file_path, set()).update(indices_to_read)
        
        result = ToolResult(
            content=content,
            content_id=file_path,
            stub_previous=should_stub
        )
        return result
    
    def replace_chunks(self, file_path: VirtualName, replacements: List[Dict],
                       encoding: Optional[str] = None) -> ToolCallOutcome:
        """Replace multiple chunks in a Python file atomically."""
        # Validate Python accessibility
        if not self._python_accessible:
            return self._error_response("Python files are not accessible")
        
        # Validate file
        if file_path not in self.config.file_mappings:
            return self._error_response(
                f"File path '{file_path}' not found in mappings. "
                f"Files you can write: {self._writable_list()}"
            )
        if file_path not in self.config.writable_paths:
            return self._error_response(
                f"File path '{file_path}' is not writable. "
                f"Files you can write: {self._writable_list()}"
            )
        
        real_path = self.config.file_mappings[file_path]
        if not real_path.endswith('.py'):
            return self._error_response(f"File '{file_path}' is not a Python file")
        if not os.path.exists(real_path):
            return self._error_response(f"File '{real_path}' does not exist")
        
        # Validate replacements
        if not replacements:
            return self._error_response("Replacements list must not be empty")
        for r in replacements:
            if 'index' not in r or 'new_content' not in r:
                return self._error_response("Each replacement must have 'index' and 'new_content'")
            if not isinstance(r['index'], int) or r['index'] < 0:
                return self._error_response("Each replacement index must be a non-negative integer")
        
        # Parse file
        try:
            chunks = self._parse_python_chunks(real_path)
        except Exception as e:
            return self._error_response(f"Error parsing Python file: {str(e)}")
        
        if not chunks:
            return self._error_response("Cannot replace chunks in empty file")
        
        # Validate indices
        for r in replacements:
            if r['index'] >= len(chunks):
                return self._error_response(f"Chunk index {r['index']} out of range (max: {len(chunks)-1})")
        
        # Apply replacements (atomic)
        try:
            for r in replacements:
                chunks[r['index']] = r['new_content']
            
            # Reconstruct file content
            new_content = "\n".join(chunks) + "\n"
            
            # Write file
            with open(real_path, 'w', encoding=encoding or 'utf-8') as f:
                f.write(new_content)
        except Exception as e:
            return self._error_response(f"Error writing file: {str(e)}")
        
        # Update state
        self.write_occurred = True
        self._read_regions.pop(file_path, None)
        self._chunk_reads.pop(file_path, None)
        # Clear search deduplication for this file
        self._searches = {(p, pat) for (p, pat) in self._searches if p != file_path}
        
        result = ToolResult(
            content="",
            content_id=file_path,
            stub_previous=True
        )
        return result
    
    def verify(self) -> ToolCallOutcome:
        """Run the verification callback."""
        if self.config.verification_callback is None:
            return ToolFailure[str]("Verification callback is not configured")
        
        try:
            result = self.config.verification_callback()
        except Exception as e:
            return ToolFailure[str](f"Verification error: {str(e)}")
        
        return ToolResult(
            content=result,
            content_id="verify",
            stub_previous=True
        )
    
    def succeed(self) -> ToolCallOutcome:
        """Signal successful termination."""
        if self.write_occurred:
            return TerminateAgentWithSuccess(
                ChangeResult(messages=["Task completed successfully"])
            )
        return TerminateAgentWithSuccess(NoChangeResult())
    
    def fail(self) -> ToolCallOutcome:
        """End the session in failure (agent failure)."""
        return TerminateAgentWithFailure[str]("Task failed")
    
    def blame(self, blames: List[Blame]) -> ToolCallOutcome:
        """Signal termination with blame: attribute the task's incompleteness to dependencies and provide feedback on how to correct their outputs."""
        if not self.config.blame_targets:
            return ToolFailure[str]("Blame targets are not configured")
        
        if not blames:
            return ToolFailure[str]("Blame list must not be empty")
        
        invalid_blames = [(t, f) for (t, f) in blames if t not in self.config.blame_targets]
        if invalid_blames:
            return ToolFailure[str](f"Blame assignment rejected for: {invalid_blames}")
        
        return TerminateAgentWithSuccess(FeedbackResult(messages=blames))
    
    def get_write_occurred(self) -> WriteOccurred:
        """Return whether the agent has modified the filesystem during the current run."""
        return self.write_occurred
    
    # Helper methods
    
    def _create_tool_definition(self, name: str, description: str, 
                                parameters: Dict[str, Any]) -> ToolDefinition:
        """Create a tool definition in OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    "additionalProperties": False
                },
            },
        }
    
    def _error_response(self, error_message: str) -> ToolFailure[str]:
        """Create a ToolFailure response for a policy or parameter violation."""
        return ToolFailure[str](self._virtualize_paths(error_message))
    
    def _readable_list(self) -> str:
        """Comma-separated list of virtual file names the agent may read."""
        return ", ".join(sorted(set(self.config.readable_paths)))
    
    def _writable_list(self) -> str:
        """Comma-separated list of virtual file names the agent may write."""
        return ", ".join(sorted(set(self.config.writable_paths)))
    
    def _virtualize_paths(self, message: str) -> str:
        """
        Replace real on-disk paths in a message with their virtual names.

        The agent only ever sees virtual file names (e.g. 'foo.txt'), so error
        text that embeds the resolved absolute path (like "File '/Users/.../
        tests/example/foo.txt' does not exist") is rewritten to use the
        virtual name ('foo.txt') before being returned to the agent.
        """
        for real_path in self._real_paths_sorted:
            if real_path in message:
                message = message.replace(real_path, self._real_to_virtual[real_path])
        return message
    
    def _should_stub_read(self, file_path: VirtualName, offset: int, end: int) -> bool:
        """Determine if a read should be stubbed based on region overlap."""
        if file_path not in self._read_regions:
            return False
        
        for prev_offset, prev_end in self._read_regions[file_path]:
            if offset < prev_end and end > prev_offset:
                return True
        return False
    
    def _should_stub_chunks(self, file_path: VirtualName, 
                           indices: Set[int]) -> bool:
        """Determine if chunk reads should be stubbed based on overlap."""
        if file_path not in self._chunk_reads:
            return False
        
        return bool(indices & self._chunk_reads[file_path])
    
    def _perform_search(self, path: str, pattern: str) -> List[str]:
        """Perform a recursive search for pattern in files."""
        results = []
        pattern_re = re.compile(pattern)
        
        if os.path.isfile(path):
            # Search a single file
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern_re.search(line):
                            results.append(f"{os.path.basename(path)}:{line_num}: {line.strip()}")
            except (UnicodeDecodeError, PermissionError):
                pass
        else:
            # Search directory recursively
            for root, dirs, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            for line_num, line in enumerate(f, 1):
                                if pattern_re.search(line):
                                    rel_path = os.path.relpath(file_path, path)
                                    results.append(f"{rel_path}:{line_num}: {line.strip()}")
                    except (UnicodeDecodeError, PermissionError, IsADirectoryError):
                        continue
        
        return results
    
    def _check_python_access(self) -> bool:
        """Check if Python files are accessible."""
        for virtual_path, real_path in self.config.file_mappings.items():
            if real_path.endswith('.py') and virtual_path in self.config.readable_paths:
                return True
        return False
    
    def _parse_python_chunks(self, file_path: str) -> List[str]:
        """Parse a Python file into semantic chunks (top-level constructs)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not content.strip():
            return []
        
        # Parse by top-level constructs (class/function definitions)
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        
        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            # Check if this is a top-level definition (indent 0 and not empty/comment)
            is_top_level = (indent == 0 and stripped and not stripped.startswith('#'))
            
            if is_top_level and current_chunk:
                # Save current chunk and start a new one
                if any(c.strip() for c in current_chunk):
                    chunks.append('\n'.join(current_chunk))
                current_chunk = []
            
            current_chunk.append(line)
        
        # Add the last chunk
        if current_chunk and any(c.strip() for c in current_chunk):
            chunks.append('\n'.join(current_chunk))
        
        return chunks