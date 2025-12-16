# 🚀 TATty Agent - AI Assistant for Development

> A portable Python package for intelligent code analysis and development tasks.

## 🎯 Quick Start

### Installation

```bash
# Clone and install the development version
git clone https://github.com/ai-that-works/ai-that-works.git
cd ai-that-works/2025-10-21-agentic-rag-context-engineering

# Set up environment
uv sync
uv run baml-cli generate

# Set API key
export OPENAI_API_KEY="your-key-here"
```

### Basic Usage

```bash
# CLI mode - single query
uv run python main.py "What files are in this project?"

# TUI mode - interactive interface (recommended)
uv run python main.py "Start" --tui

# Interactive mode - command line chat
uv run python main.py "Start" --interactive
```

## 🎪 Jupyter Integration (Primary Interface)

The **magic commands** provide the most reliable way to use TATty Agent in notebooks:

```python
# Load magic commands
%load_ext tatty_agent.jupyter.magic

# Single-line queries
%tatty "Analyze my code structure"

# Multi-line queries
%%tatty
Find all TODO comments in my project
and create a summary report
```

### Magic Commands Reference

| Command | Description |
|---------|-------------|
| `%tatty "query"` | Execute a single query |
| `%%tatty` | Execute multi-line query |
| `%tatty_history` | View conversation history |
| `%tatty_vars` | Show notebook variables |
| `%tatty_clear` | Clear conversation history |

### Installation for Jupyter

```bash
# Install in development mode
pip install -e .

# Or install from source
pip install git+https://github.com/ai-that-works/ai-that-works.git
```

## 🛠️ What TATty Agent Can Do

### Code Analysis & Development
- **File Operations**: Read, write, edit files with intelligent context
- **Code Understanding**: Analyze project structure and dependencies
- **Quality Assurance**: Run tests, linting, type checking, formatting
- **Git Integration**: View diffs, check status, analyze changes

### Smart Features
- **Notebook Integration**: Access variables, execute code in context
- **Persistent Memory**: Maintains conversation across commands
- **Tool Orchestration**: Combines multiple tools to solve complex tasks
- **Sub-Agent Delegation**: Spawns focused agents for specific subtasks

### Example Workflows

```python
# In Jupyter notebook:
%tatty "Run tests and fix any failures"
%tatty "Lint my Python files and show what needs fixing"
%tatty "Analyze my data.csv and create visualizations"
%tatty "Check if I'm missing any dependencies"
```

## 🏗️ Architecture

**Core Components:**
- `tatty_agent/core/` - Agent runtime and state management
- `tatty_agent/tools/` - 24+ specialized tools (file ops, web search, etc.)
- `tatty_agent/jupyter/` - Jupyter integration with magic commands
- `tatty_agent/cli/` - Command-line interface

**Key Technologies:**
- **BAML**: Type-safe AI function calling and schema definition
- **Pydantic**: Data validation and type safety
- **Textual**: Beautiful TUI interface
- **IPython**: Magic command integration

## 📖 Usage Examples

### CLI Examples

```bash
# Analyze a specific project
uv run python main.py "Analyze this codebase" --dir ~/my-project

# Interactive development session
uv run python main.py "Start" --tui

# Quick file search
uv run python main.py "Find all Python files using pandas"
```

### Jupyter Examples

```python
# Basic usage
%load_ext tatty_agent.jupyter.magic
%tatty "What's in this notebook's variables?"

# Complex analysis
%%tatty
Analyze my DataFrame 'sales_data' and create:
1. Summary statistics
2. Data quality report
3. Visualization suggestions

# Development workflow
%tatty "Run my tests and fix any import errors"
%tatty "Check code quality and suggest improvements"
```

## 🔧 Configuration

### Environment Variables

```bash
# Required
export OPENAI_API_KEY="your-key-here"

# Optional
export TATTY_AGENT_MODEL="gpt-4o"  # Default: gpt-4o-mini
export TATTY_AGENT_MAX_ITERATIONS="20"  # Default: 10
```

### BAML Configuration

Agent behavior is defined in `baml_src/agent.baml`:

```baml
function AgentLoop(state: Message[], working_dir: string) -> (ReplyToUser | AgentTools) {
    client GPT_4o_Mini
    prompt #"
        You are TATty Agent, an AI assistant for development tasks.
        // ... full prompt definition
    "#
}
```

## 🧪 Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/ai-that-works/ai-that-works.git
cd ai-that-works/2025-10-21-agentic-rag-context-engineering

# Install dependencies
uv sync

# Generate BAML client
uv run baml-cli generate

# Run tests (when available)
uv run python -m pytest
```

### Project Structure

```
tatty_agent/
├── core/           # Agent runtime and state
├── tools/          # Tool implementations
├── jupyter/        # Jupyter magic commands
├── cli/            # Command line interface
├── examples/       # Usage examples
└── config/         # Configuration files

baml_src/           # BAML definitions
├── agent.baml      # Agent loop functions
├── agent-tools.baml # Tool type definitions
└── clients.baml    # LLM client config
```

## 📚 Documentation

- **Magic Commands**: Primary interface for Jupyter notebooks
- **TUI Mode**: Beautiful terminal interface (`--tui` flag)
- **Tool System**: 24+ specialized tools for development tasks
- **Architecture**: BAML-based type-safe AI function calling

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure magic commands still work: `%load_ext tatty_agent.jupyter.magic`
5. Submit a pull request

## 📄 License

This project is part of the "AI That Works" series.

---

## 🎬 Original Tutorial

This package was built during a live coding session exploring Agentic RAG systems:

[![Agentic RAG + Context Engineering](https://img.youtube.com/vi/grGSFfyejA0/0.jpg)](https://www.youtube.com/watch?v=grGSFfyejA0)

**Key Insights from the Tutorial:**
- Agentic RAG lets models decide what context to retrieve (vs. deterministic vector search)
- Tool implementation details matter more than complex retry logic
- Context engineering saves significant tokens across iterations
- Magic commands provide the most reliable interface for notebook integration