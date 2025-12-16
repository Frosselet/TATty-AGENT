"""
Jupyter Integration for TATty Agent

This module provides comprehensive Jupyter notebook support with a focus on
reliable magic commands and rich display formatting.

## Features

### Magic Commands (Primary Interface)
```python
# Load the magic commands
%load_ext tatty_agent.jupyter.magic

# Single-line queries
%tatty "List all Python files"

# Multi-line queries
%%tatty
Find all TODO comments
and create a summary
```

### Notebook Context Access
```python
from tatty_agent.jupyter import get_notebook_variables, execute_in_notebook

# Access notebook variables
variables = get_notebook_variables()

# Execute code in notebook context
result = execute_in_notebook("df.head()")
```

### Rich Display Formatting
```python
from tatty_agent.jupyter import display_agent_response

display_agent_response(
    query="Your query",
    result="Agent response",
    execution_time=1.5,
    tools_used=[...]
)
```

### Live Progress Tracking
```python
from tatty_agent.jupyter import track_tool_execution

with track_tool_execution("MyTool", {"param": "value"}):
    # Tool execution code here
    pass
```

## Components

- **magic**: IPython magic commands (%tatty, %%tatty) - Primary interface
- **display**: Rich HTML/Markdown formatting and visualization
- **notebook**: Notebook variable access and cell management
- **progress**: Real-time progress indicators and execution tracking
"""

# Import all public components
from .display import (
    TattyDisplayFormatter,
    display_agent_response,
    display_tool_execution,
    display_progress_indicator,
    display_conversation_history,
    display_artifact_links
)

from .notebook import (
    NotebookContextManager,
    get_notebook_context,
    get_notebook_variables,
    execute_in_notebook,
    create_cell_with_code
)

from .progress import (
    ToolExecutionProgressTracker,
    LiveExecutionDisplay,
    get_live_display,
    track_tool_execution,
    display_execution_summary,
    create_interactive_execution_widget
)

# Magic commands are imported separately when needed
from . import magic

__all__ = [
    # Display components
    'TattyDisplayFormatter',
    'display_agent_response',
    'display_tool_execution',
    'display_progress_indicator',
    'display_conversation_history',
    'display_artifact_links',

    # Notebook integration
    'NotebookContextManager',
    'get_notebook_context',
    'get_notebook_variables',
    'execute_in_notebook',
    'create_cell_with_code',

    # Progress tracking
    'ToolExecutionProgressTracker',
    'LiveExecutionDisplay',
    'get_live_display',
    'track_tool_execution',
    'display_execution_summary',
    'create_interactive_execution_widget',

    # Magic commands module (for %load_ext)
    'magic'
]

# Auto-detection and helpful messages
try:
    from IPython import get_ipython
    from IPython.display import display, HTML

    ipython = get_ipython()
    if ipython is not None:
        # We're in an IPython/Jupyter environment

        # Check if magic commands are already loaded
        if 'tatty' not in ipython.magics_manager.magics['line_cell']:
            print("💡 TIP: Load TATty magic commands with: %load_ext tatty_agent.jupyter.magic")

        # Provide quick start info
        print("🎉 TATty Agent Jupyter Integration Available!")
        print("🎯 Magic Commands (Primary Interface):")
        print("  %load_ext tatty_agent.jupyter.magic")
        print("  %tatty \"your query here\"")
        print("  %%tatty")
        print("  multi-line query here")
        print()
        print("💡 TIP: Magic commands provide the most reliable TATty Agent experience!")

except ImportError:
    # Not in Jupyter environment
    print("ℹ️  TATty Agent Jupyter integration loaded (use in Jupyter notebooks)")

except Exception:
    # Silent fallback
    pass