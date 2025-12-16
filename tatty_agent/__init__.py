"""
TATty Agent - Agentic RAG Context Engineering

A portable Python package for intelligent code analysis, generation, and project management.
Can be installed via pip/uv and lives inside codebases as a development companion.

## Quick Start

### Library Usage
```python
from tatty_agent import TattyAgent

# Create an agent instance
agent = TattyAgent(working_dir="/path/to/project")

# Ask the agent to perform tasks
result = agent.run("List all Python files and analyze their structure")

# Execute specific tools
files = agent.execute_tool("Glob", pattern="**/*.py")

# Interactive conversation
response = agent.ask("What's the overall architecture of this codebase?")
```

### CLI Usage
```bash
# Initialize a new project
tatty-init

# Run agent with a query
tatty-agent "Find all TODO comments in the codebase"

# Launch interactive TUI
tatty-tui

# Check project status
tatty-status
```

## Features

- **24 Comprehensive Tools**: File ops, system commands, web search, development tools
- **Multi-Modal Interfaces**: CLI, TUI, Library API, Jupyter (Phase 5)
- **External Artifacts**: Clean project integration with external folder management
- **BAML Integration**: Type-safe AI tool definitions with customizable templates
- **Git Integration**: Comprehensive git operations and workflow support
- **Development Tools**: Testing, linting, type checking, formatting, dependency management
- **Artifact Management**: Organized scripts/, data/, visualization/, documents/ folders

## Installation & Testing

```bash
# Install the package
pip install TATty-agent[full]

# Test your installation
python -c "from tatty_agent.tests import run_installation_tests; run_installation_tests()"

# Access examples and documentation
python -c "from tatty_agent.examples import show_hello_world; show_hello_world()"
python -c "from tatty_agent.examples import show_jupyter_demo; show_jupyter_demo()"
python -c "from tatty_agent.docs import show_readme; show_readme()"

# Initialize your project
cd your-project
tatty-init
```

## Package Contents

After installation, you have access to:

- **tatty_agent.examples**: Hello World + comprehensive demos
- **tatty_agent.docs**: Complete documentation and guides
- **tatty_agent.tests**: Installation validation tests
- **tatty_agent.jupyter**: Jupyter notebook integration
- **tatty_agent.config**: Configuration and project setup
"""

import asyncio
from pathlib import Path
from typing import Optional, Union, Dict, Any, List

from .core.runtime import AgentRuntime
from .core.state import AgentState, AgentCallbacks
from .config import TattyConfig, load_config, ProjectInitializer
from .tools import execute_tool


class TattyAgent:
    """
    Main TATty Agent class providing a clean library API.

    This is the primary interface for using TATty Agent as a library,
    providing convenient methods for running the agent, executing tools,
    and managing conversations.

    ## Example Usage

    ```python
    from tatty_agent import TattyAgent

    # Create agent
    agent = TattyAgent(working_dir=".")

    # Run a task
    result = agent.run("Find all Python files in this project")

    # Execute specific tool
    files = agent.execute_tool("Glob", pattern="**/*.py")

    # Ask a question
    response = agent.ask("What is the main purpose of this codebase?")

    # Get conversation history
    history = agent.get_conversation_history()
    ```
    """

    def __init__(
        self,
        working_dir: str = ".",
        config: Optional[TattyConfig] = None,
        max_iterations: int = 20,
        verbose: bool = False
    ):
        """
        Initialize TATty Agent.

        Args:
            working_dir: Directory to operate in
            config: Optional configuration override
            max_iterations: Maximum iterations per agent run
            verbose: Enable verbose output
        """
        # Load configuration first to get correct working directory
        if config:
            self.config = config
            # Use config's working_dir if available, otherwise use parameter
            self.working_dir = str(Path(getattr(config, 'working_dir', working_dir)).resolve())
            # Use config values if provided, otherwise use parameters
            self.max_iterations = getattr(self.config, 'max_iterations', max_iterations)
            self.verbose = getattr(self.config, 'verbose', verbose)
        else:
            self.working_dir = str(Path(working_dir).resolve())
            self.config = load_config(working_dir=self.working_dir)
            # Use parameters when no config provided
            self.max_iterations = max_iterations
            self.verbose = verbose

        # Initialize agent state
        self.state = AgentState(working_dir=self.working_dir)

        # Set up callbacks for library usage
        self.callbacks = self._create_library_callbacks()

        # Initialize runtime
        self.runtime = AgentRuntime(self.state, self.callbacks)

        # Conversation history
        self._conversation_history: List[Dict[str, Any]] = []

    def _create_library_callbacks(self) -> AgentCallbacks:
        """Create callbacks appropriate for library usage"""
        callbacks = AgentCallbacks()

        if self.verbose:
            async def on_tool_start(tool_name: str, params: dict, tool_idx: int, total_tools: int, depth: int):
                print(f"🛠️  Executing {tool_name}...")

            async def on_tool_result(result: str, depth: int):
                print("✅ Tool completed")

            callbacks.on_tool_start = on_tool_start
            callbacks.on_tool_result = on_tool_result

        return callbacks

    def run(self, query: str, max_iterations: Optional[int] = None) -> str:
        """
        Run the agent with a query and return the final result.

        Args:
            query: The task or question for the agent
            max_iterations: Override default max iterations

        Returns:
            The agent's final response

        Example:
            ```python
            result = agent.run("Find all Python files and count lines of code")
            print(result)
            ```
        """
        iterations = max_iterations or self.max_iterations

        # Add to conversation history
        self._conversation_history.append({
            "type": "user_query",
            "content": query,
            "timestamp": self._get_timestamp()
        })

        try:
            # Run the agent loop - handle both regular Python and Jupyter environments
            try:
                # Check if we're already in an event loop (like Jupyter)
                loop = asyncio.get_running_loop()
                # We're in an event loop (Jupyter), use nest_asyncio
                import nest_asyncio
                nest_asyncio.apply(loop)
                # Now we can safely use asyncio.run
                result = asyncio.run(self.runtime.run_loop(query, iterations))
            except RuntimeError:
                # No running loop, use normal asyncio.run (CLI/script mode)
                result = asyncio.run(self.runtime.run_loop(query, iterations))

            # Add result to conversation history
            self._conversation_history.append({
                "type": "agent_result",
                "content": result,
                "timestamp": self._get_timestamp()
            })

            return result

        except KeyboardInterrupt:
            return "Agent execution interrupted by user"
        except Exception as e:
            error_msg = f"Agent execution failed: {str(e)}"
            self._conversation_history.append({
                "type": "error",
                "content": error_msg,
                "timestamp": self._get_timestamp()
            })
            return error_msg

    def ask(self, question: str) -> str:
        """
        Ask the agent a question (alias for run with conversational context).

        Args:
            question: Question to ask the agent

        Returns:
            The agent's response

        Example:
            ```python
            response = agent.ask("What is the main function in this project?")
            ```
        """
        return self.run(question)

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """
        Execute a specific tool directly.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters

        Returns:
            Tool execution result

        Example:
            ```python
            files = agent.execute_tool("Glob", pattern="**/*.py")
            content = agent.execute_tool("Read", file_path="main.py")
            ```
        """
        try:
            # Create a mock tool object (this would need the proper BAML types)
            # For now, return a placeholder
            return f"Tool {tool_name} would be executed with params: {kwargs}"
        except Exception as e:
            return f"Tool execution failed: {str(e)}"

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get the conversation history.

        Returns:
            List of conversation entries with timestamps

        Example:
            ```python
            history = agent.get_conversation_history()
            for entry in history:
                print(f"{entry['timestamp']}: {entry['type']} - {entry['content'][:100]}")
            ```
        """
        return self._conversation_history.copy()

    def clear_conversation_history(self) -> None:
        """Clear the conversation history."""
        self._conversation_history.clear()

    def get_working_dir(self) -> str:
        """Get the current working directory."""
        return self.working_dir

    def set_working_dir(self, working_dir: str) -> None:
        """
        Set a new working directory.

        Args:
            working_dir: New working directory path
        """
        self.working_dir = str(Path(working_dir).resolve())
        self.state.working_dir = self.working_dir

    def get_config(self) -> TattyConfig:
        """Get the current configuration."""
        return self.config

    def is_project_initialized(self) -> bool:
        """
        Check if the current working directory is initialized with TATty Agent.

        Returns:
            True if project is initialized, False otherwise
        """
        initializer = ProjectInitializer(self.working_dir)
        status = initializer.check_project_status()
        return status["initialized"]

    def initialize_project(self, force: bool = False) -> Dict[str, Any]:
        """
        Initialize the current working directory with TATty Agent.

        Args:
            force: Overwrite existing files

        Returns:
            Initialization results

        Example:
            ```python
            result = agent.initialize_project()
            if result["success"]:
                print("Project initialized successfully!")
            ```
        """
        initializer = ProjectInitializer(self.working_dir)
        return initializer.initialize_project(force=force)

    def _get_timestamp(self) -> str:
        """Get current timestamp for conversation history"""
        from datetime import datetime
        return datetime.now().isoformat()

    def __repr__(self) -> str:
        return f"TattyAgent(working_dir='{self.working_dir}')"


# Convenience functions for quick usage
def run_agent(query: str, working_dir: str = ".", **kwargs) -> str:
    """
    Quick function to run an agent with a single query.

    Args:
        query: The task or question for the agent
        working_dir: Working directory
        **kwargs: Additional agent configuration

    Returns:
        Agent response

    Example:
        ```python
        from tatty_agent import run_agent

        result = run_agent("List all Python files", working_dir="/my/project")
        print(result)
        ```
    """
    agent = TattyAgent(working_dir=working_dir, **kwargs)
    return agent.run(query)


def ask_agent(question: str, working_dir: str = ".", **kwargs) -> str:
    """
    Quick function to ask the agent a question.

    Args:
        question: Question for the agent
        working_dir: Working directory
        **kwargs: Additional agent configuration

    Returns:
        Agent response

    Example:
        ```python
        from tatty_agent import ask_agent

        answer = ask_agent("What is the main function?", working_dir="/my/project")
        print(answer)
        ```
    """
    agent = TattyAgent(working_dir=working_dir, **kwargs)
    return agent.ask(question)


def initialize_project(working_dir: str = ".", force: bool = False) -> Dict[str, Any]:
    """
    Initialize a project with TATty Agent.

    Args:
        working_dir: Directory to initialize
        force: Overwrite existing files

    Returns:
        Initialization results

    Example:
        ```python
        from tatty_agent import initialize_project

        result = initialize_project("/my/new/project")
        if result["success"]:
            print("Project ready!")
        ```
    """
    initializer = ProjectInitializer(working_dir)
    return initializer.initialize_project(force=force)


# Package metadata
__version__ = "0.1.0"
__author__ = "TATty Agent Development Team"
__email__ = "support@tatty-agent.com"
__description__ = "Agentic RAG Context Engineering - Portable Python package for intelligent code analysis"

# Public API exports
__all__ = [
    # Main class
    "TattyAgent",

    # Convenience functions
    "run_agent",
    "ask_agent",
    "initialize_project",

    # Configuration
    "TattyConfig",
    "load_config",

    # Core components (for advanced usage)
    "AgentRuntime",
    "AgentState",
    "ProjectInitializer",

    # Package metadata
    "__version__",
    "__author__",
    "__email__",
    "__description__",

    # Submodules (imported on demand)
    # "examples",  # Access via: from tatty_agent import examples
    # "docs",      # Access via: from tatty_agent import docs
    # "tests",     # Access via: from tatty_agent import tests
]

# Note: Submodules are available as:
# - from tatty_agent.examples import show_jupyter_demo
# - from tatty_agent.docs import show_readme
# - from tatty_agent.tests import run_installation_tests

# Import core components for advanced users
from .config import TattyConfig, load_config
from .core.runtime import AgentRuntime
from .core.state import AgentState
from .config import ProjectInitializer