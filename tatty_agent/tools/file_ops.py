"""
File operations tools for TATty Agent

This module contains all file-related tools extracted from main.py:
- Read: Read file contents with optional offset and limit
- Edit: Edit files with string replacement
- MultiEdit: Apply multiple edits to a single file
- Write: Write content to files
"""
import os
from pathlib import Path

from ..baml_client import types
from .registry import register_tool


@register_tool("Read")
def execute_read(tool: types.ReadTool, working_dir: str = ".") -> str:
    """Read a file"""
    try:
        # If file_path is relative, make it relative to working_dir
        if not os.path.isabs(tool.file_path):
            path = Path(working_dir) / tool.file_path
        else:
            path = Path(tool.file_path)

        if not path.exists():
            return f"File not found: {tool.file_path}"

        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        total_lines = len(lines)
        start = tool.offset if tool.offset else 0
        end = start + tool.limit if tool.limit else len(lines)

        # Limit to 5000 lines per read
        max_lines = 5000
        if end - start > max_lines:
            end = start + max_lines

        result_lines = []
        for i, line in enumerate(lines[start:end], start=start + 1):
            # Truncate very long lines at 20k characters
            if len(line) > 20000:
                line = line[:20000] + "... [line truncated at 20k characters]\n"
            result_lines.append(f"{i:6d}|{line.rstrip()}")

        # Add truncation notice if we hit the limit
        if end < total_lines:
            remaining = total_lines - end
            truncation_notice = f"\n\n... [Output truncated: showing lines {start + 1}-{end} of {total_lines} total lines ({remaining} lines remaining)]\n"
            truncation_notice += f"To read more, use the Read tool with: offset={end}, limit={min(5000, remaining)}"
            result_lines.append(truncation_notice)

        return "\n".join(result_lines) if result_lines else "Empty file"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@register_tool("Edit")
def execute_edit(tool: types.EditTool, working_dir: str = ".") -> str:
    """Edit a file"""
    try:
        # If file_path is relative, make it relative to working_dir
        if not os.path.isabs(tool.file_path):
            path = Path(working_dir) / tool.file_path
        else:
            path = Path(tool.file_path)

        if not path.exists():
            return f"File not found: {tool.file_path}"

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        if tool.replace_all:
            new_content = content.replace(tool.old_string, tool.new_string)
            count = content.count(tool.old_string)
        else:
            if content.count(tool.old_string) > 1:
                return f"Error: old_string is not unique in file (found {content.count(tool.old_string)} occurrences)"
            new_content = content.replace(tool.old_string, tool.new_string, 1)
            count = 1 if tool.old_string in content else 0

        if count == 0:
            return "Error: old_string not found in file"

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return f"Successfully edited {tool.file_path} ({count} replacement(s))"
    except Exception as e:
        return f"Error editing file: {str(e)}"


@register_tool("MultiEdit")
def execute_multi_edit(tool: types.MultiEditTool, working_dir: str = ".") -> str:
    """Edit a file with multiple edits"""
    try:
        # If file_path is relative, make it relative to working_dir
        if not os.path.isabs(tool.file_path):
            path = Path(working_dir) / tool.file_path
        else:
            path = Path(tool.file_path)

        if not path.exists():
            return f"File not found: {tool.file_path}"

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Apply edits sequentially
        for i, edit in enumerate(tool.edits):
            if edit.replace_all:
                content = content.replace(edit.old_string, edit.new_string)
            else:
                if content.count(edit.old_string) > 1:
                    return f"Error in edit {i+1}: old_string is not unique (found {content.count(edit.old_string)} occurrences)"
                if edit.old_string not in content:
                    return f"Error in edit {i+1}: old_string not found"
                content = content.replace(edit.old_string, edit.new_string, 1)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

        return f"Successfully applied {len(tool.edits)} edits to {tool.file_path}"
    except Exception as e:
        return f"Error editing file: {str(e)}"


@register_tool("Write")
def execute_write(tool: types.WriteTool, working_dir: str = ".") -> str:
    """Write a file"""
    try:
        # If file_path is relative, make it relative to working_dir
        if not os.path.isabs(tool.file_path):
            path = Path(working_dir) / tool.file_path
        else:
            path = Path(tool.file_path)

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(tool.content)

        return f"Successfully wrote {tool.file_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"