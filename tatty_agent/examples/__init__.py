"""
TATty Agent Examples

This module contains example notebooks and usage patterns for TATty Agent.
After installation, you can access examples programmatically:

```python
from tatty_agent.examples import get_example_notebook, list_examples

# List available examples
examples = list_examples()
print(examples)

# Get path to specific example
notebook_path = get_example_notebook("jupyter_demo")
```

## Available Examples

- **jupyter_demo.ipynb**: Comprehensive Jupyter integration demonstration
  - Interactive chat widget usage
  - Magic commands (%tatty, %%tatty)
  - Live tool execution with progress tracking
  - Notebook variable access and manipulation
  - Rich display formatting examples

## Usage in Jupyter

```python
import tatty_agent.examples
tatty_agent.examples.show_jupyter_demo()
```
"""

import os
from pathlib import Path
from typing import List, Optional

def get_examples_dir() -> Path:
    """Get the examples directory path"""
    return Path(__file__).parent

def list_examples() -> List[str]:
    """List all available example files"""
    examples_dir = get_examples_dir()
    examples = []

    for file in examples_dir.glob("*.ipynb"):
        examples.append(file.stem)

    for file in examples_dir.glob("*.py"):
        if file.name != "__init__.py":
            examples.append(file.stem)

    return sorted(examples)

def get_example_notebook(name: str) -> Optional[Path]:
    """
    Get path to a specific example notebook.

    Args:
        name: Name of the example (without extension)

    Returns:
        Path to the example file, or None if not found
    """
    examples_dir = get_examples_dir()

    # Try .ipynb first
    notebook_path = examples_dir / f"{name}.ipynb"
    if notebook_path.exists():
        return notebook_path

    # Try .py
    py_path = examples_dir / f"{name}.py"
    if py_path.exists():
        return py_path

    return None

def show_jupyter_demo():
    """Display information about the Jupyter demo notebook"""
    demo_path = get_example_notebook("tatty_agent_jupyter_demo")

    if demo_path:
        print(f"🎉 TATty Agent Jupyter Demo")
        print(f"📍 Location: {demo_path}")
        print()
        print("To use the demo:")
        print("1. Copy the notebook to your working directory")
        print("2. Open in Jupyter: jupyter lab")
        print("3. Follow the step-by-step examples")
        print()
        print("Quick start:")
        print("  from tatty_agent import TattyAgent")
        print("  agent = TattyAgent()")
        print("  result = agent.run('Analyze this project')")

        return str(demo_path)
    else:
        print("❌ Jupyter demo notebook not found")
        return None

def copy_example(name: str, destination: str = ".") -> Optional[Path]:
    """
    Copy an example to a destination directory.

    Args:
        name: Name of the example to copy
        destination: Destination directory (default: current directory)

    Returns:
        Path to the copied file, or None if source not found
    """
    import shutil

    source = get_example_notebook(name)
    if not source:
        print(f"❌ Example '{name}' not found")
        return None

    dest_dir = Path(destination)
    dest_dir.mkdir(exist_ok=True)

    dest_path = dest_dir / source.name
    shutil.copy2(source, dest_path)

    print(f"✅ Copied {source.name} to {dest_path}")
    return dest_path

__all__ = [
    'get_examples_dir',
    'list_examples',
    'get_example_notebook',
    'show_jupyter_demo',
    'copy_example'
]