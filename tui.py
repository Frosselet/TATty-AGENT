"""
BAMMY Agent TUI - Beautiful Text User Interface
"""
import asyncio
import os
from typing import Optional

from textual.app import App, ComposeResult  # type: ignore
from textual.containers import Container, Horizontal, Vertical  # type: ignore
from textual.widgets import Header, Footer, Input, Static, RichLog  # type: ignore
from textual.binding import Binding  # type: ignore
from rich.text import Text  # type: ignore
from rich.panel import Panel  # type: ignore
from rich.table import Table  # type: ignore

from dotenv import load_dotenv  # type: ignore

# Import from shared modules
from agent_runtime import AgentState, AgentCallbacks, AgentRuntime


class StatusBar(Static):
    """Status bar showing current state"""
    
    def __init__(self):
        super().__init__()
        self.iteration = 0
        self.working_dir = os.getcwd()
        self.status = "Ready"
    
    def update_status(self, status: str, iteration: Optional[int] = None):
        self.status = status
        if iteration is not None:
            self.iteration = iteration
        self.refresh()
    
    def render(self) -> Text:
        text = Text()
        text.append("📁 ", style="bold cyan")
        text.append(self.working_dir, style="cyan")
        text.append("  |  ", style="dim")
        text.append("🔄 Iteration: ", style="bold yellow")
        text.append(str(self.iteration), style="yellow")
        text.append("  |  ", style="dim")
        text.append("📊 ", style="bold green")
        text.append(self.status, style="green")
        return text


class TodoPanel(Static):
    """Panel showing the current todo list"""
    
    def render(self) -> Panel:
        # Import fresh reference to _todo_store to ensure we get updates
        from main import _todo_store
        
        if not _todo_store:
            content = Text("No todos", style="dim italic")
        else:
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Status", style="bold")
            table.add_column("Task")
            
            for todo in _todo_store[:10]:  # Show first 10
                status_icon = "✓" if todo.status == "completed" else "→" if todo.status == "in_progress" else "○"
                style = "green" if todo.status == "completed" else "yellow" if todo.status == "in_progress" else "dim"
                table.add_row(status_icon, todo.content, style=style)
            
            if len(_todo_store) > 10:
                table.add_row("...", f"and {len(_todo_store) - 10} more", style="dim")
            
            content = table
        
        return Panel(
            content,
            title="[bold cyan]📋 Todos[/]",
            border_style="cyan"
        )


class AgentLog(RichLog):
    """Log showing agent activity"""
    
    def __init__(self):
        super().__init__(highlight=True, markup=True, wrap=True, auto_scroll=True)
        self.max_lines = 1000
    
    def log_user(self, query: str):
        self.write(Panel(
            Text(query, style="bold white"),
            title="[bold blue]👤 User Query[/]",
            border_style="blue"
        ))
    
    def log_iteration(self, iteration: int):
        # Only show iteration number, no separators
        self.write(Text(f"\nIteration {iteration}", style="bold yellow"))
    
    def log_tool(self, tool_name: str, params: dict):
        # Show only essential parameters in a compact format
        essential_keys = ['file_path', 'pattern', 'command', 'path', 'url', 'prompt', 'description']
        essential_params = {k: v for k, v in params.items() if k in essential_keys and v is not None}
        
        if essential_params:
            param_text = Text()
            for key, value in essential_params.items():
                param_text.append(f"{key}: ", style="cyan")
                param_str = str(value)
                if len(param_str) > 80:
                    param_str = param_str[:80] + "..."
                param_text.append(f"{param_str}\n", style="white")
            
            self.write(Panel(
                param_text,
                title=f"[bold magenta]🔧 {tool_name}[/]",
                border_style="magenta"
            ))
        else:
            # If no essential params, just show the tool name inline
            self.write(Text(f"🔧 {tool_name}", style="bold magenta"))
    
    def log_result(self, result: str):
        result_length = len(result)
        result_text = result
        
        # Truncate for display if too long
        display_limit = 500  # Compact display
        if result_length > display_limit:
            result_text = result[:display_limit] + f"\n... ({result_length} chars total)"
        
        self.write(Panel(
            Text(result_text, style="white"),
            title=f"[bold green]✅ Result ({result_length} chars)[/]",
            border_style="green"
        ))
    
    def log_agent_reply(self, message: str):
        self.write(Panel(
            Text(message, style="bold green"),
            title="[bold green]🤖 Agent Reply[/]",
            border_style="green"
        ))
    
    def log_error(self, error: str):
        self.write(Panel(
            Text(error, style="bold red"),
            title="[bold red]❌ Error[/]",
            border_style="red"
        ))


class CommandInput(Input):
    """Input field for commands"""
    
    def __init__(self):
        super().__init__(
            placeholder="Enter your command... (Ctrl+C to exit)",
            id="command_input"
        )


class BAMMYApp(App):
    """BAMMY Agent TUI Application"""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #status_bar {
        dock: top;
        height: 1;
        background: $boost;
        color: $text;
        padding: 0 1;
    }
    
    #main_container {
        height: 1fr;
    }
    
    #content_area {
        width: 3fr;
    }
    
    #todo_panel {
        width: 1fr;
        border-left: solid $primary;
        padding: 1;
    }
    
    #agent_log {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    
    #input_container {
        dock: bottom;
        height: 3;
        background: $boost;
        padding: 0 1;
    }
    
    CommandInput {
        margin: 0 0;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+r", "reset_conversation", "Reset Chat", show=True),
        Binding("ctrl+x", "interrupt_agent", "Interrupt", show=True),
    ]
    
    def __init__(self, working_dir: Optional[str] = None, initial_query: Optional[str] = None):
        super().__init__()
        if working_dir:
            os.chdir(working_dir)
        self.working_dir = os.getcwd()
        self.is_processing = False
        self.initial_query = initial_query
        
        # Shared agent state
        self.agent_state = AgentState(working_dir=self.working_dir)
        
        # Setup callbacks for UI updates
        self.callbacks = AgentCallbacks(
            on_iteration=self.on_iteration,
            on_tool_start=self.on_tool_start,
            on_tool_result=self.on_tool_result,
            on_agent_reply=self.on_agent_reply,
            on_status_update=self.on_status_update,
            on_sub_agent_start=self.on_sub_agent_start,
            on_sub_agent_complete=self.on_sub_agent_complete,
        )
        
        self.agent_runtime = AgentRuntime(self.agent_state, self.callbacks)
        self.current_task: Optional[asyncio.Task] = None
    
    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield Header(show_clock=True)
        
        status = StatusBar()
        status.id = "status_bar"
        yield status
        
        with Horizontal(id="main_container"):
            with Vertical(id="content_area"):
                log = AgentLog()
                log.id = "agent_log"
                yield log
            
            todo = TodoPanel()
            todo.id = "todo_panel"
            yield todo
        
        with Container(id="input_container"):
            cmd_input = CommandInput()
            yield cmd_input
        
        yield Footer()
    
    def on_mount(self) -> None:
        """App mounted"""
        log = self.query_one(AgentLog)
        log.write(Panel(
            Text.from_markup(
                "[bold cyan]🤖 BAMMY Agent[/]\n\n"
                "Welcome! Enter commands below to interact with the agent.\n"
                f"Working directory: [yellow]{self.working_dir}[/]\n"
                f"Conversation history: [green]Maintained across commands[/]\n\n"
                "[dim]Shortcuts:[/]\n"
                "[dim]  Ctrl+R: Reset conversation history[/]\n"
                "[dim]  Ctrl+X: Interrupt agent execution[/]\n"
                "[dim]  Ctrl+C: Quit application[/]\n"
                "[dim]  Enter (empty): Continue agent execution[/]"
            ),
            border_style="cyan"
        ))
        self.query_one(CommandInput).focus()
        
        # Process initial query if provided (but skip generic startup commands)
        if self.initial_query and self.initial_query.strip().lower() not in ["start", "begin", "go", ""]:
            self.call_later(self.process_command, self.initial_query)
        elif self.initial_query and self.initial_query.strip().lower() in ["start", "begin", "go"]:
            # Show a helpful message for generic startup commands
            log = self.query_one(AgentLog)
            log.write(Text("🚀 BAMMY Agent ready! Type your command below and press Enter.", style="bold cyan"))
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command submission"""
        command = event.value.strip()
        
        # Clear input
        event.input.value = ""
        
        if self.is_processing:
            log = self.query_one(AgentLog)
            log.log_error("Agent is already processing a command. Please wait.")
            return
        
        # Process the command (empty command continues agent execution)
        await self.process_command(command)
    
    def action_reset_conversation(self) -> None:
        """Reset conversation history (Ctrl+R)"""
        if self.is_processing:
            return  # Don't reset while processing
        
        self.agent_state.messages = []
        self.agent_state.current_iteration = 0
        log = self.query_one(AgentLog)
        log.clear()
        log.write(Panel(
            Text.from_markup(
                "[bold yellow]🔄 Conversation History Reset[/]\n\n"
                "Starting fresh! Previous context has been cleared."
            ),
            border_style="yellow"
        ))
        self.query_one(CommandInput).focus()
    
    def action_interrupt_agent(self) -> None:
        """Interrupt the current agent execution (Ctrl+X)"""
        if not self.is_processing:
            return

        # Check if already requested interrupt (double Ctrl+X for force quit)
        if self.agent_state.interrupt_requested:
            log = self.query_one(AgentLog)
            log.write(Panel(
                Text.from_markup(
                    "🛑 [bold red]Force termination requested![/] Attempting to stop all operations immediately.\n\n"
                    "[dim]This may leave some operations in an incomplete state.[/]"
                ),
                title="[bold red]🚨 Force Stop[/]",
                border_style="red"
            ))
            # Signal immediate termination
            self.agent_state.interrupt_requested = True
            return

        # First interrupt request - graceful stop
        self.agent_state.interrupt_requested = True
        log = self.query_one(AgentLog)
        log.write(Panel(
            Text.from_markup(
                "🚨 [bold yellow]Interrupt requested![/] The agent will stop gracefully after current operation completes.\n\n"
                "[dim]Press Ctrl+X again to force immediate termination.[/]\n"
                "[dim]Current operation will finish cleanly before stopping.[/]"
            ),
            title="[bold yellow]⚠️  Interrupting Agent[/]",
            border_style="yellow"
        ))

        # Update status bar to show interrupt state
        status = self.query_one(StatusBar)
        status.update_status("Interrupting...")
    
    # Callback methods for AgentRuntime
    async def on_iteration(self, iteration: int, depth: int) -> None:
        """Callback when iteration starts"""
        log = self.query_one(AgentLog)
        if depth > 0:
            log.write(Text(f"\n{'  ' * depth}└─ Sub-agent Iteration {iteration}", style="dim cyan"))
        else:
            log.log_iteration(iteration)
        await asyncio.sleep(0.01)
    
    async def on_tool_start(self, tool_name: str, params: dict, tool_idx: int, total_tools: int, depth: int) -> None:
        """Callback when tool execution starts"""
        log = self.query_one(AgentLog)
        if depth > 0:
            log.write(Text(f"{'  ' * depth}  └─ 🔧 {tool_name} ({tool_idx}/{total_tools})", style="dim magenta"))
        else:
            log.log_tool(tool_name, params)
        await asyncio.sleep(0.01)
    
    async def on_tool_result(self, result: str, depth: int) -> None:
        """Callback when tool execution completes"""
        log = self.query_one(AgentLog)
        if depth > 0:
            result_length = len(result)
            if result_length > 80:
                result_preview = result[:80] + f"... [showing 80 of {result_length} chars]"
            else:
                result_preview = result
            log.write(Text(f"{'  ' * depth}     ✓ {result_preview}", style="dim green"))
        else:
            log.log_result(result)
        
        # Update todo panel and refresh entire app to ensure todos are visible
        self.query_one(TodoPanel).refresh()
        self.refresh()
        await asyncio.sleep(0.01)
    
    async def on_agent_reply(self, message: str) -> None:
        """Callback when agent replies to user"""
        # This is handled in process_command
        pass
    
    async def on_status_update(self, status: str, iteration: int) -> None:
        """Callback for status updates"""
        status_bar = self.query_one(StatusBar)
        depth_indicator = f" [Sub-agent L{self.agent_state.current_depth}]" if self.agent_state.current_depth > 0 else ""
        status_bar.update_status(f"{status}{depth_indicator}", iteration)
        await asyncio.sleep(0.01)
    
    async def on_sub_agent_start(self, description: str, prompt: str, depth: int) -> None:
        """Callback when sub-agent starts"""
        log = self.query_one(AgentLog)
        log.write(Panel(
            Text.from_markup(
                f"[bold cyan]🔄 Launching Sub-agent (Level {depth})[/]\n"
                f"Task: [yellow]{description}[/]\n"
                f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}"
            ),
            border_style="cyan",
            title=f"[bold cyan]Sub-agent L{depth}[/]"
        ))
        await asyncio.sleep(0.01)
    
    async def on_sub_agent_complete(self, result: str, depth: int) -> None:
        """Callback when sub-agent completes"""
        log = self.query_one(AgentLog)
        log.write(Panel(
            Text(result[:200] + "..." if len(result) > 200 else result, style="green"),
            title=f"[bold green]✓ Sub-agent L{depth} Complete[/]",
            border_style="green"
        ))
        await asyncio.sleep(0.01)
    
    async def process_command(self, query: str) -> None:
        """Process a user command"""
        self.is_processing = True
        self.agent_state.interrupt_requested = False
        self.agent_state.current_iteration = 0
        log = self.query_one(AgentLog)
        status = self.query_one(StatusBar)
        
        try:
            # Only log non-empty queries as user input
            if query:
                log.log_user(query)
            else:
                log.write(Text("Continuing agent execution...", style="dim"))
            
            status.update_status("Processing...", 0)
            
            # Run agent using shared runtime
            result = await self.agent_runtime.run_loop(query, max_iterations=20, depth=0)
            
            if self.agent_state.interrupt_requested:
                log.write(Panel(
                    Text.from_markup(
                        "🛑 [bold yellow]Agent execution was interrupted by user.[/]\n\n"
                        f"[dim]Final result:[/] {result[:200]}{'...' if len(result) > 200 else ''}"
                    ),
                    title="[bold yellow]⚠️  Interrupted[/]",
                    border_style="yellow"
                ))
            else:
                log.log_agent_reply(result)
            
            status.update_status("Ready")
            
        except asyncio.CancelledError:
            log.write(Panel(
                Text("Agent execution was cancelled.", style="red"),
                title="[bold red]❌ Cancelled[/]",
                border_style="red"
            ))
            status.update_status("Cancelled")
        except Exception as e:
            log.log_error(f"Error: {str(e)}")
            status.update_status("Error")
        finally:
            self.is_processing = False
            self.agent_state.interrupt_requested = False
            self.current_task = None
            self.query_one(CommandInput).focus()
            
            # Update todo panel
            self.query_one(TodoPanel).refresh()


def run_tui(working_dir: Optional[str] = None, initial_query: Optional[str] = None):
    """Run the TUI application"""
    load_dotenv()
    app = BAMMYApp(working_dir=working_dir, initial_query=initial_query)
    app.run()


if __name__ == "__main__":
    run_tui()

