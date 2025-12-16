"""
Agent state management and callback definitions
"""
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass, field

from ..baml_client import types


@dataclass
class AgentState:
    """Shared state for agent execution"""
    messages: list[types.Message] = field(default_factory=list)
    todos: list[types.TodoItem] = field(default_factory=list)
    interrupt_requested: bool = False
    current_iteration: int = 0
    current_depth: int = 0
    working_dir: str = "."


@dataclass
class AgentCallbacks:
    """Callbacks for UI updates during agent execution"""
    on_iteration: Optional[Callable[[int, int], Awaitable[None]]] = None  # (iteration, depth)
    on_tool_start: Optional[Callable[[str, dict, int, int, int], Awaitable[None]]] = None  # (tool_name, params, tool_idx, total_tools, depth)
    on_tool_result: Optional[Callable[[str, int], Awaitable[None]]] = None  # (result, depth)
    on_agent_reply: Optional[Callable[[str], Awaitable[None]]] = None
    on_status_update: Optional[Callable[[str, int], Awaitable[None]]] = None  # (status, iteration)
    on_sub_agent_start: Optional[Callable[[str, str, int], Awaitable[None]]] = None  # (description, prompt, depth)
    on_sub_agent_complete: Optional[Callable[[str, int], Awaitable[None]]] = None  # (result, depth)