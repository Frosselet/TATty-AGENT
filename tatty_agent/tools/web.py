"""
Web tools for TATty Agent

This module contains web-related tools extracted from main.py:
- WebFetch: Fetch and process web content from URLs
- WebSearch: Search the web using DuckDuckGo
"""
from ..baml_client import types
from .registry import register_tool


@register_tool("WebFetch")
def execute_web_fetch(tool: types.WebFetchTool, working_dir: str = ".") -> str:
    """Fetch and process web content"""
    try:
        import requests  # type: ignore
        from bs4 import BeautifulSoup  # type: ignore

        response = requests.get(tool.url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        text = soup.get_text()

        # Simple markdown conversion (just cleaning up whitespace)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        markdown_content = '\n'.join(lines)

        # TODO: call haiku to summarize the content given the query and how its related.

        # Truncate if too long
        truncation_message = ""
        if len(markdown_content) > 10000:
            markdown_content = markdown_content[:10000] + "\n... [truncated]"
            truncation_message = "if you need more information, call the WebFetch tool again to get the rest of the content with a file path"

        return f"Content from {tool.url}:\n\n{markdown_content}\n\nUser prompt: {tool.prompt}\n\n{truncation_message}".strip()
    except ImportError:
        return "Error: requests and beautifulsoup4 packages are required for web fetching. Install with: pip install requests beautifulsoup4"
    except Exception as e:
        return f"Error fetching web content: {str(e)}"


@register_tool("WebSearch")
def execute_web_search(tool: types.WebSearchTool, working_dir: str = ".") -> str:
    """Search the web using DuckDuckGo search"""
    try:
        from ddgs import DDGS

        # Initialize DuckDuckGo client
        ddgs = DDGS()

        # Perform search with content
        try:
            # Get search results (limit to 5 for token efficiency)
            search_results = list(ddgs.text(
                tool.query,
                max_results=5,
                safesearch='moderate'
            ))
        except Exception as search_error:
            return f"Error performing search: {str(search_error)}"

        if not search_results:
            return f"No results found for query: '{tool.query}'"

        # Format results
        results = []
        for i, result in enumerate(search_results, 1):
            title = result.get('title', 'No title')
            url = result.get('href', 'No URL')
            body = result.get('body', 'No content available')

            # Truncate text if too long
            if len(body) > 500:
                body = body[:500] + "..."

            results.append(f"{i}. **{title}**\n   URL: {url}\n   Content: {body}\n")

        return f"Web search results for '{tool.query}':\n\n" + "\n".join(results)

    except ImportError:
        return "Error: ddgs package not installed. Run 'uv add ddgs' to install it."
    except Exception as e:
        return f"Error performing web search: {str(e)}"