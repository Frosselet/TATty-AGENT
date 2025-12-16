"""
TATty Agent Documentation

This module provides access to documentation and guides for TATty Agent.
After installation, you can access documentation programmatically:

```python
from tatty_agent.docs import show_readme, show_distribution_guide, get_docs_dir

# Show main documentation
show_readme()

# Show distribution guide
show_distribution_guide()

# Get documentation directory
docs_path = get_docs_dir()
```
"""

from pathlib import Path
from typing import Optional

def get_docs_dir() -> Path:
    """Get the documentation directory path"""
    return Path(__file__).parent

def get_doc_path(name: str) -> Optional[Path]:
    """
    Get path to a specific documentation file.

    Args:
        name: Name of the documentation file

    Returns:
        Path to the documentation file, or None if not found
    """
    docs_dir = get_docs_dir()
    doc_path = docs_dir / name

    if doc_path.exists():
        return doc_path
    return None

def read_doc(name: str) -> Optional[str]:
    """
    Read content of a documentation file.

    Args:
        name: Name of the documentation file

    Returns:
        Content of the file, or None if not found
    """
    doc_path = get_doc_path(name)
    if doc_path:
        return doc_path.read_text()
    return None

def show_readme():
    """Display the main README documentation"""
    readme_content = read_doc("README.md")
    if readme_content:
        print("📚 TATty Agent - README")
        print("=" * 50)
        print(readme_content[:1000] + "..." if len(readme_content) > 1000 else readme_content)
        print()
        print("💡 For full documentation, see:")
        print(f"   {get_doc_path('README.md')}")
    else:
        print("❌ README.md not found")

def show_distribution_guide():
    """Display the distribution guide"""
    dist_content = read_doc("DISTRIBUTION.md")
    if dist_content:
        print("📦 Distribution Guide")
        print("=" * 50)
        print(dist_content[:1000] + "..." if len(dist_content) > 1000 else dist_content)
        print()
        print("💡 For full guide, see:")
        print(f"   {get_doc_path('DISTRIBUTION.md')}")
    else:
        print("❌ DISTRIBUTION.md not found")

def list_docs() -> list:
    """List all available documentation files"""
    docs_dir = get_docs_dir()
    return [f.name for f in docs_dir.glob("*") if f.is_file() and f.name != "__init__.py"]

__all__ = [
    'get_docs_dir',
    'get_doc_path',
    'read_doc',
    'show_readme',
    'show_distribution_guide',
    'list_docs'
]