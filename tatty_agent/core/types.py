"""
Common types and interfaces for TATty Agent package
"""
from typing import Union, Optional, Protocol

# Import BAML client types for re-export
from ..baml_client import types


class ToolExecutor(Protocol):
    """Protocol for tool execution functions"""
    async def __call__(self, tool: types.AgentTools, working_dir: str = ".") -> str:
        ...


# Type aliases for convenience
AgentTools = types.AgentTools
SubAgentTools = types.SubAgentTools
Message = types.Message
TodoItem = types.TodoItem
ReplyToUser = types.ReplyToUser