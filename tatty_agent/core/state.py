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

    # Streaming callbacks for real-time chat experience
    on_response_chunk: Optional[Callable[[str], Awaitable[None]]] = None  # (chunk) - Stream response text character by character
    on_thinking_start: Optional[Callable[[], Awaitable[None]]] = None  # () - Agent starts thinking
    on_thinking_update: Optional[Callable[[str], Awaitable[None]]] = None  # (status) - Update thinking status


class StreamingCallbacks(AgentCallbacks):
    """
    Streaming-aware callbacks implementation for real-time chat widgets.

    This class connects agent execution events directly to chat UI updates,
    enabling character-by-character streaming and visible tool execution.
    """

    def __init__(self, stream_handler, message_id: str):
        """
        Initialize streaming callbacks.

        Args:
            stream_handler: StreamingChatResponse instance for UI updates
            message_id: Unique ID for the chat message being processed
        """
        super().__init__()
        self.stream = stream_handler
        self.message_id = message_id

        # Wire up streaming callbacks
        self.on_thinking_start = self._on_thinking_start
        self.on_thinking_update = self._on_thinking_update
        self.on_tool_start = self._on_tool_start
        self.on_tool_result = self._on_tool_result
        self.on_response_chunk = self._on_response_chunk
        self.on_iteration = self._on_iteration
        self.on_status_update = self._on_status_update

    async def _on_thinking_start(self):
        """Agent starts thinking - show initial thinking bubble"""
        await self.stream.start_thinking_message(self.message_id)

    async def _on_thinking_update(self, status: str):
        """Update thinking status display"""
        await self.stream.update_thinking_status(status, self.message_id)

    async def _on_tool_start(self, tool_name: str, params: dict, tool_idx: int, total_tools: int, depth: int):
        """Tool execution starts - show in chat flow"""
        await self.stream.show_tool_execution(tool_name, params, self.message_id)

    async def _on_tool_result(self, result: str, depth: int):
        """Tool completes - update chat with result"""
        await self.stream.update_tool_result(result, self.message_id)

    async def _on_response_chunk(self, chunk: str):
        """Stream response text character by character"""
        await self.stream.stream_response_chunk(chunk, self.message_id)

    async def _on_iteration(self, iteration: int, depth: int):
        """Agent iteration progress"""
        await self.stream.update_thinking_status(f"🔄 Iteration {iteration}", self.message_id)

    async def _on_status_update(self, status: str, iteration: int):
        """General status updates"""
        await self.stream.update_thinking_status(f"{status} (iteration {iteration})", self.message_id)