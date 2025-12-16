"""
Utility tools for TATty Agent

This module contains utility and planning tools extracted from main.py:
- TodoRead: Read current todo list
- TodoWrite: Update todo list
- ExitPlanMode: Exit planning mode
- NotebookRead: Read Jupyter notebook contents
- NotebookEdit: Edit Jupyter notebook cells
"""
from ..baml_client import types
from .registry import register_tool

# In-memory storage for todos (shared global state)
_todo_store: list[types.TodoItem] = []


@register_tool("TodoRead")
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


@register_tool("TodoWrite")
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


@register_tool("ExitPlanMode")
def execute_exit_plan_mode(tool: types.ExitPlanModeTool, working_dir: str = ".") -> str:
    """Exit plan mode"""
    return f"Plan presented to user:\n{tool.plan}\n\nWaiting for user approval..."


@register_tool("NotebookRead")
def execute_notebook_read(tool: types.NotebookReadTool, working_dir: str = ".") -> str:
    """Read Jupyter notebook contents"""
    try:
        import json
        from pathlib import Path

        # If notebook_path is relative, make it relative to working_dir
        if not tool.notebook_path.startswith("/"):
            path = Path(working_dir) / tool.notebook_path
        else:
            path = Path(tool.notebook_path)

        if not path.exists():
            return f"Notebook not found: {tool.notebook_path}"

        with open(path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)

        if 'cells' not in notebook:
            return f"Invalid notebook format: {tool.notebook_path}"

        cells_info = []
        for i, cell in enumerate(notebook['cells']):
            cell_type = cell.get('cell_type', 'unknown')
            source = cell.get('source', [])

            # Join source lines
            if isinstance(source, list):
                source_text = ''.join(source)
            else:
                source_text = source

            # Truncate long cells
            if len(source_text) > 500:
                source_text = source_text[:500] + "... [truncated]"

            cells_info.append(f"Cell {i} ({cell_type}):\n{source_text}")

        return f"Notebook: {tool.notebook_path}\n\n" + "\n\n".join(cells_info)
    except Exception as e:
        return f"Error reading notebook: {str(e)}"


@register_tool("NotebookEdit")
def execute_notebook_edit(tool: types.NotebookEditTool, working_dir: str = ".") -> str:
    """Edit Jupyter notebook cell"""
    try:
        import json
        from pathlib import Path

        # If notebook_path is relative, make it relative to working_dir
        if not tool.notebook_path.startswith("/"):
            path = Path(working_dir) / tool.notebook_path
        else:
            path = Path(tool.notebook_path)

        if not path.exists():
            return f"Notebook not found: {tool.notebook_path}"

        with open(path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)

        if 'cells' not in notebook:
            return f"Invalid notebook format: {tool.notebook_path}"

        if tool.cell_number >= len(notebook['cells']):
            return f"Cell {tool.cell_number} does not exist (notebook has {len(notebook['cells'])} cells)"

        # Update cell source
        cell = notebook['cells'][tool.cell_number]

        # Convert new_source to list format that Jupyter expects
        if isinstance(tool.new_source, str):
            # Split by lines and add newlines back
            source_lines = [line + '\n' for line in tool.new_source.split('\n')]
            # Remove newline from last line if it's empty
            if source_lines and source_lines[-1] == '\n':
                source_lines = source_lines[:-1]
            cell['source'] = source_lines
        else:
            cell['source'] = tool.new_source

        # Update cell type if specified
        if hasattr(tool, 'cell_type') and tool.cell_type:
            cell['cell_type'] = tool.cell_type

        # Write back to file
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=2)

        return f"Successfully updated cell {tool.cell_number} in {tool.notebook_path}"
    except Exception as e:
        return f"Error editing notebook: {str(e)}"