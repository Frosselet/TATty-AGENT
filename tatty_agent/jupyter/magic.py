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
        def __init__(self, shell=None):
            self.shell = shell

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

    def magic_arguments(func=None):
        if func is None:
            # Called as @magic_arguments()
            def decorator(f):
                return f
            return decorator
        else:
            # Called as @magic_arguments
            return func

    def argument(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


from ..core.runtime import AgentRuntime
from ..core.state import AgentState, AgentCallbacks
from ..core.types import Message
from ..config import load_config
from .display import display_agent_response, display_progress_indicator, display_tool_execution
from .notebook import NotebookContextManager


class ErrorHandlingConfig:
    """Configuration for enhanced error handling behavior"""

    def __init__(self):
        self.enable_code_correction = True  # Enable automatic code error correction
        self.max_retry_attempts = 3        # Maximum number of retry attempts
        self.enable_dependency_auto_install = True  # Auto-install missing packages
        self.correction_timeout = 30.0     # Timeout for code correction in seconds
        self.show_correction_details = True  # Show detailed correction process

        # Error types to handle with automatic correction
        self.handled_error_types = {
            'TypeError', 'NameError', 'AttributeError', 'ValueError',
            'KeyError', 'IndexError', 'RuntimeError'
        }

    def should_handle_error(self, error_type: str) -> bool:
        """Check if an error type should be handled automatically"""
        return self.enable_code_correction and error_type in self.handled_error_types


@magics_class
class TattyMagics(Magics):
    """IPython magic commands for TATty Agent integration"""

    def __init__(self, shell=None):
        super().__init__(shell)
        self.tatty_config = load_config()  # Use different name to avoid conflict with IPython's config
        self.notebook_context = NotebookContextManager(shell) if shell else None
        self._current_runtime: Optional[AgentRuntime] = None
        self._execution_history: List[Dict[str, Any]] = []
        self._observability_session: List[Dict[str, Any]] = []  # Session-level observability tracking

        # Enhanced error handling configuration
        self.error_config = ErrorHandlingConfig()

        # Configure BAML logging to suppress debug output
        self._configure_baml_logging()

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
    @argument(
        '--fresh',
        action='store_true',
        help='Start with fresh context (ignore conversation history)'
    )
    @argument(
        '--history-limit',
        type=int,
        default=5,
        help='Maximum number of recent messages to include (default: 5)'
    )
    @argument(
        'query',
        nargs='*',
        help='The query for TATty Agent to process'
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
            --fresh            Start with fresh context (no history)
            --history-limit    Max recent messages to include (default: 5)
        """
        if not JUPYTER_AVAILABLE:
            print("TATty magic commands require IPython/Jupyter")
            return

        # Parse arguments using IPython's magic_arguments system
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
            # Join the query list back into a string (due to nargs='*')
            query = ' '.join(args.query) if args.query else ""

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
            verbose=args.verbose,
            fresh=args.fresh,
            history_limit=args.history_limit
        )

    def _run_agent_query(
        self,
        query: str,
        working_dir: str,
        max_iterations: int = 20,
        verbose: bool = False,
        fresh: bool = False,
        history_limit: int = 5
    ):
        """Execute agent query with rich display and observability"""
        import uuid
        from datetime import datetime, timezone

        execution_start = time.time()
        execution_id = str(uuid.uuid4())

        # Initialize observability tracking
        observability = {
            "execution_id": execution_id,
            "query": query,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "working_dir": working_dir,
            "max_iterations": max_iterations,
            "fresh": fresh,
            "history_limit": history_limit,
            "steps": [],
            "total_tokens": {"input": 0, "output": 0},
            "status": "running"
        }

        # Show progress indicator
        display_progress_indicator(f"Processing query: {query[:50]}...")

        try:
            # Create agent state with smart context management
            if fresh or not self.notebook_context:
                # Start with fresh state
                state = AgentState(working_dir=working_dir)
            else:
                # Use limited conversation history for better focus
                full_state = self.notebook_context.get_persistent_agent_state(working_dir)
                state = AgentState(working_dir=working_dir)

                # Keep only recent relevant messages (limit conversation history)
                if full_state.messages and history_limit > 0:
                    recent_messages = full_state.messages[-history_limit:]
                    # Filter out system/context messages, keep user queries and agent responses
                    relevant_messages = []
                    for msg in recent_messages:
                        msg_text = str(msg.message)
                        if not (msg_text.startswith("Context:") or
                               msg_text.startswith("Available notebook variables:") or
                               msg_text.startswith("Tool:")):
                            relevant_messages.append(msg)

                    state.messages = relevant_messages[-3:]  # Keep max 3 recent relevant messages

            # Add current notebook variables (fresh each time, don't accumulate)
            if self.notebook_context and not fresh:
                notebook_vars = self.notebook_context.get_notebook_variables(refresh=True)
                if notebook_vars:
                    vars_info = f"Available notebook variables: {', '.join(notebook_vars.keys())}"
                    state.messages.append(Message(
                        role="assistant",
                        message=f"Context: {vars_info}"
                    ))

            # Step 1: Classify user intent with observability tracking
            from ..baml_client.async_client import b
            from ..baml_client import types

            intent_start = time.time()
            intent_start_iso = datetime.now(timezone.utc).isoformat()
            print(f"🔍 Classifying user intent...")

            intent_result = asyncio.run(b.ClassifyUserIntent(user_query=query))
            intent_end = time.time()
            intent_duration = intent_end - intent_start

            # Show real-time progress
            print(f"🎯 Intent classified as: {intent_result.intent} ({intent_result.confidence})")
            print(f"   Reasoning: {intent_result.reasoning}")

            # Add to observability tracking
            intent_step = {
                "step": "intent_classification",
                "model": "openai-responses/gpt-5-mini",
                "start_time": intent_start_iso,
                "end_time": datetime.now(timezone.utc).isoformat(),
                "duration": intent_duration,
                "tokens": {"input": len(query.split()) * 1.3, "output": len(intent_result.reasoning.split()) * 1.3},  # Rough estimate
                "input_messages": [{"role": "user", "content": query}],
                "output": {
                    "intent": str(intent_result.intent),
                    "confidence": intent_result.confidence,
                    "reasoning": intent_result.reasoning
                },
                "status": "success"
            }
            observability["steps"].append(intent_step)
            observability["total_tokens"]["input"] += intent_step["tokens"]["input"]
            observability["total_tokens"]["output"] += intent_step["tokens"]["output"]

            # Capture decision-making process for HTML display (legacy)
            decision_steps = []
            decision_steps.append({
                "name": "Intent Classification",
                "params": {"query": query},
                "result": f"Intent: {intent_result.intent}\nConfidence: {intent_result.confidence}\nReasoning: {intent_result.reasoning}",
                "execution_time": intent_duration
            })

            if verbose:
                print(f"🔍 Routing to intent-specific handler...")

            # Step 2: Route to intent-specific handler with observability
            if intent_result.intent == types.UserIntent.ExecutableCode:
                result, response_obj, handler_steps = asyncio.run(self._handle_code_generation(query, intent_result, state, working_dir, verbose, observability))
            elif intent_result.intent == types.UserIntent.TextResponse:
                result, response_obj, handler_steps = asyncio.run(self._handle_text_response(query, intent_result, state, working_dir, verbose, observability))
            else:  # tool_execution
                result, response_obj, handler_steps = asyncio.run(self._handle_tool_execution(query, intent_result, state, working_dir, max_iterations, verbose, observability))

            # Combine decision steps (legacy)
            decision_steps.extend(handler_steps or [])

            total_execution_time = time.time() - execution_start

            # Finalize observability data
            observability["end_time"] = datetime.now(timezone.utc).isoformat()
            observability["total_duration"] = total_execution_time
            observability["status"] = "success"

            # Clear progress indicator
            clear_output(wait=True)

            # Execute Python code if the response contains it
            code_execution_start = time.time()
            self._handle_code_execution(response_obj, original_query=query)
            code_execution_time = time.time() - code_execution_start

            if code_execution_time > 0.01:  # Only track if meaningful execution happened
                observability["steps"].append({
                    "step": "code_execution",
                    "model": "local_python",
                    "start_time": datetime.now(timezone.utc).isoformat(),
                    "end_time": datetime.now(timezone.utc).isoformat(),
                    "duration": code_execution_time,
                    "tokens": {"input": 0, "output": 0},
                    "output": {"executed": True, "response_type": type(response_obj).__name__ if response_obj else None},
                    "status": "success"
                })

            # Ensure result is always a string for display
            display_result = str(result)

            # Add to session observability tracking
            self._observability_session.append(observability)

            # Display rich result with observability data
            display_agent_response(
                query=query,
                result=display_result,
                execution_time=total_execution_time,
                tools_used=decision_steps,
                observability_data=observability
            )

            # Add to history
            self._execution_history.append({
                "type": "user_query",
                "content": query,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            self._execution_history.append({
                "type": "agent_result",
                "content": display_result,  # Use the display string
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "execution_time": total_execution_time,
                "tools_used": len(decision_steps)
            })

            # Return display result for potential variable assignment
            return display_result

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

    async def _handle_code_generation(self, query: str, intent_result, state: AgentState, working_dir: str, verbose: bool, observability: dict):
        """Handle executable_code intent - try AgentDispatcher first, fall back to full loop if needed"""
        from ..baml_client.async_client import b
        from ..baml_client import types
        from datetime import datetime, timezone
        import time

        steps = []
        start_time = time.time()
        start_time_iso = datetime.now(timezone.utc).isoformat()

        # Show real-time progress
        print(f"🔧 Code Generation Mode: Generating executable Python code...")

        # Call AgentDispatcher for code generation
        response = asyncio.run(b.AgentDispatcher(
            user_query=query,
            intent=intent_result,
            state=state.messages,
            working_dir=working_dir
        ))

        dispatcher_time = time.time() - start_time
        end_time_iso = datetime.now(timezone.utc).isoformat()

        # Show real-time progress
        print(f"🔍 AgentDispatcher returned: {type(response).__name__}")

        # Add to observability tracking
        code_gen_step = {
            "step": "code_generation",
            "model": "openai-responses/gpt-5-mini",
            "start_time": start_time_iso,
            "end_time": end_time_iso,
            "duration": dispatcher_time,
            "tokens": {"input": len(query.split()) * 2.5, "output": 0},  # Will update based on response
            "input_messages": [{"role": "user", "content": query}],
            "output": {},
            "status": "success"
        }

        # Legacy decision steps (for existing UI)
        steps.append({
            "name": "Code Generation",
            "params": {"mode": "AgentDispatcher", "intent": str(intent_result.intent)},
            "result": f"Response type: {type(response).__name__}\nMode: Direct code generation via AgentDispatcher",
            "execution_time": dispatcher_time
        })

        # Check what we got back
        if isinstance(response, types.ReplyWithCode):
            print(f"✅ Agent generated executable Python code")
            print(f"📝 Generated code: {response.message}")

            # Update observability with response details
            code_gen_step["tokens"]["output"] = len(response.python_code.split()) * 1.3 + len(response.message.split()) * 1.3
            code_gen_step["output"] = {
                "response_type": "ReplyWithCode",
                "message": response.message,
                "code_length": len(response.python_code),
                "python_code": response.python_code
            }
            observability["steps"].append(code_gen_step)
            observability["total_tokens"]["input"] += code_gen_step["tokens"]["input"]
            observability["total_tokens"]["output"] += code_gen_step["tokens"]["output"]

            steps.append({
                "name": "Python Code Generated",
                "params": {"code_length": len(response.python_code), "has_message": bool(response.message)},
                "result": f"Successfully generated executable Python code:\n\n{response.python_code}",
                "execution_time": 0.01
            })
            return response.message, response, steps
        elif isinstance(response, types.ReplyToUser):
            # Agent returned text instead of code - this might indicate it needs tools
            print(f"⚠️  Agent returned text instead of code - may need tool execution")
            print(f"🔄 Falling back to full agent loop for complex code generation...")
            steps.append({
                "name": "Fallback to Full Agent Loop",
                "params": {"reason": "text_response_instead_of_code"},
                "result": "Agent returned text response instead of code. Falling back to full agent loop for complex code generation.",
                "execution_time": 0.01
            })
            # Fall back to full agent loop which can use tools
            result, response_obj, loop_steps = asyncio.run(self._run_full_agent_loop(query, state, working_dir, verbose))
            steps.extend(loop_steps or [])
            return result, response_obj, steps
        else:
            # Tool execution needed - agent wants to use tools before generating code
            print(f"🛠️  Agent needs to use tools before generating code")
            print(f"🔄 Running full agent loop to show tool decisions...")
            steps.append({
                "name": "Fallback to Full Agent Loop",
                "params": {"reason": "tool_execution_needed"},
                "result": "Agent needs to use tools before generating code. Running full agent loop to show tool decisions.",
                "execution_time": 0.01
            })
            # Fall back to full agent loop to show tool execution process
            result, response_obj, loop_steps = asyncio.run(self._run_full_agent_loop(query, state, working_dir, verbose))
            steps.extend(loop_steps or [])
            return result, response_obj, steps

    async def _handle_text_response(self, query: str, intent_result, state: AgentState, working_dir: str, verbose: bool, observability: dict):
        """Handle text_response intent using AgentDispatcher"""
        from ..baml_client.async_client import b
        from ..baml_client import types
        import time

        steps = []
        start_time = time.time()

        # Call AgentDispatcher for text response
        response = asyncio.run(b.AgentDispatcher(
            user_query=query,
            intent=intent_result,
            state=state.messages,
            working_dir=working_dir
        ))

        dispatcher_time = time.time() - start_time

        steps.append({
            "name": "Text Response Generation",
            "params": {"mode": "AgentDispatcher", "intent": str(intent_result.intent)},
            "result": f"Response type: {type(response).__name__}\nMode: Direct text response via AgentDispatcher",
            "execution_time": dispatcher_time
        })

        # Should get ReplyToUser for text_response intent
        if isinstance(response, types.ReplyToUser):
            steps.append({
                "name": "Text Response Completed",
                "params": {"response_length": len(response.message)},
                "result": f"Successfully generated text response:\n\n{response.message}",
                "execution_time": 0.01
            })
            return response.message, response, steps
        elif isinstance(response, types.ReplyWithCode):
            # Agent returned code instead of text - execute it anyway
            steps.append({
                "name": "Unexpected Code Response",
                "params": {"expected": "text", "received": "code"},
                "result": f"Agent returned code instead of text for text_response intent. Code will be executed anyway:\n\n{response.python_code}",
                "execution_time": 0.01
            })
            return response.message, response, steps
        else:
            # Tool execution - shouldn't happen for text_response intent
            steps.append({
                "name": "Unexpected Tool Response",
                "params": {"expected": "text", "received": "tool"},
                "result": f"Agent returned tool instead of text for text_response intent. Falling back to tool execution.",
                "execution_time": 0.01
            })
            # Fall back to tool execution
            result, response_obj = asyncio.run(self._execute_agent_tools(response, state, working_dir, verbose))
            return result, response_obj, steps

    async def _handle_tool_execution(self, query: str, intent_result, state: AgentState, working_dir: str, max_iterations: int, verbose: bool, observability: dict):
        """Handle tool_execution intent using full agent runtime loop"""
        steps = []

        # For tool execution, we need to run the full agent loop with callbacks
        callbacks = self._create_notebook_callbacks(verbose)

        # Create runtime with callbacks for tool execution
        runtime = AgentRuntime(state, callbacks)

        steps.append({
            "name": "Tool Execution Mode",
            "params": {"max_iterations": max_iterations, "intent": str(intent_result.intent)},
            "result": "Running full agent loop to handle tool execution requests. This enables file operations, web searches, and system commands.",
            "execution_time": 0.01
        })

        # Run the agent loop
        result = asyncio.run(runtime.run_loop(query, max_iterations))

        # Get the last response object if available
        response_obj = getattr(state, 'last_response', None)

        # Capture tool executions from callbacks
        tools_count = len(callbacks._tools_executed) if hasattr(callbacks, '_tools_executed') else 0

        if tools_count > 0:
            # Add tool execution summary
            tools_summary = []
            for tool in getattr(callbacks, '_tools_executed', []):
                tools_summary.append(f"• {tool.get('name', 'Unknown')}: {tool.get('execution_time', 0):.2f}s")

            steps.append({
                "name": "Tools Executed",
                "params": {"tool_count": tools_count},
                "result": f"Successfully executed {tools_count} tools:\n\n" + "\n".join(tools_summary),
                "execution_time": sum(tool.get('execution_time', 0) for tool in getattr(callbacks, '_tools_executed', []))
            })

        steps.append({
            "name": "Agent Loop Completed",
            "params": {"result_length": len(str(result)), "tools_used": tools_count},
            "result": f"Agent loop completed successfully. Final result:\n\n{result}",
            "execution_time": 0.01
        })

        return result, response_obj, steps

    async def _execute_agent_tools(self, response, state: AgentState, working_dir: str, verbose: bool):
        """Execute a single tool response (fallback helper)"""
        # Import tool executor
        from ..tools.registry import execute_tool

        try:
            result = asyncio.run(execute_tool(response, working_dir))
            if verbose:
                print(f"✅ Executed tool: {response.action}")
            return result, response
        except Exception as e:
            error_msg = f"Error executing tool {response.action}: {str(e)}"
            if verbose:
                print(f"❌ {error_msg}")
            return error_msg, response

    async def _run_full_agent_loop(self, query: str, state: AgentState, working_dir: str, verbose: bool):
        """Run the full agent loop to show tool execution decisions"""
        steps = []

        # Show real-time progress
        print(f"🔄 Running full agent analysis to show decision-making process...")

        # Create callbacks to capture tool executions
        callbacks = self._create_notebook_callbacks(verbose=True)  # Always show tools for transparency

        steps.append({
            "name": "Full Agent Analysis",
            "params": {"max_iterations": 10, "verbose": True},
            "result": "Running comprehensive agent analysis with tool execution capabilities to handle complex requests.",
            "execution_time": 0.01
        })

        # Create runtime with callbacks
        runtime = AgentRuntime(state, callbacks)

        # Run the agent loop
        result = asyncio.run(runtime.run_loop(query, max_iterations=10))

        # Get the last response object if available
        response_obj = getattr(state, 'last_response', None)

        # Capture tool executions from callbacks
        tools_count = len(callbacks._tools_executed) if hasattr(callbacks, '_tools_executed') else 0

        if tools_count > 0:
            # Add detailed tool execution information
            tools_details = []
            for tool in getattr(callbacks, '_tools_executed', []):
                tool_name = tool.get('name', 'Unknown')
                tool_time = tool.get('execution_time', 0)
                tool_result = tool.get('result', '')
                tools_details.append(f"• {tool_name} ({tool_time:.2f}s): {tool_result[:100]}{'...' if len(tool_result) > 100 else ''}")

            steps.append({
                "name": "Comprehensive Tool Execution",
                "params": {"tool_count": tools_count},
                "result": f"Executed {tools_count} tools during analysis:\n\n" + "\n".join(tools_details),
                "execution_time": sum(tool.get('execution_time', 0) for tool in getattr(callbacks, '_tools_executed', []))
            })

        steps.append({
            "name": "Analysis Completed",
            "params": {"result_type": type(response_obj).__name__ if response_obj else "string", "tools_used": tools_count},
            "result": f"Agent analysis completed successfully with {tools_count} tool executions.\n\nFinal result: {result}",
            "execution_time": 0.01
        })

        # Show real-time completion
        print(f"📋 Agent completed analysis and decision-making")

        return result, response_obj, steps

    def _create_notebook_callbacks(self, verbose: bool = False) -> AgentCallbacks:
        """Create callbacks for notebook display"""
        callbacks = AgentCallbacks()

        # Track executed tools for display
        callbacks._tools_executed = []

        # Always show clean tool usage messages (not just in verbose mode)
        async def on_tool_start(tool_name: str, params: dict, tool_idx: int, total_tools: int, depth: int):
            # Store tool info for result processing
            callbacks._last_tool_info = {
                'name': tool_name,
                'params': params,
                'start_time': time.time(),
                'tool_idx': tool_idx,
                'total_tools': total_tools
            }

            # Show clean tool usage message
            reason = self._get_tool_reason(tool_name, params)
            if not verbose:
                # Clean, one-line message for non-verbose mode
                print(f"🛠️ TATty used {tool_name} to {reason}")
            else:
                # More detailed message for verbose mode
                display_progress_indicator(f"Executing {tool_name}: {reason}", show_bar=False)

        async def on_tool_result(result: str, depth: int):
            # Store the last tool execution for display
            if hasattr(callbacks, '_last_tool_info'):
                tool_info = callbacks._last_tool_info
                tool_info['result'] = result
                tool_info['execution_time'] = time.time() - tool_info['start_time']
                callbacks._tools_executed.append(tool_info)

                # Only display detailed tool execution in verbose mode
                if verbose:
                    display_tool_execution(
                        tool_name=tool_info['name'],
                        params=tool_info['params'],
                        result=result,
                        execution_time=tool_info['execution_time']
                    )

        async def on_status_update(status: str, iteration: int):
            if verbose:
                display_progress_indicator(f"Iteration {iteration}: {status}", show_bar=False)

            callbacks.on_tool_start = on_tool_start
            callbacks.on_tool_result = on_tool_result
            callbacks.on_status_update = on_status_update

        return callbacks


    def _configure_baml_logging(self):
        """Configure BAML logging to suppress debug output in Jupyter"""
        try:
            import os
            # Set BAML log level to ERROR to suppress INFO/WARN messages
            os.environ["BAML_LOG"] = "ERROR"

            # Also configure via the API if available
            from ..baml_client.config import set_log_level
            set_log_level("ERROR")
        except Exception:
            pass  # Fail silently if BAML logging config is not available


    def _handle_code_execution(self, response_obj, original_query: str = None):
        """Execute Python code if the response contains it"""
        if response_obj is None:
            return  # No structured response available

        try:
            from ..baml_client import types

            if hasattr(types, 'ReplyWithCode') and isinstance(response_obj, types.ReplyWithCode):
                code = response_obj.python_code
                if code:
                    print(f"🔧 Executing Python code from agent...")
                    try:
                        # Execute the code in the IPython environment
                        from IPython import get_ipython
                        shell = get_ipython()
                        if shell:
                            exec_result = shell.run_cell(code, store_history=True, silent=False)
                            if exec_result.error_before_exec or exec_result.error_in_exec:
                                error_msg = str(exec_result.error_in_exec)
                                print(f"⚠️ Error executing generated code: {error_msg}")

                                # Enhanced error handling with query context
                                self._handle_execution_error(error_msg, code, original_query)
                            else:
                                print(f"✅ Python code executed successfully")
                        else:
                            print("⚠️ IPython shell not available")
                    except Exception as e:
                        error_msg = str(e)
                        print(f"⚠️ Error executing generated code: {error_msg}")

                        # Enhanced error handling with query context
                        self._handle_execution_error(error_msg, code, original_query)
        except Exception as e:
            pass  # Fallback to no code execution

    def _get_tool_reason(self, tool_name: str, params: dict) -> str:
        """Get a human-readable reason for why a tool was used"""
        tool_reasons = {
            'Dependency': lambda p: f"check if {', '.join(p.get('packages', ['packages']))} are available" if p.get('check_type') == 'imports' else 'check dependencies',
            'Read': lambda p: f"read file {p.get('file_path', 'unknown')}" if p.get('file_path') else 'read a file',
            'Write': lambda p: f"write to {p.get('file_path', 'a file')}" if p.get('file_path') else 'write a file',
            'Edit': lambda p: f"edit {p.get('file_path', 'a file')}" if p.get('file_path') else 'edit a file',
            'Bash': lambda p: f"run command: {p.get('command', 'unknown')[:50]}{'...' if len(p.get('command', '')) > 50 else ''}" if p.get('command') else 'run a command',
            'Glob': lambda p: f"find files matching '{p.get('pattern', 'unknown')}'" if p.get('pattern') else 'find files',
            'Grep': lambda p: f"search for '{p.get('pattern', 'unknown')}' in files" if p.get('pattern') else 'search files',
            'WebFetch': lambda p: f"fetch content from {p.get('url', 'unknown URL')}" if p.get('url') else 'fetch web content',
            'WebSearch': lambda p: f"search the web for '{p.get('query', 'unknown')}'" if p.get('query') else 'search the web',
            'TodoWrite': lambda p: 'update task list',
            'TodoRead': lambda p: 'check current tasks',
            'NotebookEdit': lambda p: f"edit notebook cell {p.get('cell_number', 'unknown')}" if 'cell_number' in p else 'edit notebook cell',
            'InstallPackages': lambda p: f"install packages: {', '.join(p.get('packages', ['unknown']))}" if p.get('packages') else 'install packages',
            'ArtifactManagement': lambda p: f"{p.get('action_type', 'manage')} artifacts" if p.get('action_type') else 'manage artifacts',
            'Agent': lambda p: f"delegate task: {p.get('description', 'unknown task')}" if p.get('description') else 'delegate to sub-agent'
        }

        if tool_name in tool_reasons:
            try:
                return tool_reasons[tool_name](params)
            except Exception:
                return f"use {tool_name}"
        else:
            return f"use {tool_name}"

    def _handle_execution_error(self, error_msg: str, original_code: str, original_query: str = None, retry_count: int = 0):
        """Enhanced error handling for both dependencies and code logic errors"""
        import re
        import subprocess
        import sys
        import asyncio

        # Use configuration for error handling behavior
        max_retries = self.error_config.max_retry_attempts
        enable_code_correction = self.error_config.enable_code_correction

        # First, check if it's a missing dependency error
        module_match = re.search(r"No module named '([^']+)'", error_msg)
        if module_match and self.error_config.enable_dependency_auto_install:
            return self._handle_dependency_error(error_msg, original_code, original_query, retry_count)

        # Enhanced: Handle logic/syntax errors with LLM correction
        if enable_code_correction and original_query and retry_count < max_retries:
            error_type = self._classify_error_type(error_msg)
            if self.error_config.should_handle_error(error_type):
                return self._handle_code_logic_error(error_msg, original_code, original_query, retry_count)

        # If we reach here, either correction is disabled or max retries exceeded
        print(f"⚠️ Code execution failed: {error_msg}")
        if retry_count >= max_retries:
            print(f"🚫 Max retry attempts ({max_retries}) reached. Please try modifying your request.")
        if not enable_code_correction:
            print(f"💡 Automatic error correction is disabled. Enable with: %tatty_config enable_code_correction True")
        print(f"💡 You can request code correction manually: %tatty \"Fix the error: {error_msg[:100]}...\"")

    def _handle_dependency_error(self, error_msg: str, original_code: str, original_query: str = None, retry_count: int = 0):
        """Handle missing module dependencies"""
        import re
        import subprocess
        import sys

        module_match = re.search(r"No module named '([^']+)'", error_msg)
        missing_module = module_match.group(1)
        print(f"🔍 Detected missing module: {missing_module}")

        # Map common modules to their package names
        module_to_package = {
            'matplotlib': 'matplotlib',
            'seaborn': 'seaborn',
            'pandas': 'pandas',
            'numpy': 'numpy',
            'sklearn': 'scikit-learn',
            'cv2': 'opencv-python',
            'PIL': 'Pillow',
            'requests': 'requests'
        }

        package_name = module_to_package.get(missing_module, missing_module)
        print(f"🔧 Auto-installing package: {package_name}")

        try:
            # Auto-install the package using pip
            print(f"📦 Installing {package_name}...")
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', package_name
            ], capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                print(f"✅ Successfully installed {package_name}!")
                print(f"🔄 Retrying code execution...")

                # Re-execute the original code
                try:
                    from IPython import get_ipython
                    shell = get_ipython()
                    if shell:
                        exec_result = shell.run_cell(original_code, store_history=True, silent=False)
                        if exec_result.error_before_exec or exec_result.error_in_exec:
                            print(f"⚠️ Code still failed after installing {package_name}: {exec_result.error_in_exec}")
                            # Try to handle any additional missing dependencies
                            error_msg_new = str(exec_result.error_in_exec)
                            if "No module named" in error_msg_new and error_msg_new != error_msg:
                                print(f"🔄 Attempting to install additional dependencies...")
                                self._handle_execution_error(error_msg_new, original_code, original_query, retry_count)
                            elif original_query:  # If still failing and we have query, try code correction
                                self._handle_code_logic_error(error_msg_new, original_code, original_query, retry_count)
                        else:
                            print(f"🎉 Code executed successfully after installing {package_name}!")
                except Exception as e:
                    print(f"⚠️ Error re-executing code: {e}")
            else:
                print(f"❌ Failed to install {package_name}")
                print(f"Error: {result.stderr}")
                print(f"\n💡 Manual fallback options:")
                print(f"   pip install {package_name}")
                print(f"   %tatty \"Install {package_name} package\"")

        except subprocess.TimeoutExpired:
            print(f"⏰ Installation timed out for {package_name}")
            print(f"💡 Try manually: pip install {package_name}")
        except Exception as e:
            print(f"⚠️ Error during auto-installation: {e}")
            print(f"💡 Manual fallback:")
            print(f"   pip install {package_name}")
            print(f"   %tatty \"Install {package_name} package\"")

    def _handle_code_logic_error(self, error_msg: str, original_code: str, original_query: str, retry_count: int = 0):
        """Handle code logic errors using LLM correction"""
        import asyncio
        import time

        max_retries = self.error_config.max_retry_attempts
        retry_count += 1

        if retry_count > max_retries:
            print(f"🚫 Max retry attempts ({max_retries}) reached for code correction.")
            return

        # Classify error type
        error_type = self._classify_error_type(error_msg)

        if self.error_config.show_correction_details:
            print(f"🔧 Attempting to fix {error_type} (attempt {retry_count}/{max_retries})...")
            print(f"🧠 Using AI to analyze and correct the code...")
        else:
            print(f"🔧 Fixing {error_type} (attempt {retry_count}/{max_retries})...")

        try:
            from ..baml_client.async_client import b
            from ..baml_client import types

            # Call the FixCodeError function
            correction_start = time.time()
            corrected_response = asyncio.run(b.FixCodeError(
                original_query=original_query,
                failed_code=original_code,
                error_message=error_msg,
                error_type=error_type,
                attempt_number=retry_count
            ))
            correction_time = time.time() - correction_start

            if isinstance(corrected_response, types.ReplyWithCode):
                corrected_code = corrected_response.python_code
                print(f"🔧 Generated corrected code ({correction_time:.1f}s)")
                print(f"💡 Fix explanation: {corrected_response.message}")

                # Execute the corrected code
                try:
                    from IPython import get_ipython
                    shell = get_ipython()
                    if shell:
                        print(f"🔄 Executing corrected code...")
                        exec_result = shell.run_cell(corrected_code, store_history=True, silent=False)

                        if exec_result.error_before_exec or exec_result.error_in_exec:
                            # Still failed, try again with recursive call
                            new_error_msg = str(exec_result.error_in_exec)
                            print(f"⚠️ Corrected code still failed: {new_error_msg}")

                            # Check if it's a different error or we should retry
                            if new_error_msg != error_msg and retry_count < max_retries:
                                self._handle_execution_error(new_error_msg, corrected_code, original_query, retry_count)
                            else:
                                print(f"🚫 Unable to automatically fix the error after {retry_count} attempts.")
                                print(f"💡 Please try rephrasing your request or providing more specific requirements.")
                        else:
                            print(f"🎉 Code executed successfully after error correction!")
                except Exception as e:
                    print(f"⚠️ Error executing corrected code: {e}")
            else:
                print(f"⚠️ Unexpected response type from error correction: {type(corrected_response)}")

        except Exception as e:
            print(f"⚠️ Error during code correction: {e}")
            print(f"💡 Falling back to manual correction required.")

    def _classify_error_type(self, error_msg: str) -> str:
        """Classify the type of error for better correction prompts"""
        error_msg_lower = error_msg.lower()

        if "typeerror" in error_msg_lower:
            return "TypeError"
        elif "nameerror" in error_msg_lower:
            return "NameError"
        elif "attributeerror" in error_msg_lower:
            return "AttributeError"
        elif "valueerror" in error_msg_lower:
            return "ValueError"
        elif "keyerror" in error_msg_lower:
            return "KeyError"
        elif "indexerror" in error_msg_lower:
            return "IndexError"
        elif "syntaxerror" in error_msg_lower:
            return "SyntaxError"
        elif "indentationerror" in error_msg_lower:
            return "IndentationError"
        else:
            return "RuntimeError"

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

    @magic_arguments()
    @argument(
        'setting',
        nargs='?',
        type=str,
        default=None,
        help='Configuration setting to view or modify'
    )
    @argument(
        'value',
        nargs='?',
        type=str,
        default=None,
        help='New value for the setting'
    )
    @line_magic
    def tatty_config(self, line: str):
        """Configure TATty Agent error handling behavior"""
        args = parse_argstring(self.tatty_config, line)

        if not args.setting:
            # Show all current settings
            print("🔧 TATty Agent Error Handling Configuration:")
            print("=" * 50)
            print(f"  enable_code_correction: {self.error_config.enable_code_correction}")
            print(f"  max_retry_attempts: {self.error_config.max_retry_attempts}")
            print(f"  enable_dependency_auto_install: {self.error_config.enable_dependency_auto_install}")
            print(f"  correction_timeout: {self.error_config.correction_timeout}s")
            print(f"  show_correction_details: {self.error_config.show_correction_details}")
            print(f"  handled_error_types: {', '.join(sorted(self.error_config.handled_error_types))}")
            print()
            print("💡 Usage examples:")
            print("   %tatty_config enable_code_correction True")
            print("   %tatty_config max_retry_attempts 5")
            print("   %tatty_config show_correction_details False")
            return

        # Handle specific setting changes
        setting = args.setting.lower()
        value = args.value

        if not value:
            # Show current value of specific setting
            if hasattr(self.error_config, setting):
                current_value = getattr(self.error_config, setting)
                print(f"Current value of {setting}: {current_value}")
            else:
                print(f"Unknown setting: {setting}")
            return

        # Set new value
        try:
            if setting == 'enable_code_correction':
                self.error_config.enable_code_correction = value.lower() in ('true', 'yes', '1')
                print(f"✅ Set enable_code_correction = {self.error_config.enable_code_correction}")
            elif setting == 'enable_dependency_auto_install':
                self.error_config.enable_dependency_auto_install = value.lower() in ('true', 'yes', '1')
                print(f"✅ Set enable_dependency_auto_install = {self.error_config.enable_dependency_auto_install}")
            elif setting == 'show_correction_details':
                self.error_config.show_correction_details = value.lower() in ('true', 'yes', '1')
                print(f"✅ Set show_correction_details = {self.error_config.show_correction_details}")
            elif setting == 'max_retry_attempts':
                self.error_config.max_retry_attempts = int(value)
                print(f"✅ Set max_retry_attempts = {self.error_config.max_retry_attempts}")
            elif setting == 'correction_timeout':
                self.error_config.correction_timeout = float(value)
                print(f"✅ Set correction_timeout = {self.error_config.correction_timeout}s")
            else:
                print(f"Unknown setting: {setting}")
                print("Available settings: enable_code_correction, max_retry_attempts, enable_dependency_auto_install, correction_timeout, show_correction_details")
        except ValueError as e:
            print(f"❌ Invalid value for {setting}: {e}")

    @magic_arguments()
    @argument(
        '--task-id', '-t',
        type=str,
        default=None,
        help='Get observability data for specific task (execution_id)'
    )
    @argument(
        '--summary', '-s',
        action='store_true',
        help='Show summary statistics for all tasks'
    )
    @argument(
        '--context-window', '-c',
        action='store_true',
        help='Show context window usage analysis'
    )
    @argument(
        '--export', '-e',
        type=str,
        default=None,
        help='Export observability data to JSON file'
    )
    @line_magic
    def tatty_observability(self, line: str):
        """Access TATty Agent observability data

        Examples:
            %tatty_observability                    # Show all observability data
            %tatty_observability --summary          # Show session summary
            %tatty_observability --context-window   # Show context window analysis
            %tatty_observability --task-id abc123   # Show specific task data
            %tatty_observability --export session.json  # Export to file
        """
        args = parse_argstring(self.tatty_observability, line)

        if not self._observability_session:
            print("📊 No observability data available yet. Run some TATty commands first!")
            return

        if args.export:
            self._export_observability(args.export)
            return

        if args.summary:
            self._show_observability_summary()
            return

        if args.context_window:
            self._show_context_window_analysis()
            return

        if args.task_id:
            self._show_task_observability(args.task_id)
            return

        # Default: show latest task data
        latest_obs = self._observability_session[-1]
        from .display import display_agent_response

        # Show context for the latest task
        steps_count = len(latest_obs.get('steps', []))
        total_tokens_in = latest_obs.get('total_tokens', {}).get('input', 0)
        total_tokens_out = latest_obs.get('total_tokens', {}).get('output', 0)
        total_tokens = total_tokens_in + total_tokens_out
        duration = latest_obs.get('total_duration', 0)

        print("📊 Latest Task Observability Data:")
        print("=" * 50)
        print(f"🎯 Task: {latest_obs.get('query', 'Unknown query')}")
        print(f"📋 Execution: 1 task with {steps_count} steps")
        print(f"⏱️  Duration: {duration:.1f}s")
        print(f"🎯 Tokens: {total_tokens:,.0f} total ({total_tokens_in:,.0f} in, {total_tokens_out:,.0f} out)")
        print(f"🆔 Task ID: {latest_obs.get('execution_id')}")
        print()

        # Import the module so we can access the observability display directly
        from ..jupyter.display import TattyDisplayFormatter
        formatter = TattyDisplayFormatter()
        formatter._display_observability_toggle(latest_obs)

        return latest_obs  # Return for programmatic access

    def _export_observability(self, filename: str):
        """Export observability data to JSON file"""
        import json
        from pathlib import Path

        try:
            export_data = {
                "session_summary": self._calculate_session_summary(),
                "tasks": self._observability_session,
                "exported_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            Path(filename).write_text(json.dumps(export_data, indent=2, default=str))
            print(f"📁 Exported {len(self._observability_session)} tasks to {filename}")

        except Exception as e:
            print(f"❌ Export failed: {e}")

    def _show_observability_summary(self):
        """Show session observability summary"""
        summary = self._calculate_session_summary()

        print("📊 TATty Agent Session Summary:")
        print("=" * 50)
        print(f"📈 Total Tasks: {summary['total_tasks']}")
        print(f"⏱️  Total Duration: {summary['total_duration']:.1f}s")
        print(f"🎯 Total Tokens: {summary['total_tokens']:,} ({summary['total_input_tokens']:,} in, {summary['total_output_tokens']:,} out)")
        print(f"🔧 Total Steps: {summary['total_steps']}")
        print(f"📊 Avg Duration: {summary['avg_duration']:.1f}s per task")
        print(f"🎯 Avg Tokens: {summary['avg_tokens']:.0f} per task")

        print(f"\n🎯 Intent Distribution:")
        for intent, count in summary['intent_distribution'].items():
            print(f"  {intent}: {count} tasks")

        print(f"\n🔧 Model Usage:")
        for model, stats in summary['model_usage'].items():
            print(f"  {model}: {stats['calls']} calls, {stats['tokens']:,} tokens")

    def _calculate_session_summary(self):
        """Calculate session summary statistics"""
        if not self._observability_session:
            return {}

        total_tasks = len(self._observability_session)
        total_duration = sum(task.get('total_duration', 0) for task in self._observability_session)
        total_input_tokens = sum(task.get('total_tokens', {}).get('input', 0) for task in self._observability_session)
        total_output_tokens = sum(task.get('total_tokens', {}).get('output', 0) for task in self._observability_session)
        total_tokens = total_input_tokens + total_output_tokens
        total_steps = sum(len(task.get('steps', [])) for task in self._observability_session)

        # Intent distribution
        intent_distribution = {}
        model_usage = {}

        for task in self._observability_session:
            for step in task.get('steps', []):
                if step.get('step') == 'intent_classification':
                    intent = step.get('output', {}).get('intent', 'Unknown')
                    intent_distribution[intent] = intent_distribution.get(intent, 0) + 1

                model = step.get('model', 'Unknown')
                if model not in model_usage:
                    model_usage[model] = {'calls': 0, 'tokens': 0}
                model_usage[model]['calls'] += 1
                model_usage[model]['tokens'] += step.get('tokens', {}).get('input', 0) + step.get('tokens', {}).get('output', 0)

        return {
            'total_tasks': total_tasks,
            'total_duration': total_duration,
            'total_input_tokens': total_input_tokens,
            'total_output_tokens': total_output_tokens,
            'total_tokens': total_tokens,
            'total_steps': total_steps,
            'avg_duration': total_duration / total_tasks if total_tasks > 0 else 0,
            'avg_tokens': total_tokens / total_tasks if total_tasks > 0 else 0,
            'intent_distribution': intent_distribution,
            'model_usage': model_usage
        }

    def _show_context_window_analysis(self):
        """Show context window usage analysis"""
        summary = self._calculate_session_summary()

        # Estimate context window usage (rough estimates)
        CONTEXT_WINDOW_SIZE = 128000  # GPT-4 context window
        TOKENS_PER_MESSAGE = 50  # Rough estimate for conversation overhead

        current_context_usage = 0
        for task in self._observability_session[-5:]:  # Last 5 tasks in context
            current_context_usage += task.get('total_tokens', {}).get('input', 0)
            current_context_usage += task.get('total_tokens', {}).get('output', 0)
            current_context_usage += TOKENS_PER_MESSAGE  # Message overhead

        history_context = len(self._execution_history) * TOKENS_PER_MESSAGE
        total_estimated_context = current_context_usage + history_context

        context_percentage = (total_estimated_context / CONTEXT_WINDOW_SIZE) * 100
        remaining_context = CONTEXT_WINDOW_SIZE - total_estimated_context

        print("🧠 Context Window Analysis:")
        print("=" * 50)
        print(f"📏 Context Window Size: {CONTEXT_WINDOW_SIZE:,} tokens")
        print(f"📊 Current Usage: ~{total_estimated_context:,} tokens ({context_percentage:.1f}%)")
        print(f"📈 Available: ~{remaining_context:,} tokens ({100-context_percentage:.1f}%)")
        print(f"🔄 Recent Tasks: {current_context_usage:,} tokens")
        print(f"📚 History Overhead: {history_context:,} tokens")

        if context_percentage > 80:
            print("⚠️  WARNING: Context window usage is high. Consider using --fresh for new tasks.")
        elif context_percentage > 60:
            print("💡 TIP: Context window usage is moderate. Monitor for efficiency.")
        else:
            print("✅ Context window usage is healthy.")

    def _show_task_observability(self, task_id: str):
        """Show observability data for a specific task"""
        task = None
        for obs_data in self._observability_session:
            if obs_data.get('execution_id') == task_id:
                task = obs_data
                break

        if not task:
            print(f"❌ Task with ID '{task_id}' not found")
            print("Available task IDs:")
            for obs_data in self._observability_session:
                print(f"  - {obs_data.get('execution_id')}")
            return

        print(f"📊 Task Observability: {task_id}")
        print("=" * 50)

        from ..jupyter.display import TattyDisplayFormatter
        formatter = TattyDisplayFormatter()
        formatter._display_observability_toggle(task)

        return task


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
        ipython.register_magic_function(magics.tatty_observability, 'line')

        print("🎉 TATty Agent magic commands loaded!")
        print("Available commands:")
        print("  %tatty \"query\"         - Run a single query")
        print("  %%tatty                 - Run multi-line query")
        print("  %tatty_history          - Show conversation history")
        print("  %tatty_clear            - Clear conversation history")
        print("  %tatty_vars             - Show notebook variables")
        print("  %tatty_observability    - Access observability data")
        print()
        print("Options: --verbose, --dir, --max-iterations, --history, --clear-history, --fresh, --history-limit")
        print("Observability: --summary, --context-window, --task-id, --export")

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