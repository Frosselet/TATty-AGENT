"""
Tool registry and dispatch system for TATty Agent

This module centralizes tool registration and execution, providing a clean
interface for the agent runtime to execute tools without tight coupling.
"""
from typing import Dict, Callable, Awaitable, Union
import inspect

from ..baml_client import types
from ..core.types import ToolExecutor


class ToolRegistry:
    """Registry for tool handlers with dynamic discovery and execution"""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._async_tools: Dict[str, Callable] = {}

    def register_tool(self, action: str, handler: Callable):
        """Register a tool handler for a specific action"""
        if inspect.iscoroutinefunction(handler):
            self._async_tools[action] = handler
        else:
            self._tools[action] = handler

    def get_available_tools(self) -> list[str]:
        """Get list of all available tool actions"""
        return list(self._tools.keys()) + list(self._async_tools.keys())

    async def execute(self, tool: types.AgentTools, working_dir: str = ".") -> str:
        """Execute a tool based on its action type"""
        # Check for global interrupt state if available
        try:
            from ..core.runtime import AgentRuntime
            if hasattr(AgentRuntime, '_current_state') and AgentRuntime._current_state:
                if AgentRuntime._current_state.interrupt_requested:
                    return "❌ Tool execution interrupted by user"
        except:
            pass  # No interrupt checking available

        action = tool.action

        # Check async tools first
        if action in self._async_tools:
            handler = self._async_tools[action]
            return await handler(tool, working_dir)

        # Check sync tools
        if action in self._tools:
            handler = self._tools[action]
            return handler(tool, working_dir)

        return f"Unknown tool type: {action}"


# Global registry instance
_registry = ToolRegistry()


def register_tool(action: str):
    """Decorator for registering tool handlers"""
    def decorator(handler: Callable):
        _registry.register_tool(action, handler)
        return handler
    return decorator


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance"""
    return _registry


async def execute_tool(tool: types.AgentTools, working_dir: str = ".") -> str:
    """Main entry point for tool execution - used by AgentRuntime"""
    return await _registry.execute(tool, working_dir)


def get_registered_tools():
    """Get all registered tool names"""
    return _registry.get_available_tools()


def discover_and_register_tools():
    """
    Discover and register all tool handlers from their respective modules.
    This will be called during package initialization.
    """
    # Import all tool modules to trigger registration
    # All modules have been created during Phase 2
    try:
        from . import file_ops
        from . import system
        from . import web
        from . import utility
        from . import development
        from . import artifacts
    except ImportError as e:
        # If import fails, show warning but continue with placeholder handlers
        print(f"Warning: Could not import tool module: {e}")
        pass

    # For now, register the placeholder handlers that will be extracted
    # This ensures the registry system works while we're in transition
    _register_placeholder_tools()


def _register_placeholder_tools():
    """
    Register placeholder tool handlers that delegate to the current main.py functions.
    This ensures backward compatibility during the transition period.
    """
    # Import the current tool handlers from main.py
    try:
        # This is a temporary solution during Phase 1
        # In Phase 2, these will be replaced with proper modular handlers
        import sys
        import os

        # Add the project root to path to import main
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        import main

        # Register all the current tool handlers
        _registry.register_tool("Bash", main.execute_bash)
        _registry.register_tool("Glob", main.execute_glob)
        _registry.register_tool("Grep", main.execute_grep)
        _registry.register_tool("LS", main.execute_ls)
        _registry.register_tool("Read", main.execute_read)
        _registry.register_tool("Edit", main.execute_edit)
        _registry.register_tool("MultiEdit", main.execute_multi_edit)
        _registry.register_tool("Write", main.execute_write)
        _registry.register_tool("NotebookRead", main.execute_notebook_read)
        _registry.register_tool("NotebookEdit", main.execute_notebook_edit)
        _registry.register_tool("WebFetch", main.execute_web_fetch)
        _registry.register_tool("TodoRead", main.execute_todo_read)
        _registry.register_tool("TodoWrite", main.execute_todo_write)
        _registry.register_tool("WebSearch", main.execute_web_search)
        _registry.register_tool("ExitPlanMode", main.execute_exit_plan_mode)
        _registry.register_tool("PytestRun", main.execute_pytest_run)
        _registry.register_tool("Lint", main.execute_lint)
        _registry.register_tool("TypeCheck", main.execute_type_check)
        _registry.register_tool("Format", main.execute_format)
        _registry.register_tool("Dependency", main.execute_dependency)
        _registry.register_tool("GitDiff", main.execute_git_diff)
        _registry.register_tool("InstallPackages", main.execute_install_packages)
        _registry.register_tool("ArtifactManagement", main.execute_artifact_management)
        # Note: Agent tool is handled specially in AgentRuntime.execute_tool

    except ImportError as e:
        # main.py has been modularized, no longer needed
        pass  # This is expected in the packaged version


# Initialize the registry when this module is imported
discover_and_register_tools()