"""
IPython magic commands for TATty Agent

This module provides %tatty and %%tatty magic commands for seamless
integration with Jupyter notebooks.

Usage:
    %tatty "List all Python files"
    %%tatty
    Find all TODO comments
    and create a summary report
"""
import asyncio
import time
from typing import Any, Dict, List, Optional, Union

try:
    from IPython import get_ipython
    from IPython.core.magic import (
        Magics, line_magic, cell_magic, magics_class, line_cell_magic
    )
    from IPython.core.magic_arguments import (
        parse_argstring, magic_arguments, argument
    )
    from IPython.display import display, clear_output
    JUPYTER_AVAILABLE = True
except ImportError:
    JUPYTER_AVAILABLE = False
    # Fallback for non-Jupyter environments
    class Magics:
        pass

    def magics_class(cls):
        return cls

    def line_magic(name):
        def decorator(func):
            return func
        return decorator

    def cell_magic(name):
        def decorator(func):
            return func
        return decorator

    def line_cell_magic(name):
        def decorator(func):
            return func
        return decorator

    def magic_arguments(func):
        return func

    def argument(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from ..core.runtime import AgentRuntime
from ..core.state import AgentState, AgentCallbacks
from ..config import load_config
from .display import display_agent_response, display_progress_indicator, display_tool_execution
from .notebook import NotebookContextManager


@magics_class
class TattyMagics(Magics):
    """IPython magic commands for TATty Agent integration"""

    def __init__(self, shell=None):
        super().__init__(shell)
        self.tatty_config = load_config()  # Use different name to avoid conflict with IPython's config
        self.notebook_context = NotebookContextManager(shell) if shell else None
        self._current_runtime: Optional[AgentRuntime] = None
        self._execution_history: List[Dict[str, Any]] = []

    @magic_arguments()
    @argument(
        '--dir', '-d',
        type=str,
        default=None,
        help='Working directory for the agent'
    )
    @argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output showing tool executions'
    )
    @argument(
        '--max-iterations', '-i',
        type=int,
        default=20,
        help='Maximum iterations for agent execution'
    )
    @argument(
        '--history',
        action='store_true',
        help='Show conversation history instead of running a query'
    )
    @argument(
        '--clear-history',
        action='store_true',
        help='Clear conversation history'
    )
    @line_cell_magic
    def tatty(self, line: str, cell: str = None):
        """
        TATty Agent magic command

        Line magic:  %tatty "query here"
        Cell magic:  %%tatty
                     multi-line query here

        Options:
            --dir, -d          Working directory
            --verbose, -v      Show tool executions
            --max-iterations   Maximum agent iterations
            --history          Show conversation history
            --clear-history    Clear conversation history
        """
        if not JUPYTER_AVAILABLE:
            print("TATty magic commands require IPython/Jupyter")
            return

        # Parse arguments
        args = parse_argstring(self.tatty, line)

        # Handle special commands
        if args.clear_history:
            self._execution_history.clear()
            display_progress_indicator("Conversation history cleared", show_bar=False)
            return

        if args.history:
            from .display import display_conversation_history
            display_conversation_history(self._execution_history)
            return

        # Determine the query
        if cell is not None:  # Cell magic
            query = cell.strip()
        else:  # Line magic
            query = line.strip()
            # Remove parsed arguments from the query
            import shlex
            try:
                # Simple approach: find the last quoted string or unquoted text
                tokens = shlex.split(line)
                # Remove known argument tokens
                filtered_tokens = []
                skip_next = False
                for i, token in enumerate(tokens):
                    if skip_next:
                        skip_next = False
                        continue
                    if token in ['--dir', '-d', '--max-iterations', '-i']:
                        skip_next = True
                        continue
                    if token in ['--verbose', '-v', '--history', '--clear-history']:
                        continue
                    filtered_tokens.append(token)

                query = ' '.join(filtered_tokens)
            except:
                # Fallback: use original line without argument parsing
                query = line.strip()

        if not query:
            print("❌ Please provide a query for TATty Agent")
            print("Usage: %tatty \"your query here\"")
            print("   or: %%tatty")
            print("       your multi-line query")
            print("       goes here")
            return

        # Set up working directory
        working_dir = args.dir or self.tatty_config.working_dir

        # Execute the agent
        return self._run_agent_query(
            query=query,
            working_dir=working_dir,
            max_iterations=args.max_iterations,
            verbose=args.verbose
        )

    def _run_agent_query(
        self,
        query: str,
        working_dir: str,
        max_iterations: int = 20,
        verbose: bool = False
    ):
        """Execute agent query with rich display"""
        start_time = time.time()

        # Show progress indicator
        display_progress_indicator(f"Processing query: {query[:50]}...")

        try:
            # Set up agent state and callbacks
            state = AgentState(working_dir=working_dir)
            callbacks = self._create_notebook_callbacks(verbose=verbose)
            runtime = AgentRuntime(state, callbacks)
            self._current_runtime = runtime

            # Add notebook context to state if available
            if self.notebook_context:
                notebook_vars = self.notebook_context.get_notebook_variables()
                if notebook_vars:
                    # Add available variables info to the beginning of conversation
                    vars_info = f"Available notebook variables: {', '.join(notebook_vars.keys())}"
                    state.messages.append({
                        "role": "system",
                        "message": f"Context: {vars_info}"
                    })

            # Run the agent
            result = asyncio.run(runtime.run_loop(query, max_iterations))
            execution_time = time.time() - start_time

            # Clear progress indicator
            clear_output(wait=True)

            # Get tools used from the state
            tools_used = getattr(callbacks, '_tools_executed', [])

            # Display rich result
            display_agent_response(
                query=query,
                result=result,
                execution_time=execution_time,
                tools_used=tools_used
            )

            # Add to history
            self._execution_history.append({
                "type": "user_query",
                "content": query,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            self._execution_history.append({
                "type": "agent_result",
                "content": result,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "execution_time": execution_time,
                "tools_used": len(tools_used)
            })

            # Return result for potential variable assignment
            return result

        except KeyboardInterrupt:
            clear_output(wait=True)
            print("❌ Agent execution interrupted by user")
            return "Interrupted"
        except Exception as e:
            clear_output(wait=True)
            print(f"❌ Error executing TATty Agent: {str(e)}")
            if verbose:
                import traceback
                traceback.print_exc()
            return f"Error: {str(e)}"

    def _create_notebook_callbacks(self, verbose: bool = False) -> AgentCallbacks:
        """Create callbacks for notebook display"""
        callbacks = AgentCallbacks()

        # Track executed tools for display
        callbacks._tools_executed = []

        if verbose:
            async def on_tool_start(tool_name: str, params: dict, tool_idx: int, total_tools: int, depth: int):
                display_progress_indicator(f"Executing {tool_name}...", show_bar=False)

            async def on_tool_result(result: str, depth: int):
                # Store the last tool execution for display
                if hasattr(callbacks, '_last_tool_info'):
                    tool_info = callbacks._last_tool_info
                    tool_info['result'] = result
                    tool_info['execution_time'] = time.time() - tool_info['start_time']
                    callbacks._tools_executed.append(tool_info)

                    # Display tool execution immediately in verbose mode
                    display_tool_execution(
                        tool_name=tool_info['name'],
                        params=tool_info['params'],
                        result=result,
                        execution_time=tool_info['execution_time']
                    )

            async def on_status_update(status: str, iteration: int):
                display_progress_indicator(f"Iteration {iteration}: {status}", show_bar=False)

            callbacks.on_tool_start = on_tool_start
            callbacks.on_tool_result = on_tool_result
            callbacks.on_status_update = on_status_update

        return callbacks

    @line_magic
    def tatty_history(self, line: str):
        """Show TATty Agent conversation history"""
        from .display import display_conversation_history
        display_conversation_history(self._execution_history)

    @line_magic
    def tatty_clear(self, line: str):
        """Clear TATty Agent conversation history"""
        self._execution_history.clear()
        display_progress_indicator("Conversation history cleared", show_bar=False)

    @line_magic
    def tatty_vars(self, line: str):
        """Show available notebook variables that TATty can access"""
        if not self.notebook_context:
            print("Notebook context not available")
            return

        variables = self.notebook_context.get_notebook_variables()

        if not variables:
            print("No variables available in notebook")
            return

        print("📊 Available Notebook Variables:")
        print("=" * 40)

        for name, info in variables.items():
            var_type = info.get('type', 'unknown')
            value_preview = str(info.get('value', ''))
            if len(value_preview) > 100:
                value_preview = value_preview[:97] + "..."

            print(f"  {name}: {var_type}")
            if hasattr(info.get('value'), 'shape'):  # DataFrame, array, etc.
                print(f"    Shape: {info['value'].shape}")
            elif isinstance(info.get('value'), (list, dict, str)):
                print(f"    Length: {len(info['value'])}")

            if var_type in ['DataFrame', 'Series']:
                print(f"    Columns: {list(info['value'].columns) if hasattr(info['value'], 'columns') else 'N/A'}")

            print(f"    Preview: {value_preview}")
            print()


def load_ipython_extension(ipython):
    """Load the TATty magic extension"""
    if not JUPYTER_AVAILABLE:
        print("Warning: TATty magic commands require IPython/Jupyter")
        return

    try:
        # Register the magic class
        magics = TattyMagics(ipython)
        ipython.register_magic_function(magics.tatty, 'line_cell')
        ipython.register_magic_function(magics.tatty_history, 'line')
        ipython.register_magic_function(magics.tatty_clear, 'line')
        ipython.register_magic_function(magics.tatty_vars, 'line')

        print("🎉 TATty Agent magic commands loaded!")
        print("Available commands:")
        print("  %tatty \"query\"       - Run a single query")
        print("  %%tatty               - Run multi-line query")
        print("  %tatty_history        - Show conversation history")
        print("  %tatty_clear          - Clear conversation history")
        print("  %tatty_vars           - Show notebook variables")
        print()
        print("Options: --verbose, --dir, --max-iterations, --history, --clear-history")

    except Exception as e:
        print(f"Error loading TATty magic commands: {e}")


def unload_ipython_extension(ipython):
    """Unload the TATty magic extension"""
    # IPython will handle cleanup automatically
    pass


# Auto-load if in IPython environment
if JUPYTER_AVAILABLE:
    try:
        ipython = get_ipython()
        if ipython is not None:
            load_ipython_extension(ipython)
    except:
        pass  # Silently fail if not in interactive environment