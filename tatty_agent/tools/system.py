"""
System tools for TATty Agent

This module contains system-related tools extracted from main.py:
- Bash: Execute shell commands with timeout
- Glob: Find files matching glob patterns
- Grep: Search for patterns in files using ripgrep
- LS: List directory contents with filtering
"""
import subprocess
import os
import glob as glob_module
import fnmatch
from pathlib import Path

from ..baml_client import types
from .registry import register_tool


@register_tool("Bash")
def execute_bash(tool: types.BashTool, working_dir: str = ".") -> str:
    """Execute a bash command and return the output"""
    try:
        result = subprocess.run(
            tool.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=tool.timeout / 1000 if tool.timeout else 120,  # Convert ms to seconds
            cwd=working_dir
        )

        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR: {result.stderr}"
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"

        return output if output else "Command executed successfully (no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {tool.timeout}ms"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@register_tool("Glob")
def execute_glob(tool: types.GlobTool, working_dir: str = ".") -> str:
    """Find files matching a glob pattern"""
    try:
        search_path = tool.path if tool.path else working_dir
        pattern = os.path.join(search_path, tool.pattern) if not tool.pattern.startswith("**/") else tool.pattern

        matches = glob_module.glob(pattern, recursive=True)

        if not matches:
            return f"No files found matching pattern: {tool.pattern}"

        # Sort by modification time
        matches.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)

        # Normalize paths to be relative to working_dir
        working_dir_path = Path(working_dir).resolve()
        normalized_matches = []
        for match in matches[:50]:  # Limit to first 50 matches
            try:
                match_path = Path(match).resolve()
                # Try to make it relative to working_dir
                try:
                    relative_path = match_path.relative_to(working_dir_path)
                    normalized_matches.append(str(relative_path))
                except ValueError:
                    # If it can't be made relative, use the absolute path
                    normalized_matches.append(match)
            except Exception:
                # If there's any issue, just use the original path
                normalized_matches.append(match)

        return "\n".join(normalized_matches)
    except Exception as e:
        return f"Error executing glob: {str(e)}"


@register_tool("Grep")
def execute_grep(tool: types.GrepTool, working_dir: str = ".") -> str:
    """Search for pattern in files"""
    try:
        search_path = tool.path if tool.path else working_dir

        # Build rg command
        cmd = ["rg", tool.pattern, search_path, "--files-with-matches"]

        if tool.include:
            cmd.extend(["--glob", tool.include])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            files = result.stdout.strip().split("\n")

            # Normalize paths to be relative to working_dir
            working_dir_path = Path(working_dir).resolve()
            normalized_files = []
            for file in files[:50]:  # Limit to first 50 matches
                try:
                    file_path = Path(file).resolve()
                    # Try to make it relative to working_dir
                    try:
                        relative_path = file_path.relative_to(working_dir_path)
                        normalized_files.append(str(relative_path))
                    except ValueError:
                        # If it can't be made relative, use the absolute path
                        normalized_files.append(file)
                except Exception:
                    # If there's any issue, just use the original path
                    normalized_files.append(file)

            return "\n".join(normalized_files)
        elif result.returncode == 1:
            return f"No matches found for pattern: {tool.pattern}"
        else:
            return f"Error: {result.stderr}"
    except FileNotFoundError:
        # Fallback to Python's re if rg is not available
        return "Error: ripgrep (rg) not found. Please install ripgrep."
    except Exception as e:
        return f"Error executing grep: {str(e)}"


@register_tool("LS")
def execute_ls(tool: types.LSTool, working_dir: str = ".") -> str:
    """List files in a directory"""
    try:
        path = Path(tool.path) if tool.path else Path(working_dir)

        if not path.exists():
            return f"Directory not found: {tool.path}"

        if not path.is_dir():
            return f"Not a directory: {tool.path}"

        items = []
        for item in path.iterdir():
            # Skip ignored patterns
            if tool.ignore:
                skip = False
                for pattern in tool.ignore:
                    if fnmatch.fnmatch(item.name, pattern):
                        skip = True
                        break
                if skip:
                    continue

            item_type = "DIR " if item.is_dir() else "FILE"
            items.append(f"{item_type} {item.name}")

        items.sort()
        return "\n".join(items) if items else "Empty directory"
    except Exception as e:
        return f"Error listing directory: {str(e)}"