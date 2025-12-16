import asyncio
import subprocess
import os
import glob as glob_module
import fnmatch
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

from baml_client import types

# In-memory storage for todos
_todo_store: list[types.TodoItem] = []


def is_interrupted() -> bool:
    """Check if agent execution has been interrupted"""
    try:
        from agent_runtime import AgentRuntime
        if hasattr(AgentRuntime, '_current_state') and AgentRuntime._current_state:
            return AgentRuntime._current_state.interrupt_requested
    except:
        pass
    return False


async def run_interruptible_subprocess(cmd, timeout=120, **kwargs):
    """Run subprocess with interrupt checking for long-running commands"""
    if is_interrupted():
        return subprocess.CompletedProcess(cmd, 130, "", "Process interrupted by user")

    try:
        # For shorter commands, just run normally
        if timeout <= 10:
            return subprocess.run(cmd, timeout=timeout, **kwargs)

        # For longer commands, check for interrupts periodically
        process = subprocess.Popen(cmd, **kwargs)

        # Check every 0.5 seconds for interrupt
        check_interval = 0.5
        elapsed = 0

        while process.poll() is None and elapsed < timeout:
            if is_interrupted():
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                return subprocess.CompletedProcess(cmd, 130, "", "Process interrupted by user")

            await asyncio.sleep(check_interval)
            elapsed += check_interval

        if process.poll() is None:
            # Timeout reached
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
            raise subprocess.TimeoutExpired(cmd, timeout)

        stdout, stderr = process.communicate()
        return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)

    except Exception as e:
        raise e


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


def execute_notebook_read(tool: types.NotebookReadTool, working_dir: str = ".") -> str:
    """Read a Jupyter notebook"""
    try:
        import json
        # If notebook_path is relative, make it relative to working_dir
        if not os.path.isabs(tool.notebook_path):
            path = Path(working_dir) / tool.notebook_path
        else:
            path = Path(tool.notebook_path)
        
        if not path.exists():
            return f"Notebook not found: {tool.notebook_path}"
        
        with open(path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        cells_output = []
        for i, cell in enumerate(notebook.get('cells', [])):
            cell_type = cell.get('cell_type', 'unknown')
            source = ''.join(cell.get('source', []))
            cells_output.append(f"Cell {i} ({cell_type}):\n{source}\n")
        
        return "\n".join(cells_output) if cells_output else "Empty notebook"
    except Exception as e:
        return f"Error reading notebook: {str(e)}"


def execute_notebook_edit(tool: types.NotebookEditTool, working_dir: str = ".") -> str:
    """Edit a Jupyter notebook cell"""
    try:
        import json
        # If notebook_path is relative, make it relative to working_dir
        if not os.path.isabs(tool.notebook_path):
            path = Path(working_dir) / tool.notebook_path
        else:
            path = Path(tool.notebook_path)
        
        if not path.exists():
            return f"Notebook not found: {tool.notebook_path}"
        
        with open(path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        cells = notebook.get('cells', [])
        
        if tool.edit_mode == "delete":
            if 0 <= tool.cell_number < len(cells):
                cells.pop(tool.cell_number)
            else:
                return f"Error: cell index {tool.cell_number} out of range"
        elif tool.edit_mode == "insert":
            if not tool.cell_type:
                return "Error: cell_type is required for insert mode"
            new_cell = {
                'cell_type': tool.cell_type,
                'source': tool.new_source.split('\n'),
                'metadata': {}
            }
            cells.insert(tool.cell_number, new_cell)
        else:  # replace
            if 0 <= tool.cell_number < len(cells):
                cells[tool.cell_number]['source'] = tool.new_source.split('\n')
                if tool.cell_type:
                    cells[tool.cell_number]['cell_type'] = tool.cell_type
            else:
                return f"Error: cell index {tool.cell_number} out of range"
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=2)
        
        return f"Successfully edited notebook {tool.notebook_path}"
    except Exception as e:
        return f"Error editing notebook: {str(e)}"


def execute_web_fetch(tool: types.WebFetchTool, working_dir: str = ".") -> str:
    """Fetch and process web content"""
    try:
        import requests  # type: ignore
        from bs4 import BeautifulSoup  # type: ignore
        
        response = requests.get(tool.url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        text = soup.get_text()
        
        # Simple markdown conversion (just cleaning up whitespace)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        markdown_content = '\n'.join(lines)

        # TODO: call haiku to summarize the content given the query and how its related.
        
        # Truncate if too long
        truncation_message = ""
        if len(markdown_content) > 10000:
            markdown_content = markdown_content[:10000] + "\n... [truncated]"
            truncation_message = "if you need more information, call the WebFetch tool again to get the rest of the content with a file path"
        
        return f"Content from {tool.url}:\n\n{markdown_content}\n\nUser prompt: {tool.prompt}\n\n{truncation_message}".strip()
    except ImportError:
        return "Error: requests and beautifulsoup4 packages are required for web fetching. Install with: pip install requests beautifulsoup4"
    except Exception as e:
        return f"Error fetching web content: {str(e)}"


def execute_todo_read(tool: types.TodoReadTool, working_dir: str = ".") -> str:
    """Read the todo list from in-memory storage"""
    global _todo_store
    
    if not _todo_store:
        return "No todos currently tracked"
    
    todo_summary = []
    for todo in _todo_store:
        status_icon = "✓" if todo.status == "completed" else "→" if todo.status == "in_progress" else "○"
        todo_summary.append(f"{status_icon} [{todo.priority}] {todo.content} (id: {todo.id}, status: {todo.status})")
    
    return f"Current todos ({len(_todo_store)}):\n" + "\n".join(todo_summary)


def execute_todo_write(tool: types.TodoWriteTool, working_dir: str = ".") -> str:
    """Write the todo list to in-memory storage"""
    global _todo_store
    
    # Replace entire todo list with new one
    _todo_store = tool.todos
    
    todo_summary = []
    for todo in tool.todos:
        status_icon = "✓" if todo.status == "completed" else "→" if todo.status == "in_progress" else "○"
        todo_summary.append(f"{status_icon} [{todo.priority}] {todo.content} (id: {todo.id})")
    
    return f"Updated {len(tool.todos)} todos:\n" + "\n".join(todo_summary)


def execute_web_search(tool: types.WebSearchTool, working_dir: str = ".") -> str:
    """Search the web using DuckDuckGo search"""
    try:
        from ddgs import DDGS

        # Initialize DuckDuckGo client
        ddgs = DDGS()

        # Perform search with content
        try:
            # Get search results (limit to 5 for token efficiency)
            search_results = list(ddgs.text(
                tool.query,
                max_results=5,
                safesearch='moderate'
            ))
        except Exception as search_error:
            return f"Error performing search: {str(search_error)}"

        if not search_results:
            return f"No results found for query: '{tool.query}'"

        # Format results
        results = []
        for i, result in enumerate(search_results, 1):
            title = result.get('title', 'No title')
            url = result.get('href', 'No URL')
            body = result.get('body', 'No content available')

            # Truncate text if too long
            if len(body) > 500:
                body = body[:500] + "..."

            results.append(f"{i}. **{title}**\n   URL: {url}\n   Content: {body}\n")

        return f"Web search results for '{tool.query}':\n\n" + "\n".join(results)

    except ImportError:
        return "Error: ddgs package not installed. Run 'uv add ddgs' to install it."
    except Exception as e:
        return f"Error performing web search: {str(e)}"


def execute_exit_plan_mode(tool: types.ExitPlanModeTool, working_dir: str = ".") -> str:
    """Exit plan mode"""
    return f"Plan presented to user:\n{tool.plan}\n\nWaiting for user approval..."


def execute_pytest_run(tool: types.PytestRunTool, working_dir: str = ".") -> str:
    """Run pytest tests and return formatted results"""
    try:
        # Build pytest command
        cmd = ["python", "-m", "pytest"]

        # Add test path if specified
        if tool.test_path:
            cmd.append(tool.test_path)

        # Add pytest options
        if tool.verbose:
            cmd.append("-v")

        if tool.capture:
            cmd.extend(["-s"] if tool.capture == "no" else [f"--capture={tool.capture}"])

        if tool.markers:
            cmd.extend(["-m", tool.markers])

        if tool.keywords:
            cmd.extend(["-k", tool.keywords])

        if tool.max_failures:
            cmd.extend(["--maxfail", str(tool.max_failures)])

        # Add output formatting
        cmd.extend(["--tb=short", "--no-header"])

        # Execute with timeout
        timeout = (tool.timeout / 1000) if tool.timeout else 120
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir
        )

        # Format output
        output_lines = []

        # Add command info
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append(f"Working directory: {working_dir}")
        output_lines.append("")

        # Process stdout
        if result.stdout:
            stdout_lines = result.stdout.strip().split('\n')

            # Extract test summary
            summary_line = None
            for line in stdout_lines:
                if " passed" in line or " failed" in line or " error" in line:
                    summary_line = line
                    break

            if summary_line:
                output_lines.append(f"Test Summary: {summary_line}")
                output_lines.append("")

            # Add detailed output (truncated if needed)
            if len(stdout_lines) > 100:
                output_lines.extend(stdout_lines[:50])
                output_lines.append(f"\n... [Truncated: showing first 50 of {len(stdout_lines)} lines]")
                output_lines.append("To see full output, run PytestRun with specific test_path")
                output_lines.extend(stdout_lines[-20:])  # Show last 20 lines
            else:
                output_lines.extend(stdout_lines)

        # Add stderr if present
        if result.stderr:
            output_lines.append("\nErrors:")
            stderr_lines = result.stderr.strip().split('\n')
            if len(stderr_lines) > 20:
                output_lines.extend(stderr_lines[:20])
                output_lines.append(f"... [Error output truncated: {len(stderr_lines)} total lines]")
            else:
                output_lines.extend(stderr_lines)

        # Add exit code
        output_lines.append(f"\nExit code: {result.returncode}")

        return "\n".join(output_lines)

    except FileNotFoundError:
        return "Error: pytest not found. Install with: pip install pytest"
    except subprocess.TimeoutExpired:
        return f"Error: pytest timed out after {timeout}s. Consider using max_failures or specific test_path"
    except Exception as e:
        return f"Error running pytest: {str(e)}"


def execute_lint(tool: types.LintTool, working_dir: str = ".") -> str:
    """Run Ruff linter with optional auto-fixing"""
    try:
        # Build ruff command
        cmd = ["ruff", "check"]

        # Add target path
        target = tool.target_path or "."
        cmd.append(target)

        # Add options
        if tool.fix:
            cmd.append("--fix")

        if tool.show_fixes:
            cmd.extend(["--diff", "--preview"])

        if tool.select_codes:
            cmd.extend(["--select", tool.select_codes])

        if tool.ignore:
            cmd.extend(["--ignore", tool.ignore])

        if tool.format and tool.format != "text":
            cmd.extend(["--format", tool.format])

        # Execute ruff
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # Ruff is fast, 60s should be plenty
            cwd=working_dir
        )

        # Format output
        output_lines = []
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append(f"Target: {target}")
        output_lines.append("")

        if result.returncode == 0:
            if tool.fix:
                output_lines.append("✅ All fixable issues have been resolved")
            else:
                output_lines.append("✅ No lint issues found")

            if result.stdout:
                output_lines.append(result.stdout)
        else:
            # Process lint results
            if result.stdout:
                stdout_lines = result.stdout.strip().split('\n')

                # Count issues
                issue_count = sum(1 for line in stdout_lines if ':' in line and any(
                    level in line for level in ['error:', 'warning:', 'info:']
                ))

                if issue_count > 0:
                    output_lines.append(f"Found {issue_count} lint issues:")
                    output_lines.append("")

                # Truncate if too many issues
                if len(stdout_lines) > 50:
                    output_lines.extend(stdout_lines[:40])
                    output_lines.append(f"\n... [Truncated: showing first 40 of {len(stdout_lines)} lines]")
                    output_lines.append("Run with specific target_path to focus on fewer files")
                    output_lines.extend(stdout_lines[-5:])  # Show last few lines
                else:
                    output_lines.extend(stdout_lines)

            if result.stderr:
                output_lines.append("\nErrors:")
                output_lines.append(result.stderr)

        # Add suggestions
        if result.returncode != 0 and not tool.fix:
            output_lines.append("\n💡 Tip: Use fix=true to automatically fix many of these issues")

        return "\n".join(output_lines)

    except FileNotFoundError:
        return "Error: ruff not found. Install with: pip install ruff"
    except subprocess.TimeoutExpired:
        return "Error: Ruff timed out. Try targeting a smaller directory"
    except Exception as e:
        return f"Error running ruff: {str(e)}"


def execute_type_check(tool: types.TypeCheckTool, working_dir: str = ".") -> str:
    """Run static type checking"""
    try:
        checker = tool.checker or "mypy"
        target = tool.target_path or "."

        if checker == "mypy":
            cmd = ["mypy", target]

            if tool.strict:
                cmd.append("--strict")

            if tool.ignore_missing_imports:
                cmd.append("--ignore-missing-imports")

            if tool.incremental:
                cmd.extend(["--incremental", "--cache-dir", ".mypy_cache"])

            if tool.config_file:
                cmd.extend(["--config-file", tool.config_file])

        elif checker == "pyright":
            cmd = ["pyright", target]

            if tool.strict:
                cmd.append("--level=error")

            # Pyright reads configuration from pyrightconfig.json or pyproject.toml
            if tool.config_file:
                cmd.extend(["--project", tool.config_file])

        else:
            return f"Error: Unknown type checker '{checker}'. Use 'mypy' or 'pyright'"

        # Execute type checker
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # Type checking can be slow
            cwd=working_dir
        )

        # Format output
        output_lines = []
        output_lines.append(f"Type Checker: {checker}")
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append(f"Target: {target}")
        output_lines.append("")

        if result.returncode == 0:
            output_lines.append("✅ No type errors found")
            if result.stdout:
                # Sometimes mypy outputs success info
                output_lines.append(result.stdout.strip())
        else:
            # Process type errors
            if result.stdout:
                stdout_lines = result.stdout.strip().split('\n')

                # Count errors
                error_count = sum(1 for line in stdout_lines if 'error:' in line.lower())

                if error_count > 0:
                    output_lines.append(f"Found {error_count} type errors:")
                    output_lines.append("")

                # Truncate if too many errors
                if len(stdout_lines) > 30:
                    output_lines.extend(stdout_lines[:25])
                    output_lines.append(f"\n... [Truncated: showing first 25 of {len(stdout_lines)} lines]")
                    output_lines.append("Run with specific target_path to focus analysis")
                    output_lines.extend(stdout_lines[-5:])
                else:
                    output_lines.extend(stdout_lines)

        if result.stderr:
            output_lines.append("\nWarnings/Errors:")
            output_lines.append(result.stderr)

        return "\n".join(output_lines)

    except FileNotFoundError:
        return f"Error: {checker} not found. Install with: pip install {checker}"
    except subprocess.TimeoutExpired:
        return f"Error: {checker} timed out. Try checking a smaller scope"
    except Exception as e:
        return f"Error running {checker}: {str(e)}"


def execute_format(tool: types.FormatTool, working_dir: str = ".") -> str:
    """Format Python code using Black"""
    try:
        # Build black command
        cmd = ["black"]

        # Add target path
        target = tool.target_path or "."

        # Add options
        if tool.check_only:
            cmd.append("--check")

        if tool.diff:
            cmd.append("--diff")

        if tool.line_length:
            cmd.extend(["--line-length", str(tool.line_length)])

        if tool.skip_string_normalization:
            cmd.append("--skip-string-normalization")

        if tool.target_version:
            cmd.extend(["--target-version", tool.target_version])

        # Add target last
        cmd.append(target)

        # Execute black
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # Black is fast
            cwd=working_dir
        )

        # Format output
        output_lines = []
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append(f"Target: {target}")
        output_lines.append("")

        if result.returncode == 0:
            if tool.check_only:
                output_lines.append("✅ All files are already properly formatted")
            else:
                output_lines.append("✅ Code formatting completed successfully")

            if result.stdout:
                output_lines.append(result.stdout.strip())
        else:
            # Black found formatting issues
            if result.stdout:
                stdout_lines = result.stdout.strip().split('\n')

                if tool.check_only:
                    formatted_files = [line for line in stdout_lines if line.startswith("would reformat")]
                    if formatted_files:
                        output_lines.append(f"Found {len(formatted_files)} files that need formatting:")
                        output_lines.extend(formatted_files)
                        output_lines.append("\n💡 Run without check_only=true to apply formatting")
                else:
                    # Show formatting results
                    if tool.diff:
                        output_lines.append("Formatting changes:")
                        # Truncate large diffs
                        if len(stdout_lines) > 100:
                            output_lines.extend(stdout_lines[:80])
                            output_lines.append(f"\n... [Diff truncated: {len(stdout_lines)} total lines]")
                            output_lines.append("Use target_path to format specific files for smaller diffs")
                        else:
                            output_lines.extend(stdout_lines)
                    else:
                        output_lines.extend(stdout_lines)

        if result.stderr:
            output_lines.append("\nErrors:")
            output_lines.append(result.stderr)

        return "\n".join(output_lines)

    except FileNotFoundError:
        return "Error: black not found. Install with: pip install black"
    except subprocess.TimeoutExpired:
        return "Error: Black timed out. Try formatting a smaller directory"
    except Exception as e:
        return f"Error running black: {str(e)}"


def execute_dependency(tool: types.DependencyTool, working_dir: str = ".") -> str:
    """Check and manage Python dependencies"""
    try:
        check_type = tool.check_type or "missing"
        requirements_file = tool.requirements_file or "pyproject.toml"

        output_lines = []
        output_lines.append(f"Dependency Check: {check_type}")
        output_lines.append(f"Requirements file: {requirements_file}")
        output_lines.append(f"Working directory: {working_dir}")
        output_lines.append("")

        if check_type == "missing":
            # Check for missing dependencies
            try:
                import toml
                req_path = os.path.join(working_dir, requirements_file)

                if not os.path.exists(req_path):
                    return f"Error: Requirements file not found: {req_path}"

                # Parse requirements
                with open(req_path, 'r') as f:
                    config = toml.load(f)

                dependencies = []
                if 'project' in config and 'dependencies' in config['project']:
                    dependencies.extend(config['project']['dependencies'])

                if tool.include_dev and 'project' in config and 'optional-dependencies' in config['project']:
                    for group in config['project']['optional-dependencies'].values():
                        dependencies.extend(group)

                missing_packages = []
                installed_packages = []

                for dep in dependencies:
                    # Extract package name (remove version constraints)
                    package_name = dep.split('>=')[0].split('==')[0].split('~=')[0].split('<')[0].split('>')[0].strip()

                    try:
                        import importlib.util
                        spec = importlib.util.find_spec(package_name.replace('-', '_'))
                        if spec is None:
                            missing_packages.append(dep)
                        else:
                            installed_packages.append(dep)
                    except ImportError:
                        missing_packages.append(dep)

                if missing_packages:
                    output_lines.append(f"❌ Found {len(missing_packages)} missing dependencies:")
                    output_lines.extend([f"  - {pkg}" for pkg in missing_packages])
                    output_lines.append(f"\n💡 Install with: pip install {' '.join(missing_packages)}")
                else:
                    output_lines.append("✅ All dependencies are installed")

                if installed_packages:
                    output_lines.append(f"\n✅ Installed ({len(installed_packages)} packages):")
                    output_lines.extend([f"  - {pkg}" for pkg in installed_packages[:10]])  # Show first 10
                    if len(installed_packages) > 10:
                        output_lines.append(f"  ... and {len(installed_packages) - 10} more")

            except ImportError:
                return "Error: toml package not found. Install with: pip install toml"
            except Exception as e:
                return f"Error parsing requirements file: {str(e)}"

        elif check_type == "outdated":
            # Check for outdated packages
            cmd = ["pip", "list", "--outdated", "--format=columns"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=working_dir)

            if result.returncode == 0:
                if result.stdout.strip():
                    output_lines.append("Outdated packages:")
                    output_lines.append(result.stdout.strip())
                else:
                    output_lines.append("✅ All packages are up to date")
            else:
                output_lines.append("Error checking outdated packages:")
                output_lines.append(result.stderr or "Unknown error")

        elif check_type == "tree":
            # Show dependency tree
            cmd = ["pip", "show", "--verbose"]
            # Get all installed packages first
            list_result = subprocess.run(["pip", "list", "--format=freeze"],
                                        capture_output=True, text=True, timeout=30, cwd=working_dir)
            if list_result.returncode == 0:
                packages = [line.split('==')[0] for line in list_result.stdout.strip().split('\n') if line]
                output_lines.append(f"Installed packages ({len(packages)}):")
                output_lines.extend([f"  - {pkg}" for pkg in packages[:20]])  # Show first 20
                if len(packages) > 20:
                    output_lines.append(f"  ... and {len(packages) - 20} more")
            else:
                output_lines.append("Error listing packages")

        elif check_type == "imports":
            # Check if specific packages can be imported
            packages = tool.packages or []
            if not packages:
                return "Error: packages parameter is required for 'imports' check type"

            missing_packages = []
            available_packages = []

            for package_name in packages:
                try:
                    import importlib.util
                    # Check common package name variations
                    variations = [
                        package_name,
                        package_name.replace('-', '_'),
                        package_name.replace('_', '-'),
                        package_name.lower()
                    ]

                    found = False
                    for variation in variations:
                        spec = importlib.util.find_spec(variation)
                        if spec is not None:
                            available_packages.append(package_name)
                            found = True
                            break

                    if not found:
                        missing_packages.append(package_name)

                except Exception:
                    missing_packages.append(package_name)

            # Report results
            output_lines.append(f"Import check for {len(packages)} packages:")

            if available_packages:
                output_lines.append(f"\n✅ Available packages ({len(available_packages)}):")
                output_lines.extend([f"  - {pkg}" for pkg in available_packages])

            if missing_packages:
                output_lines.append(f"\n❌ Missing packages ({len(missing_packages)}):")
                output_lines.extend([f"  - {pkg}" for pkg in missing_packages])
                output_lines.append("\n💡 To install missing packages:")
                output_lines.append(f"   uv add {' '.join(missing_packages)}")
                output_lines.append(f"   # or: pip install {' '.join(missing_packages)}")
                output_lines.append("\n🤖 The agent can install these for you if you approve.")

        else:
            return f"Error: Unknown check_type '{check_type}'. Use 'missing', 'outdated', 'tree', or 'imports'"

        return "\n".join(output_lines)

    except subprocess.TimeoutExpired:
        return "Error: Dependency check timed out"
    except Exception as e:
        return f"Error checking dependencies: {str(e)}"


def execute_git_diff(tool: types.GitDiffTool, working_dir: str = ".") -> str:
    """Compare files against git references"""
    try:
        # Build git diff command
        cmd = ["git", "diff"]

        # Add reference
        reference = tool.reference or "HEAD"
        if reference != "HEAD":
            cmd.append(reference)

        # Add options
        if tool.staged:
            cmd.append("--staged")

        if tool.stat:
            cmd.append("--stat")

        if tool.context_lines is not None:
            cmd.extend([f"--context={tool.context_lines}"])

        if tool.ignore_whitespace:
            cmd.append("--ignore-space-change")

        # Add target path
        if tool.target_path:
            cmd.append(tool.target_path)

        # Execute git diff
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=working_dir
        )

        # Format output
        output_lines = []
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append(f"Reference: {reference}")
        output_lines.append(f"Working directory: {working_dir}")
        output_lines.append("")

        if result.returncode == 0:
            if result.stdout.strip():
                stdout_lines = result.stdout.strip().split('\n')

                # Truncate large diffs
                if len(stdout_lines) > 200:
                    output_lines.extend(stdout_lines[:150])
                    output_lines.append(f"\n... [Diff truncated: showing first 150 of {len(stdout_lines)} lines]")
                    output_lines.append("Use target_path to focus on specific files")
                    output_lines.extend(stdout_lines[-20:])  # Show last 20 lines
                else:
                    output_lines.extend(stdout_lines)
            else:
                output_lines.append("✅ No differences found")
        else:
            if result.stderr:
                output_lines.append("Error:")
                output_lines.append(result.stderr.strip())
            else:
                output_lines.append("Git diff command failed")

        return "\n".join(output_lines)

    except FileNotFoundError:
        return "Error: git not found or not in a git repository"
    except subprocess.TimeoutExpired:
        return "Error: Git diff timed out. Try using target_path for specific files"
    except Exception as e:
        return f"Error running git diff: {str(e)}"


def execute_install_packages(tool: types.InstallPackagesTool, working_dir: str = ".") -> str:
    """Install Python packages using uv or pip with user permission"""
    try:
        # Safety check - require user confirmation
        if not tool.user_confirmed:
            return "❌ Error: Installation requires user confirmation. Set user_confirmed=true to proceed."

        packages = tool.packages
        if not packages:
            return "❌ Error: No packages specified for installation"

        # Validate Python packages only
        non_python_indicators = [
            'brew', 'homebrew', 'apt', 'yum', 'pacman',  # Package managers
            'node', 'npm', 'yarn',  # Node.js
            'docker', 'kubernetes', 'helm',  # Container tools
            'git', 'svn', 'mercurial',  # VCS (use GitPython instead)
            'redis', 'mongodb', 'postgresql',  # Databases (use Python clients)
            'nginx', 'apache', 'mysql',  # Servers
            'terraform', 'ansible',  # Infrastructure
            'ruby', 'go', 'rust', 'java',  # Other languages
        ]

        invalid_packages = []
        python_alternatives = {
            'git': 'GitPython',
            'redis': 'redis-py',
            'mongodb': 'pymongo',
            'postgresql': 'psycopg2-binary',
            'mysql': 'PyMySQL',
            'sqlite': 'sqlite3 (built-in)',
            'docker': 'docker-py',
            'kubernetes': 'kubernetes-client',
            'node': 'pynode or find Python equivalent',
            'npm': 'find Python equivalent',
        }

        for package in packages:
            package_lower = package.lower()

            # Check if package name exactly matches or starts with non-Python indicators
            # But allow Python wrappers that contain these terms (e.g., GitPython, redis-py)
            is_invalid = False
            for indicator in non_python_indicators:
                # Exact match
                if package_lower == indicator:
                    is_invalid = True
                    break
                # Package starts with indicator followed by non-letter character
                elif package_lower.startswith(indicator + "-") or package_lower.startswith(indicator + "_"):
                    # Exception: allow common Python wrapper patterns
                    python_wrapper_patterns = [
                        "redis-py", "redis_py", "docker-py", "docker_py",
                        "postgresql-py", "mysql-py"
                    ]
                    if package_lower not in python_wrapper_patterns:
                        is_invalid = True
                        break
                # Standalone tool names (but allow Python wrappers like GitPython)
                elif indicator in ["git", "node", "npm", "docker", "redis"] and package_lower == indicator:
                    is_invalid = True
                    break

            if is_invalid:
                invalid_packages.append(package)

        if invalid_packages:
            output_lines = []
            output_lines.append("❌ Error: Non-Python packages detected!")
            output_lines.append("This tool only installs Python packages from PyPI.")
            output_lines.append("")
            output_lines.append("Invalid packages:")
            for pkg in invalid_packages:
                output_lines.append(f"  - {pkg}")
                if pkg.lower() in python_alternatives:
                    output_lines.append(f"    💡 Try instead: {python_alternatives[pkg.lower()]}")

            output_lines.append("")
            output_lines.append("For system dependencies:")
            output_lines.append("1. Use WebSearch to find Python equivalents")
            output_lines.append("2. Look for Python wrappers or clients")
            output_lines.append("3. Consider pure-Python implementations")
            output_lines.append("")
            output_lines.append("Examples:")
            output_lines.append("  - git → GitPython")
            output_lines.append("  - redis → redis-py")
            output_lines.append("  - docker → docker-py")
            return "\n".join(output_lines)

        # Format output
        output_lines = []
        output_lines.append("📦 Installing packages...")
        output_lines.append(f"Packages: {', '.join(packages)}")
        output_lines.append(f"Development: {'Yes' if tool.dev else 'No'}")
        output_lines.append(f"Upgrade: {'Yes' if tool.upgrade else 'No'}")
        output_lines.append(f"Working directory: {working_dir}")
        output_lines.append("")

        # Try uv first (preferred), then fallback to pip
        uv_available = False
        pip_available = False

        # Check if uv is available
        try:
            uv_result = subprocess.run(["uv", "--version"], capture_output=True, timeout=5, cwd=working_dir)
            if uv_result.returncode == 0:
                uv_available = True
                output_lines.append("✅ Using uv (preferred package manager)")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check if pip is available if uv isn't
        if not uv_available:
            try:
                pip_result = subprocess.run(["pip", "--version"], capture_output=True, timeout=5, cwd=working_dir)
                if pip_result.returncode == 0:
                    pip_available = True
                    output_lines.append("✅ Using pip (fallback package manager)")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        if not uv_available and not pip_available:
            return "❌ Error: Neither uv nor pip are available. Please install a package manager."

        # Build installation command
        if uv_available:
            cmd = ["uv", "add"]
            if tool.dev:
                cmd.append("--dev")
            if tool.upgrade:
                cmd.append("--upgrade")
            cmd.extend(packages)
        else:
            cmd = ["pip", "install"]
            if tool.upgrade:
                cmd.append("--upgrade")
            cmd.extend(packages)

        # Execute installation
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append("")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout for installs
            cwd=working_dir
        )

        if result.returncode == 0:
            output_lines.append("✅ Installation completed successfully!")
            if result.stdout.strip():
                stdout_lines = result.stdout.strip().split('\n')
                # Show relevant output (truncated for large installs)
                if len(stdout_lines) > 50:
                    output_lines.append("\nInstallation output (truncated):")
                    output_lines.extend(stdout_lines[-20:])  # Show last 20 lines
                    output_lines.append(f"... (showing last 20 of {len(stdout_lines)} lines)")
                else:
                    output_lines.append("\nInstallation output:")
                    output_lines.extend(stdout_lines)
        else:
            output_lines.append("❌ Installation failed!")
            if result.stderr:
                output_lines.append("\nError details:")
                error_lines = result.stderr.strip().split('\n')
                # Show error details (truncated for very long errors)
                if len(error_lines) > 30:
                    output_lines.extend(error_lines[:20])
                    output_lines.append(f"... (showing first 20 of {len(error_lines)} error lines)")
                else:
                    output_lines.extend(error_lines)

            # Provide helpful suggestions
            output_lines.append("\n💡 Troubleshooting suggestions:")
            if uv_available:
                output_lines.append("   - Check package names are correct")
                output_lines.append("   - Try: uv sync to refresh dependencies")
                output_lines.append("   - Try: uv lock --upgrade to update lockfile")
            else:
                output_lines.append("   - Check package names are correct")
                output_lines.append("   - Try: pip install --upgrade pip")
                output_lines.append("   - Consider using uv for better dependency management")

        return "\n".join(output_lines)

    except subprocess.TimeoutExpired:
        return "❌ Error: Package installation timed out (5 minute limit)"
    except Exception as e:
        return f"❌ Error installing packages: {str(e)}"


def execute_artifact_management(tool: types.ArtifactManagementTool, working_dir: str = ".") -> str:
    """Manage and organize project artifacts in standard folders"""
    import glob
    import os
    from pathlib import Path

    try:
        # Define standard artifact folders
        artifact_folders = {
            "script": ["scripts"],
            "data": ["data"],
            "visualization": ["visualization", "plots"],  # Include legacy plots folder
            "any": ["scripts", "data", "visualization", "plots"]
        }

        output_lines = []
        output_lines.append(f"🗂️ Artifact Management: {tool.action_type}")

        if tool.folder:
            output_lines.append(f"Target folder: {tool.folder}")
        if tool.pattern:
            output_lines.append(f"Search pattern: {tool.pattern}")
        if tool.artifact_type:
            output_lines.append(f"Artifact type: {tool.artifact_type}")

        output_lines.append(f"Working directory: {working_dir}")
        output_lines.append("")

        action_type = tool.action_type.lower()

        if action_type == "list":
            # List artifacts in specified folders
            folders_to_check = []

            if tool.folder:
                folders_to_check = [tool.folder]
            elif tool.artifact_type and tool.artifact_type in artifact_folders:
                folders_to_check = artifact_folders[tool.artifact_type]
            else:
                folders_to_check = artifact_folders["any"]

            total_files = 0
            for folder in folders_to_check:
                folder_path = os.path.join(working_dir, folder)
                if os.path.exists(folder_path):
                    pattern = tool.pattern or "*"
                    search_path = os.path.join(folder_path, pattern)
                    files = glob.glob(search_path, recursive=True)

                    if files:
                        output_lines.append(f"📁 {folder}/ ({len(files)} files):")
                        for file_path in sorted(files):
                            relative_path = os.path.relpath(file_path, working_dir)
                            file_size = os.path.getsize(file_path)
                            size_str = f"({file_size:,} bytes)" if file_size < 10000 else f"({file_size//1024:,} KB)"
                            output_lines.append(f"  - {relative_path} {size_str}")
                        total_files += len(files)
                        output_lines.append("")
                    else:
                        output_lines.append(f"📁 {folder}/ (empty)")
                        output_lines.append("")
                else:
                    output_lines.append(f"📁 {folder}/ (folder does not exist)")
                    output_lines.append("")

            output_lines.append(f"📊 Summary: {total_files} total artifacts found")

        elif action_type == "find":
            # Find specific artifacts across all folders
            if not tool.pattern:
                return "❌ Error: pattern parameter required for 'find' action"

            all_matches = []
            for folder in artifact_folders["any"]:
                folder_path = os.path.join(working_dir, folder)
                if os.path.exists(folder_path):
                    search_path = os.path.join(folder_path, "**", tool.pattern)
                    matches = glob.glob(search_path, recursive=True)
                    all_matches.extend(matches)

            if all_matches:
                output_lines.append(f"🔍 Found {len(all_matches)} matches for '{tool.pattern}':")
                output_lines.append("")

                # Group by folder
                by_folder = {}
                for match in sorted(all_matches):
                    relative_path = os.path.relpath(match, working_dir)
                    folder_name = relative_path.split('/')[0]
                    if folder_name not in by_folder:
                        by_folder[folder_name] = []
                    by_folder[folder_name].append(relative_path)

                for folder_name, files in by_folder.items():
                    output_lines.append(f"📁 {folder_name}/:")
                    for file_path in files:
                        file_size = os.path.getsize(os.path.join(working_dir, file_path))
                        size_str = f"({file_size:,} bytes)" if file_size < 10000 else f"({file_size//1024:,} KB)"
                        output_lines.append(f"  - {file_path} {size_str}")
                    output_lines.append("")
            else:
                output_lines.append(f"🔍 No matches found for pattern '{tool.pattern}'")
                output_lines.append("")
                output_lines.append("💡 Tip: Try broader patterns like '*plot*', '*.py', '*.csv'")

        elif action_type == "organize":
            # Ensure all standard folders exist and provide organization tips
            created_folders = []
            for folder in artifact_folders["any"]:
                folder_path = os.path.join(working_dir, folder)
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path, exist_ok=True)
                    created_folders.append(folder)

            if created_folders:
                output_lines.append(f"✅ Created missing folders: {', '.join(created_folders)}")
                output_lines.append("")

            # Check for files in root that should be organized
            root_files = glob.glob(os.path.join(working_dir, "*"))
            root_files = [f for f in root_files if os.path.isfile(f)]

            suggestions = []
            for file_path in root_files:
                filename = os.path.basename(file_path)
                if filename.endswith(('.py', '.ipynb')) and not filename.startswith(('main.', 'tui.', 'agent_runtime.')):
                    suggestions.append(f"  mv {filename} scripts/")
                elif filename.endswith(('.csv', '.json', '.txt', '.xlsx')):
                    suggestions.append(f"  mv {filename} data/")
                elif filename.endswith(('.png', '.jpg', '.svg', '.pdf', '.html')):
                    suggestions.append(f"  mv {filename} visualization/")

            if suggestions:
                output_lines.append("💡 Organization suggestions for root directory files:")
                output_lines.extend(suggestions[:10])  # Show first 10 suggestions
                if len(suggestions) > 10:
                    output_lines.append(f"  ... and {len(suggestions) - 10} more files")
                output_lines.append("")

            output_lines.append("📋 Standard folder structure:")
            output_lines.append("  scripts/       - Python scripts, code generators, analysis tools")
            output_lines.append("  data/          - CSV files, datasets, JSON files, text data")
            output_lines.append("  visualization/ - Plots, charts, images, visual outputs")
            output_lines.append("  plots/         - Legacy plot folder")

        elif action_type == "clean":
            # Clean up empty folders and provide cleanup suggestions
            empty_folders = []
            for folder in artifact_folders["any"]:
                folder_path = os.path.join(working_dir, folder)
                if os.path.exists(folder_path) and not os.listdir(folder_path):
                    empty_folders.append(folder)

            if empty_folders:
                output_lines.append(f"🗑️ Empty folders found: {', '.join(empty_folders)}")
                output_lines.append("These folders are kept for future artifact organization")
                output_lines.append("")

            # Check for duplicate files
            output_lines.append("🔍 Checking for potential duplicates...")
            # This is a basic check - could be enhanced with content comparison
            all_files = []
            for folder in artifact_folders["any"]:
                folder_path = os.path.join(working_dir, folder)
                if os.path.exists(folder_path):
                    files = glob.glob(os.path.join(folder_path, "**/*"), recursive=True)
                    all_files.extend([f for f in files if os.path.isfile(f)])

            filenames = {}
            for file_path in all_files:
                filename = os.path.basename(file_path)
                if filename not in filenames:
                    filenames[filename] = []
                filenames[filename].append(file_path)

            duplicates = {name: paths for name, paths in filenames.items() if len(paths) > 1}
            if duplicates:
                output_lines.append(f"⚠️ Found {len(duplicates)} potential duplicate filenames:")
                for filename, paths in list(duplicates.items())[:5]:  # Show first 5
                    output_lines.append(f"  {filename}:")
                    for path in paths:
                        relative_path = os.path.relpath(path, working_dir)
                        output_lines.append(f"    - {relative_path}")
                if len(duplicates) > 5:
                    output_lines.append(f"  ... and {len(duplicates) - 5} more")
            else:
                output_lines.append("✅ No duplicate filenames found")

        else:
            return f"❌ Error: Unknown action_type '{tool.action_type}'. Use 'list', 'find', 'organize', or 'clean'"

        return "\n".join(output_lines)

    except Exception as e:
        return f"❌ Error managing artifacts: {str(e)}"


async def execute_agent(tool: types.AgentTool) -> str:
    """Launch a sub-agent (recursive call)"""
    try:
        print(f"\n🔄 Launching sub-agent: {tool.description}")
        print(f"   Prompt: {tool.prompt[:100]}{'...' if len(tool.prompt) > 100 else ''}")
        
        # Recursively call the agent loop with a reasonable limit for sub-agents
        result = await agent_loop(tool.prompt, max_iterations=50, working_dir=".")
        
        return f"Sub-agent completed:\nTask: {tool.description}\nResult: {result}"
    except Exception as e:
        return f"Sub-agent error: {str(e)}"


async def execute_tool(tool: types.AgentTools, working_dir: str = ".") -> str:
    """Execute a tool based on its type using match statement"""
    # Check for global interrupt state if available
    try:
        from agent_runtime import AgentRuntime
        if hasattr(AgentRuntime, '_current_state') and AgentRuntime._current_state:
            if AgentRuntime._current_state.interrupt_requested:
                return "❌ Tool execution interrupted by user"
    except:
        pass  # No interrupt checking available

    match tool.action:
        case "Bash":
            return execute_bash(tool, working_dir)
        case "Glob":
            return execute_glob(tool, working_dir)
        case "Grep":
            return execute_grep(tool, working_dir)
        case "LS":
            return execute_ls(tool, working_dir)
        case "Read":
            return execute_read(tool, working_dir)
        case "Edit":
            return execute_edit(tool, working_dir)
        case "MultiEdit":
            return execute_multi_edit(tool, working_dir)
        case "Write":
            return execute_write(tool, working_dir)
        case "NotebookRead":
            return execute_notebook_read(tool, working_dir)
        case "NotebookEdit":
            return execute_notebook_edit(tool, working_dir)
        case "WebFetch":
            return execute_web_fetch(tool, working_dir)
        case "TodoRead":
            return execute_todo_read(tool, working_dir)
        case "TodoWrite":
            return execute_todo_write(tool, working_dir)
        case "WebSearch":
            return execute_web_search(tool, working_dir)
        case "ExitPlanMode":
            return execute_exit_plan_mode(tool, working_dir)
        case "PytestRun":
            return execute_pytest_run(tool, working_dir)
        case "Lint":
            return execute_lint(tool, working_dir)
        case "TypeCheck":
            return execute_type_check(tool, working_dir)
        case "Format":
            return execute_format(tool, working_dir)
        case "Dependency":
            return execute_dependency(tool, working_dir)
        case "GitDiff":
            return execute_git_diff(tool, working_dir)
        case "InstallPackages":
            return execute_install_packages(tool, working_dir)
        case "ArtifactManagement":
            return execute_artifact_management(tool, working_dir)
        case "Agent":
            return await execute_agent(tool)
        case other:
            return f"Unknown tool type: {other}"


async def agent_loop(user_message: str, max_iterations: int = 20, working_dir: str = ".") -> str:
    """Main agent loop that calls the BAML agent and executes tools"""
    from agent_runtime import AgentState, AgentCallbacks, AgentRuntime
    import os
    
    # Suppress BAML verbose logging for CLI
    os.environ["BAML_LOG"] = "WARN"
    
    # Create state and callbacks for CLI
    state = AgentState(working_dir=working_dir)
    
    async def on_reply(msg: str) -> None:
        print(f"\n🤖 Agent reply: {msg}")
    
    callbacks = AgentCallbacks(
        on_iteration=print_iteration,
        on_tool_start=print_tool_start,
        on_tool_result=print_tool_result,
        on_agent_reply=on_reply,
    )
    
    runtime = AgentRuntime(state, callbacks)
    return await runtime.run_loop(user_message, max_iterations=max_iterations, depth=0)


async def print_iteration(iteration: int, depth: int) -> None:
    """Print iteration info"""
    if depth == 0:
        print(f"\n{'='*60}")
        print(f"Iteration {iteration}")
        print(f"{'='*60}")


async def print_tool_start(tool_name: str, params: dict, tool_idx: int, total_tools: int, depth: int) -> None:
    """Print tool execution start"""
    if depth == 0:
        print(f"\n🔧 Executing tool: {tool_name}")
        if params:
            # Show only essential parameters, not the full dict
            essential_params = {}
            for key, value in params.items():
                if key in ['file_path', 'pattern', 'command', 'path']:
                    essential_params[key] = value
            if essential_params:
                print(f"   Parameters: {essential_params}")


async def print_tool_result(result: str, depth: int) -> None:
    """Print tool result"""
    if depth == 0:
        # Truncate long results for CLI
        if len(result) > 500:
            result = result[:500] + f"\n... [truncated: showing first 500 of {len(result)} characters]"
        print(f"   Result: {result}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="BAMMY Agent - Agentic RAG Context Engineering Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a single command
  python main.py "What files are in this directory?"
  
  # Interactive mode - keeps asking for commands
  python main.py --interactive
  python main.py "Start" --interactive  # conventional way to start interactive mode
  
  # TUI mode - beautiful text interface (no initial query needed)
  python main.py --tui
  python main.py "Start" --tui  # conventional way to start TUI

  # TUI mode with initial query
  python main.py "List files" --tui
  
  # Specify a working directory
  python main.py "Find all Python files" --dir /path/to/project
        """
    )
    
    parser.add_argument(
        "query",
        type=str,
        nargs="?",
        default=None,
        help="The query or task for the agent to perform (optional in TUI mode)"
    )
    
    parser.add_argument(
        "--dir",
        "-d",
        type=str,
        default=None,
        help="Working directory for the agent (defaults to current directory)"
    )
    
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode (keep asking for commands)"
    )
    
    parser.add_argument(
        "--tui",
        "-t",
        action="store_true",
        help="Run in TUI mode (beautiful text user interface)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Launch TUI mode if requested
    if args.tui:
        from tui import run_tui
        
        work_dir = None
        if args.dir:
            work_dir = Path(args.dir).resolve()
            if not work_dir.exists():
                print(f"❌ Error: Directory does not exist: {work_dir}")
                sys.exit(1)
            if not work_dir.is_dir():
                print(f"❌ Error: Not a directory: {work_dir}")
                sys.exit(1)
            work_dir = str(work_dir)
        
        run_tui(working_dir=work_dir, initial_query=args.query)
        return
    
    # Set working directory for CLI mode
    if args.dir:
        work_dir = str(Path(args.dir).resolve())
        work_dir_path = Path(work_dir)
        if not work_dir_path.exists():
            print(f"❌ Error: Directory does not exist: {work_dir}")
            sys.exit(1)
        if not work_dir_path.is_dir():
            print(f"❌ Error: Not a directory: {work_dir}")
            sys.exit(1)
        
        os.chdir(work_dir)
        print(f"📁 Working directory: {work_dir}")
    else:
        work_dir = os.getcwd()
        print(f"📁 Working directory: {work_dir}")
    
    # Require query in non-interactive/non-TUI mode
    if not args.query and not args.interactive:
        parser.error("query is required unless using --interactive mode")
    
    # Print header
    print("🤖 BAMMY Agent - Agentic RAG Context Engineering Demo")
    print("=" * 60)
    
    # Interactive loop or single command
    first_query = args.query
    
    while True:
        try:
            if first_query:
                query = first_query
                first_query = None  # Only use the first query once
            else:
                print("\n" + "=" * 60)
                query = input("📝 Enter your command (or 'exit' to quit): ").strip()

                if not query:
                    continue

                if query.lower() in ['exit', 'quit', 'q']:
                    print("👋 Goodbye!")
                    break

            # Skip generic startup commands that don't provide meaningful tasks
            if query.strip().lower() in ["start", "begin", "go"]:
                print(f"\n📝 Query: {query}")
                print("🚀 BAMMY Agent ready! Please enter a specific command or task.")
                print("💡 Examples: 'List files', 'Search for Python functions', 'Explain this code'")
                if not args.interactive:
                    break  # In non-interactive mode, exit after showing help
                continue  # In interactive mode, ask for another command

            print(f"\n📝 Query: {query}")
            print("🔄 Running agent...")
            print("=" * 60)

            # Run the agent
            result = asyncio.run(agent_loop(query, max_iterations=20, working_dir=work_dir))
            
            print(f"\n{'='*60}")
            print(f"✅ Final result:\n{result}")
            print(f"{'='*60}")
            
            # If not in interactive mode, exit after first query
            if not args.interactive:
                break
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            if args.interactive:
                continue  # Go back to prompt
            else:
                sys.exit(130)
        except Exception as e:
            print(f"\n\n❌ Error: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            if not args.interactive:
                sys.exit(1)
            # In interactive mode, continue to next query


if __name__ == "__main__":
    # Load .env file with override=True to override shell environment variables
    load_dotenv(override=True)

    # Print loaded keys for verification
    openai_key = os.getenv("OPENAI_API_KEY")
    boundary_key = os.getenv("BOUNDARY_API_KEY")

    print(f"🔑 OpenAI API Key loaded: {openai_key[-6:] if openai_key else 'Not found'}")
    print(f"🔑 Boundary API Key loaded: {boundary_key[-6:] if boundary_key else 'Not found'}")

    main()
