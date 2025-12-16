# TATty Agent - Portable AI Development Companion

<div align="center">

![TATty Agent Logo](https://via.placeholder.com/300x100/2E8B57/FFFFFF?text=TATty+Agent)

**A comprehensive, portable AI agent for developers that lives in your codebase**

[![PyPI version](https://badge.fury.io/py/TATty-agent.svg)](https://badge.fury.io/py/TATty-agent)
[![Python Support](https://img.shields.io/pypi/pyversions/TATty-agent.svg)](https://pypi.org/project/TATty-agent/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

## 🚀 Quick Start

```bash
# Install TATty Agent with all features
pip install TATty-agent[full]

# Initialize your project
cd your_project
tatty-init

# Start using immediately
tatty-agent "Analyze my Python code and suggest improvements"

# Or use interactively
tatty-tui

# Or in Jupyter notebooks
%load_ext tatty_agent.jupyter.magic
%tatty "Help me debug this function"
```

## ✨ Features

### 🎯 **Multi-Modal Interfaces**
- **CLI Mode**: Quick commands and script integration
- **TUI Mode**: Rich interactive terminal interface
- **Jupyter Mode**: Notebook integration with chat widgets and magic commands
- **Library API**: Direct Python integration for custom applications

### 🛠️ **Comprehensive Tool Suite** (24+ Tools)
- **File Operations**: Read, write, edit, multi-file editing
- **System Integration**: Shell commands, file search, directory navigation
- **Web Capabilities**: Fetch, search, and analyze web content
- **Development Tools**: Git operations, testing, linting, formatting
- **Artifact Management**: Scripts, data, visualizations, documents

### 📁 **External Artifact Management**
- **scripts/**: Automation and utility scripts
- **data/**: Datasets, CSVs, and data processing
- **visualization/**: Charts, graphs, and visual outputs
- **documents/**: Reports (PDF, MD), spreadsheets, presentations

### 📓 **Jupyter Integration**
- **Interactive Chat Widget**: ChatGPT-like interface in notebooks
- **Magic Commands**: `%tatty` and `%%tatty` for quick queries
- **Live Tool Execution**: Real-time progress tracking with collapsible output
- **Notebook Variable Access**: Work directly with your DataFrame and variables
- **Rich Display**: Formatted output with syntax highlighting

## 📦 Installation Options

### Standard Installation
```bash
pip install TATty-agent
```

### Full Installation (Recommended)
```bash
pip install TATty-agent[full]
```

### Custom Installation
```bash
# Just CLI and library
pip install TATty-agent

# Add TUI support
pip install TATty-agent[tui]

# Add Jupyter support
pip install TATty-agent[jupyter]

# Add visualization tools
pip install TATty-agent[visualization]

# Add document generation
pip install TATty-agent[documents]

# Add web search capabilities
pip install TATty-agent[web]
```

## 🏗️ Project Setup

### Initialize New Project
```bash
# Create artifact folders and configuration
tatty-init

# This creates:
# ├── scripts/           # Automation scripts
# ├── data/             # Datasets and data files
# ├── visualization/    # Charts and graphs
# ├── documents/        # Reports and documentation
# ├── .env             # API keys configuration
# └── baml_src/        # BAML tool definitions (customizable)
```

### Initialize Existing Project
```bash
cd existing_project
tatty-init --existing

# Safely adds TATty Agent folders without disrupting existing structure
```

## 💻 Usage Examples

### CLI Usage
```bash
# Quick analysis
tatty-agent "Find all TODO comments in this codebase"

# File operations
tatty-agent "Refactor the authentication module to use modern patterns"

# Git operations
tatty-agent "Create a feature branch and implement user settings"

# Web research
tatty-agent "Search for the latest React best practices and summarize them"
```

### Library API
```python
from tatty_agent import TattyAgent

# Create agent instance
agent = TattyAgent(working_dir=".", verbose=True)

# Ask questions
result = agent.run("Analyze the main.py file and suggest optimizations")

# Execute specific tools
response = agent.execute_tool("Grep", pattern="TODO", path="src/")

# Access conversation history
history = agent.get_conversation_history()

# Manage working directory
agent.set_working_dir("/path/to/project")
```

### TUI Mode
```bash
# Launch interactive terminal interface
tatty-tui

# Features:
# - Rich conversation history
# - Live tool execution with progress
# - File tree navigation
# - Syntax-highlighted code display
# - Multi-pane layout with collapsible sections
```

### Jupyter Integration

#### Magic Commands
```python
# Load magic commands
%load_ext tatty_agent.jupyter.magic

# Line magic for quick queries
%tatty "What are the main functions in utils.py?"

# Cell magic for multi-line requests
%%tatty
Analyze the DataFrame df and:
1. Show basic statistics
2. Identify potential data quality issues
3. Suggest cleaning steps
```

#### Interactive Chat Widget
```python
from tatty_agent.jupyter import create_quick_chat

# Create and display chat interface
chat = create_quick_chat()
# Interactive ChatGPT-like interface appears above
```

#### Working with Notebook Variables
```python
# TATty can access your notebook variables
import pandas as pd
df = pd.read_csv("data.csv")

# Agent can analyze your data
%tatty "Analyze the df DataFrame and create a summary report"

# Agent can generate new cells with code
%tatty "Create a visualization of the sales trends in df and add it as a new cell"
```

#### Live Tool Execution
```python
from tatty_agent.jupyter import track_tool_execution

# Real-time progress tracking
with track_tool_execution("AnalyzeCode", {"path": "src/"}) as tracker:
    # Shows live progress with collapsible sections
    tracker.update_progress(50, "Analyzing modules...")
```

## 🔧 Configuration

### Environment Variables
```bash
# API Keys (required)
OPENAI_API_KEY=your_openai_key
BOUNDARY_API_KEY=your_boundary_key

# Optional configurations
TATTY_VERBOSE=true
TATTY_MAX_ITERATIONS=25
TATTY_WORKING_DIR=/custom/path
TATTY_DEFAULT_MODEL=gpt-4
TATTY_FAST_MODEL=gpt-3.5-turbo
```

### Programmatic Configuration
```python
from tatty_agent import TattyAgent, TattyConfig

config = TattyConfig(
    openai_api_key="your_key",
    verbose=True,
    max_iterations=30,
    default_model="gpt-4-turbo"
)

agent = TattyAgent(config=config)
```

### Custom BAML Tools
```bash
# Customize tool definitions
cd your_project
edit baml_src/agent-tools.baml

# Regenerate tools
tatty-agent --rebuild-tools
```

## 📊 Artifact Types

### Scripts (`scripts/`)
- **Automation scripts**: Build, deployment, data processing
- **Utility functions**: Helper scripts and one-off tools
- **Analysis scripts**: Custom analytics and reporting

### Data (`data/`)
- **Raw datasets**: CSV, JSON, XML files
- **Processed data**: Cleaned and transformed datasets
- **Database exports**: SQL dumps and query results

### Visualization (`visualization/`)
- **Charts and graphs**: PNG, SVG, PDF plots
- **Interactive dashboards**: HTML dashboards
- **Infographics**: Custom visual reports

### Documents (`documents/`)
- **Reports**: Analysis reports in Markdown, PDF
- **Spreadsheets**: Excel files with formulas and charts
- **Presentations**: PowerPoint slides for stakeholders
- **Documentation**: Technical specs, API docs

## 🧪 Development and Testing

### Running Tests
```bash
# Install development dependencies
pip install TATty-agent[full]

# Run unit tests
pytest tests/

# Run integration tests
pytest tests/test_integration.py -v

# Run Jupyter integration tests
pytest tests/test_jupyter_integration.py -v

# Test specific functionality
pytest tests/test_library_api.py::TestTattyAgent -v
```

### Package Structure
```
tatty_agent/
├── __init__.py              # Main API and convenience functions
├── cli/                     # Command-line interface
│   ├── main.py             # Primary CLI entry point
│   └── commands.py         # tatty-init, tatty-tui commands
├── core/                    # Core runtime and state management
│   ├── runtime.py          # Agent execution engine
│   ├── state.py            # Shared state and callbacks
│   └── types.py            # Type definitions and BAML integration
├── tools/                   # Modular tool implementations
│   ├── registry.py         # Tool registration and dispatch
│   ├── file_ops.py         # File read/write/edit operations
│   ├── system.py           # Shell and filesystem tools
│   ├── web.py              # Web fetch and search
│   ├── development.py      # Git, testing, linting tools
│   └── artifacts.py        # Artifact and document management
├── tui/                     # Terminal user interface
│   ├── app.py              # Main TUI application
│   └── components/         # Reusable UI widgets
├── jupyter/                 # Jupyter notebook integration
│   ├── display.py          # Rich HTML/Markdown formatting
│   ├── magic.py            # IPython magic commands
│   ├── notebook.py         # Variable access and cell management
│   ├── progress.py         # Live execution tracking
│   └── widgets.py          # Interactive chat interface
├── config/                  # Configuration and initialization
│   ├── settings.py         # Config management
│   └── initialization.py   # Project setup and folders
└── assets/                  # Template files and resources
    └── baml_src/           # BAML tool definition templates
```

## 🔧 Advanced Usage

### Custom Tool Development
```python
from tatty_agent.tools.registry import register_tool

@register_tool("CustomTool")
def execute_custom_tool(tool_data, working_dir="."):
    # Your custom tool implementation
    return "Tool result"
```

### Sub-Agent Creation
```python
# Create specialized sub-agents
code_reviewer = TattyAgent(
    config=TattyConfig(
        default_model="gpt-4",
        working_dir="./src",
        verbose=True
    )
)

# Chain agent operations
analysis = agent.run("Analyze codebase structure")
review = code_reviewer.run(f"Review this analysis: {analysis}")
```

### Batch Processing
```bash
# Process multiple files
find . -name "*.py" -exec tatty-agent "Analyze and document {}" \;

# Generate reports for all projects
for dir in projects/*/; do
    cd "$dir"
    tatty-agent "Create project status report in documents/"
    cd ..
done
```

## 🌟 Migration from Previous Versions

### From Single-File Agent
```python
# Old usage (main.py based)
python main.py --query "Analyze code"

# New usage (package based)
tatty-agent "Analyze code"

# Or in Python
from tatty_agent import run_agent
result = run_agent("Analyze code")
```

### Preserving Existing Configurations
```bash
# Your existing .env and BAML configurations are preserved
tatty-init --preserve-existing

# Manual migration
cp old_project/.env new_project/
cp old_project/baml_src/* new_project/baml_src/
```

## 📚 Documentation

- **API Documentation**: Comprehensive docstrings and type hints
- **Example Notebooks**: `examples/tatty_agent_jupyter_demo.ipynb`
- **Tool Reference**: Complete tool documentation in BAML files
- **Configuration Guide**: Environment and programmatic config options

## 🤝 Contributing

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature-name`
3. **Make changes** with proper tests
4. **Run test suite**: `pytest tests/ -v`
5. **Submit pull request**

### Development Setup
```bash
git clone https://github.com/your-org/tatty-agent
cd tatty-agent
pip install -e .[full]
pytest tests/
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **BAML Integration**: Powered by [Boundary ML](https://boundary.ml) for type-safe AI tools
- **UI Framework**: Built with [Textual](https://textual.textualize.io) for rich terminal interfaces
- **Jupyter Integration**: Enhanced with [ipywidgets](https://ipywidgets.readthedocs.io) for interactive widgets

## 📞 Support

- **Issues**: Report bugs and feature requests on GitHub Issues
- **Documentation**: Visit our documentation site
- **Community**: Join our developer community

---

<div align="center">

**TATty Agent** - Making AI development accessible, powerful, and portable

Made with ❤️ by the AI That Works team

</div>