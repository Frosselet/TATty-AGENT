"""
Jupyter notebook integration for TATty Agent

This module provides access to notebook variables, dataframes, and the ability
to generate and modify cells programmatically.
"""
import inspect
import json
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime
import sys

from ..core.state import AgentState
from ..core.types import Message

try:
    from IPython import get_ipython
    from IPython.display import display, HTML, Code, Javascript
    from IPython.core.interactiveshell import InteractiveShell
    import pandas as pd
    import numpy as np
    JUPYTER_AVAILABLE = True
except ImportError:
    JUPYTER_AVAILABLE = False
    pd = None
    np = None
    InteractiveShell = None

    def get_ipython():
        return None

    def display(*args, **kwargs):
        pass


class NotebookContextManager:
    """Manages interaction between TATty Agent and Jupyter notebook context"""

    def __init__(self, shell: Optional[Any] = None):
        self.shell = shell or get_ipython()
        self._variable_cache: Dict[str, Any] = {}
        self._last_cache_time: Optional[datetime] = None

        # Persistent agent state shared across all notebook interactions
        self._agent_state: Optional[AgentState] = None
        self._working_dir: str = "."

    def get_notebook_variables(self, refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Get all accessible variables from the notebook namespace

        Args:
            refresh: Force refresh of variable cache

        Returns:
            Dictionary mapping variable names to their info
        """
        if not self.shell:
            return {}

        # Use cache if recent and not forcing refresh
        now = datetime.now()
        if (not refresh and self._last_cache_time and
            (now - self._last_cache_time).total_seconds() < 30):
            return self._variable_cache

        variables = {}
        user_ns = self.shell.user_ns

        for name, value in user_ns.items():
            # Skip private variables and builtins
            if name.startswith('_') or name in ['In', 'Out', 'get_ipython', 'exit', 'quit']:
                continue

            # Skip modules and functions (unless they're user-defined)
            if inspect.ismodule(value) or (inspect.isfunction(value) and
                                         getattr(value, '__module__', None) != '__main__'):
                continue

            var_info = self._analyze_variable(name, value)
            if var_info:
                variables[name] = var_info

        self._variable_cache = variables
        self._last_cache_time = now
        return variables

    def get_variable_by_name(self, name: str) -> Any:
        """Get a specific variable by name"""
        if not self.shell:
            return None

        return self.shell.user_ns.get(name)

    def set_variable(self, name: str, value: Any) -> bool:
        """Set a variable in the notebook namespace"""
        if not self.shell:
            return False

        try:
            self.shell.user_ns[name] = value
            # Clear cache to force refresh
            self._last_cache_time = None
            return True
        except Exception:
            return False

    def execute_code(self, code: str, silent: bool = False) -> Dict[str, Any]:
        """
        Execute code in the notebook context

        Args:
            code: Python code to execute
            silent: If True, don't display output

        Returns:
            Dictionary with execution result info
        """
        if not self.shell:
            return {"success": False, "error": "No IPython shell available"}

        try:
            # Execute the code
            result = self.shell.run_cell(code, silent=silent)

            return {
                "success": result.success,
                "error": str(result.error_before_exec or result.error_in_exec) if not result.success else None,
                "execution_count": result.execution_count,
                "result": result.result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_new_cell(self, code: str, cell_type: str = "code", position: str = "below") -> bool:
        """
        Create a new cell in the notebook

        Args:
            code: Content for the new cell
            cell_type: Type of cell ('code' or 'markdown')
            position: Where to insert ('above' or 'below' current cell)

        Returns:
            True if successful, False otherwise
        """
        if not JUPYTER_AVAILABLE:
            return False

        # JavaScript to create a new cell
        js_code = f"""
        var cell_type = '{cell_type}';
        var code = {json.dumps(code)};
        var position = '{position}';

        if (Jupyter && Jupyter.notebook) {{
            var notebook = Jupyter.notebook;
            var current_index = notebook.get_selected_index();
            var new_index = position === 'above' ? current_index : current_index + 1;

            var new_cell = notebook.insert_cell_at_index(cell_type, new_index);
            new_cell.set_text(code);

            if (cell_type === 'code') {{
                new_cell.focus_editor();
            }}

            notebook.select(new_index);
        }}
        """

        try:
            display(Javascript(js_code))
            return True
        except Exception:
            return False

    def get_dataframe_info(self, df_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a DataFrame"""
        df = self.get_variable_by_name(df_name)
        if df is None or not hasattr(df, 'shape'):
            return None

        try:
            info = {
                "name": df_name,
                "shape": df.shape,
                "columns": list(df.columns) if hasattr(df, 'columns') else None,
                "dtypes": df.dtypes.to_dict() if hasattr(df, 'dtypes') else None,
                "memory_usage": df.memory_usage(deep=True).sum() if hasattr(df, 'memory_usage') else None,
                "null_counts": df.isnull().sum().to_dict() if hasattr(df, 'isnull') else None,
                "summary": None
            }

            # Generate summary statistics for numeric columns
            if hasattr(df, 'describe'):
                try:
                    info["summary"] = df.describe().to_dict()
                except:
                    pass

            return info
        except Exception:
            return None

    def create_dataframe_report(self, df_name: str) -> Optional[str]:
        """Create a comprehensive report about a DataFrame"""
        df_info = self.get_dataframe_info(df_name)
        if not df_info:
            return None

        report_lines = [
            f"# DataFrame Report: {df_name}",
            "",
            f"**Shape:** {df_info['shape'][0]:,} rows × {df_info['shape'][1]} columns",
            ""
        ]

        if df_info['memory_usage']:
            memory_mb = df_info['memory_usage'] / (1024 * 1024)
            report_lines.append(f"**Memory Usage:** {memory_mb:.2f} MB")
            report_lines.append("")

        # Column information
        if df_info['columns']:
            report_lines.append("## Columns")
            report_lines.append("")
            report_lines.append("| Column | Type | Null Count |")
            report_lines.append("|--------|------|------------|")

            for col in df_info['columns']:
                dtype = df_info['dtypes'].get(col, 'unknown') if df_info['dtypes'] else 'unknown'
                null_count = df_info['null_counts'].get(col, 0) if df_info['null_counts'] else 0
                report_lines.append(f"| {col} | {dtype} | {null_count:,} |")

            report_lines.append("")

        # Summary statistics
        if df_info['summary']:
            report_lines.append("## Summary Statistics")
            report_lines.append("")

            # Create a simple text table of summary stats
            summary = df_info['summary']
            if summary:
                stats = ['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']
                numeric_cols = [col for col in df_info['columns'] if col in summary][:5]  # Limit to 5 cols

                if numeric_cols:
                    # Header
                    header = "| Statistic |" + "".join([f" {col} |" for col in numeric_cols])
                    separator = "|-----------|" + "".join(["-------|" for _ in numeric_cols])
                    report_lines.append(header)
                    report_lines.append(separator)

                    # Data rows
                    for stat in stats:
                        if stat in summary.get(numeric_cols[0], {}):
                            row = f"| {stat} |"
                            for col in numeric_cols:
                                value = summary.get(col, {}).get(stat, '')
                                if isinstance(value, float):
                                    row += f" {value:.3f} |"
                                else:
                                    row += f" {value} |"
                            report_lines.append(row)

        return "\n".join(report_lines)

    def export_conversation_to_cell(self, conversation: List[Dict[str, Any]], cell_type: str = "markdown") -> bool:
        """Export conversation history to a new notebook cell"""
        if not conversation:
            return False

        # Format conversation as markdown
        content_lines = ["# TATty Agent Conversation", ""]

        for entry in conversation:
            timestamp = entry.get('timestamp', 'Unknown time')
            content_type = entry.get('type', 'unknown')
            content = entry.get('content', '')

            if content_type == 'user_query':
                content_lines.append(f"## 👤 User Query ({timestamp})")
                content_lines.append(f"```")
                content_lines.append(content)
                content_lines.append(f"```")
            elif content_type == 'agent_result':
                content_lines.append(f"## 🤖 Agent Response ({timestamp})")
                tools_used = entry.get('tools_used', 0)
                exec_time = entry.get('execution_time', 0)
                if tools_used or exec_time:
                    content_lines.append(f"*Execution time: {exec_time:.1f}s, Tools used: {tools_used}*")
                content_lines.append("")
                content_lines.append(content)

            content_lines.append("")

        cell_content = "\n".join(content_lines)
        return self.create_new_cell(cell_content, cell_type)

    def _analyze_variable(self, name: str, value: Any) -> Optional[Dict[str, Any]]:
        """Analyze a variable and return its metadata"""
        try:
            var_type = type(value).__name__

            # Basic info
            info = {
                "type": var_type,
                "value": value,
                "size": sys.getsizeof(value)
            }

            # Special handling for different types
            if pd and isinstance(value, pd.DataFrame):
                info.update({
                    "type": "DataFrame",
                    "shape": value.shape,
                    "columns": list(value.columns),
                    "memory_usage": value.memory_usage(deep=True).sum()
                })
                # Don't store full DataFrame in cache, just metadata
                info["value"] = f"<DataFrame {value.shape[0]}x{value.shape[1]}>"

            elif pd and isinstance(value, pd.Series):
                info.update({
                    "type": "Series",
                    "shape": value.shape,
                    "dtype": str(value.dtype)
                })
                info["value"] = f"<Series length={len(value)}>"

            elif np and isinstance(value, np.ndarray):
                info.update({
                    "type": "ndarray",
                    "shape": value.shape,
                    "dtype": str(value.dtype)
                })
                info["value"] = f"<Array {value.shape}>"

            elif isinstance(value, (list, tuple, set)):
                info.update({
                    "length": len(value),
                    "element_types": list(set(type(item).__name__ for item in value)) if value else []
                })
                if len(value) > 10:
                    info["value"] = f"<{var_type} length={len(value)}>"

            elif isinstance(value, dict):
                info.update({
                    "length": len(value),
                    "keys": list(value.keys())[:10] if len(value) <= 10 else list(value.keys())[:10] + ["..."]
                })
                if len(value) > 5:
                    info["value"] = f"<Dict with {len(value)} keys>"

            elif isinstance(value, str):
                if len(value) > 200:
                    info["value"] = value[:200] + "..."
                info["length"] = len(value)

            elif callable(value) and hasattr(value, '__module__'):
                if value.__module__ == '__main__':
                    info["type"] = "function"
                    try:
                        sig = inspect.signature(value)
                        info["signature"] = str(sig)
                    except:
                        pass
                else:
                    return None  # Skip non-user functions

            return info

        except Exception:
            # If we can't analyze it, skip it
            return None

    def get_persistent_agent_state(self, working_dir: str = ".") -> AgentState:
        """
        Get or create the persistent agent state for this notebook session.

        This ensures continuity across all %tatty magic commands and chat widget
        interactions within the same notebook session.

        Args:
            working_dir: Working directory for the agent

        Returns:
            The persistent AgentState instance
        """
        if self._agent_state is None:
            self._agent_state = AgentState(working_dir=working_dir)
            self._working_dir = working_dir

            # Add initial context about notebook environment
            notebook_vars = self.get_notebook_variables()
            if notebook_vars:
                vars_info = f"Notebook session started. Available variables: {', '.join(notebook_vars.keys())}"
                self._agent_state.messages.append(Message(
                    role="assistant",
                    message=f"Session Context: {vars_info}"
                ))
        elif working_dir != self._working_dir:
            # Update working directory if changed
            self._agent_state.working_dir = working_dir
            self._working_dir = working_dir

        return self._agent_state

    def update_agent_context(self, message: str, role: str = "assistant") -> None:
        """
        Add a context message to the persistent agent state.

        Args:
            message: The context message to add
            role: Message role ("user" or "assistant")
        """
        state = self.get_persistent_agent_state()
        state.messages.append(Message(role=role, message=message))

    def clear_agent_memory(self) -> None:
        """
        Clear the persistent agent memory for this notebook session.
        This will start a fresh conversation context.
        """
        self._agent_state = None

    def get_conversation_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current conversation state.

        Returns:
            Dictionary with conversation statistics and recent messages
        """
        if self._agent_state is None:
            return {
                "total_messages": 0,
                "recent_messages": [],
                "conversation_active": False
            }

        messages = self._agent_state.messages
        recent_count = min(5, len(messages))
        recent_messages = [
            {"role": msg.role, "message": str(msg.message)[:100] + ("..." if len(str(msg.message)) > 100 else "")}
            for msg in messages[-recent_count:]
        ]

        return {
            "total_messages": len(messages),
            "recent_messages": recent_messages,
            "conversation_active": len(messages) > 0,
            "working_dir": self._working_dir
        }


# Global notebook context instance
_notebook_context: Optional[NotebookContextManager] = None

def get_notebook_context() -> Optional[NotebookContextManager]:
    """Get the global notebook context manager"""
    global _notebook_context
    if _notebook_context is None and JUPYTER_AVAILABLE:
        _notebook_context = NotebookContextManager()
    return _notebook_context

def get_notebook_variables(refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """Convenience function to get notebook variables"""
    context = get_notebook_context()
    return context.get_notebook_variables(refresh) if context else {}

def execute_in_notebook(code: str, silent: bool = False) -> Dict[str, Any]:
    """Convenience function to execute code in notebook"""
    context = get_notebook_context()
    return context.execute_code(code, silent) if context else {"success": False, "error": "No notebook context"}

def create_cell_with_code(code: str, cell_type: str = "code") -> bool:
    """Convenience function to create a new cell"""
    context = get_notebook_context()
    return context.create_new_cell(code, cell_type) if context else False

def get_agent_conversation_summary() -> Dict[str, Any]:
    """Get summary of current agent conversation in this notebook"""
    context = get_notebook_context()
    return context.get_conversation_summary() if context else {"conversation_active": False}

def clear_agent_memory() -> None:
    """Clear the agent's memory for this notebook session"""
    context = get_notebook_context()
    if context:
        context.clear_agent_memory()
        print("✅ Agent memory cleared. Next interaction will start fresh.")