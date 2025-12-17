// Agent Tool Definitions
// Each tool has an action field with the tool name and its full description

class AgentTool {
  action "Agent" @description(#"
    Launch a new agent that has access to the following tools: Bash, Glob, Grep, LS, exit_plan_mode, Read, WebFetch, TodoRead, TodoWrite. When you are searching for a keyword or file and are not confident that you will find the right match in the first few tries, use the Agent tool to perform the search for you.

    When to use the Agent tool:
    - If you are searching for a keyword like "config" or "logger", or for questions like "which file does X?", the Agent tool is strongly recommended

    When NOT to use the Agent tool:
    - If you want to read a specific file path, use the Read or Glob tool instead of the Agent tool, to find the match more quickly
    - If you are searching for a specific class definition like "class Foo", use the Glob tool instead, to find the match more quickly
    - If you are searching for code within a specific file or set of 2-3 files, use the Read tool instead of the Agent tool, to find the match more quickly
    - Writing code and running bash commands (use other tools for that)

    Usage notes:
    1. Launch multiple agents concurrently whenever possible, to maximize performance; to do that, use a single message with multiple tool uses
    2. When the agent is done, it will return a single message back to you. The result returned by the agent is not visible to the user. To show the user the result, you should send a text message back to the user with a concise summary of the result.
    3. Each agent invocation is stateless. You will not be able to send additional messages to the agent, nor will the agent be able to communicate with you outside of its final report. Therefore, your prompt should contain a highly detailed task description for the agent to perform autonomously and you should specify exactly what information the agent should return back to you in its final and only message to you.
    4. The agent's outputs should generally be trusted
    5. Clearly tell the agent whether you expect it to write code or just to do research (search, file reads, web fetches, etc.), since it is not aware of the user's intent
  "#)
  description string @description("A short (3-5 word) description of the task")
  prompt string @description("The task for the agent to perform")
}

class BashTool {
  action "Bash" @description(#"
    Executes a given bash command in a persistent shell session with optional timeout, ensuring proper handling and security measures.

    Before executing the command, please follow these steps:

    1. Directory Verification:
       - If the command will create new directories or files, first use the LS tool to verify the parent directory exists and is the correct location
       - For example, before running "mkdir foo/bar", first use LS to check that "foo" exists and is the intended parent directory

    2. Command Execution:
       - Always quote file paths that contain spaces with double quotes (e.g., cd "path with spaces/file.txt")
       - Examples of proper quoting:
         - cd "/Users/name/My Documents" (correct)
         - cd /Users/name/My Documents (incorrect - will fail)
         - python "/path/with spaces/script.py" (correct)
         - python /path/with spaces/script.py (incorrect - will fail)
       - After ensuring proper quoting, execute the command.
       - Capture the output of the command.

    Usage notes:
      - The command argument is required.
      - You can specify an optional timeout in milliseconds (up to 600000ms / 10 minutes). If not specified, commands will timeout after 120000ms (2 minutes).
      - It is very helpful if you write a clear, concise description of what this command does in 5-10 words.
      - If the output exceeds 30000 characters, output will be truncated before being returned to you.
      - VERY IMPORTANT: You MUST avoid using search commands like `find` and `grep`. Instead use Grep, Glob, or Task to search. You MUST avoid read tools like `cat`, `head`, `tail`, and `ls`, and use Read and LS to read files.
      - If you _still_ need to run `grep`, STOP. ALWAYS USE ripgrep at `rg` first, which all Claude Code users have pre-installed.
      - When issuing multiple commands, use the ';' or '&&' operator to separate them. DO NOT use newlines (newlines are ok in quoted strings).
      - Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`. You may use `cd` if the User explicitly requests it.
  "#)
  command string @description("The command to execute")
  timeout int? @description("Optional timeout in milliseconds (max 600000)")
  description string? @description("Clear, concise description of what this command does in 5-10 words")
}

class GlobTool {
  action "Glob" @description(#"
    Fast file pattern matching tool that works with any codebase size
    - Supports glob patterns like "**/*.js" or "src/**/*.ts"
    - Returns matching file paths sorted by modification time
    - Use this tool when you need to find files by name patterns
    - When you are doing an open ended search that may require multiple rounds of globbing and grepping, use the Agent tool instead
    - You have the capability to call multiple tools in a single response. It is always better to speculatively perform multiple searches as a batch that are potentially useful.
  "#)
  pattern string @description("The glob pattern to match files against")
  path string? @description("The directory to search in. If not specified, the current working directory will be used. IMPORTANT: Omit this field to use the default directory. DO NOT enter 'undefined' or 'null' - simply omit it for the default behavior. Must be a valid directory path if provided.")
}

class GrepTool {
  action "Grep" @description(#"
    Fast content search tool that works with any codebase size
    - Searches file contents using regular expressions
    - Supports full regex syntax (eg. "log.*Error", "function\s+\w+", etc.)
    - Filter files by pattern with the include parameter (eg. "*.js", "*.{ts,tsx}")
    - Returns file paths with at least one match sorted by modification time
    - Use this tool when you need to find files containing specific patterns
    - If you need to identify/count the number of matches within files, use the Bash tool with `rg` (ripgrep) directly. Do NOT use `grep`.
    - When you are doing an open ended search that may require multiple rounds of globbing and grepping, use the Agent tool instead
  "#)
  pattern string @description("The regular expression pattern to search for in file contents")
  path string? @description("The directory to search in. Defaults to the current working directory.")
  include string? @description("File pattern to include in the search (e.g. '*.js', '*.{ts,tsx}')")
}

class LSTool {
  action "LS" @description(#"
    Lists files and directories in a given path. The path parameter must be an absolute path, not a relative path. You can optionally provide an array of glob patterns to ignore with the ignore parameter. You should generally prefer the Glob and Grep tools, if you know which directories to search.
  "#)
  path string @description("The absolute path to the directory to list (must be absolute, not relative)")
  ignore string[]? @description("List of glob patterns to ignore")
}

class ExitPlanModeTool {
  action "exit_plan_mode" @description(#"
    Use this tool when you are in plan mode and have finished presenting your plan and are ready to code. This will prompt the user to exit plan mode.
  "#)
  plan string @description("The plan you came up with, that you want to run by the user for approval. Supports markdown. The plan should be pretty concise.")
}

class ReadTool {
  action "Read" @description(#"
    Reads a file from the local filesystem. You can access any file directly by using this tool.
    Assume this tool is able to read all files on the machine. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

    Usage:
    - The file_path parameter must be an absolute path, not a relative path
    - By default, it reads up to 2000 lines starting from the beginning of the file
    - You can optionally specify a line offset and limit (especially handy for long files), but it's recommended to read the whole file by not providing these parameters
    - Any lines longer than 2000 characters will be truncated
    - Results are returned using cat -n format, with line numbers starting at 1
    - This tool allows Claude Code to read images (eg PNG, JPG, etc). When reading an image file the contents are presented visually as Claude Code is a multimodal LLM.
    - You have the capability to call multiple tools in a single response. It is always better to speculatively read multiple files as a batch that are potentially useful. 
    - You will regularly be asked to read screenshots. If the user provides a path to a screenshot ALWAYS use this tool to view the file at the path. This tool will work with all temporary file paths like /var/folders/123/abc/T/TemporaryItems/NSIRD_screencaptureui_ZfB1tD/Screenshot.png
    - If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents.
  "#)
  file_path string @description("The absolute path to the file to read")
  offset int? @description("The line number to start reading from. Only provide if the file is too large to read at once")
  limit int? @description("The number of lines to read. Only provide if the file is too large to read at once.")
}

class EditTool {
  action "Edit" @description(#"
    Performs exact string replacements in files. 

    Usage:
    - You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file. 
    - When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + tab. Everything after that tab is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
    - ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
    - Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
    - The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`. 
    - Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance.
  "#)
  file_path string @description("The absolute path to the file to modify")
  old_string string @description("The text to replace")
  new_string string @description("The text to replace it with (must be different from old_string)")
  replace_all bool? @description("Replace all occurences of old_string (default false)")
}

class EditOperation {
  old_string string @description("The text to replace")
  new_string string @description("The text to replace it with")
  replace_all bool? @description("Replace all occurences of old_string. This parameter is optional and defaults to false.")
}

class MultiEditTool {
  action "MultiEdit" @description(#"
    This is a tool for making multiple edits to a single file in one operation. It is built on top of the Edit tool and allows you to perform multiple find-and-replace operations efficiently. Prefer this tool over the Edit tool when you need to make multiple edits to the same file.

    Before using this tool:

    1. Use the Read tool to understand the file's contents and context
    2. Verify the directory path is correct

    To make multiple file edits, provide the following:
    1. file_path: The absolute path to the file to modify (must be absolute, not relative)
    2. edits: An array of edit operations to perform

    IMPORTANT:
    - All edits are applied in sequence, in the order they are provided
    - Each edit operates on the result of the previous edit
    - All edits must be valid for the operation to succeed - if any edit fails, none will be applied
    - This tool is ideal when you need to make several changes to different parts of the same file
    - For Jupyter notebooks (.ipynb files), use the NotebookEdit instead

    CRITICAL REQUIREMENTS:
    1. All edits follow the same requirements as the single Edit tool
    2. The edits are atomic - either all succeed or none are applied
    3. Plan your edits carefully to avoid conflicts between sequential operations

    WARNING:
    - The tool will fail if edits.old_string doesn't match the file contents exactly (including whitespace)
    - The tool will fail if edits.old_string and edits.new_string are the same
    - Since edits are applied in sequence, ensure that earlier edits don't affect the text that later edits are trying to find

    When making edits:
    - Ensure all edits result in idiomatic, correct code
    - Do not leave the code in a broken state
    - Always use absolute file paths (starting with /)
    - Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
    - Use replace_all for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance.

    If you want to create a new file, use:
    - A new file path, including dir name if needed
    - First edit: empty old_string and the new file's contents as new_string
    - Subsequent edits: normal edit operations on the created content
  "#)
  file_path string @description("The absolute path to the file to modify")
  edits EditOperation[] @description("Array of edit operations to perform sequentially on the file")
}

class WriteTool {
  action "Write" @description(#"
    Writes a file to the local filesystem.

    Usage:
    - This tool will overwrite the existing file if there is one at the provided path.
    - If this is an existing file, you MUST use the Read tool first to read the file's contents. This tool will fail if you did not read the file first.
    - ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
    - NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
    - Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked.
  "#)
  file_path string @description("The absolute path to the file to write (must be absolute, not relative)")
  content string @description("The content to write to the file")
}

class NotebookReadTool {
  action "NotebookRead" @description(#"
    Reads a Jupyter notebook (.ipynb file) and returns all of the cells with their outputs. Jupyter notebooks are interactive documents that combine code, text, and visualizations, commonly used for data analysis and scientific computing. The notebook_path parameter must be an absolute path, not a relative path.
  "#)
  notebook_path string @description("The absolute path to the Jupyter notebook file to read (must be absolute, not relative)")
}

class NotebookEditTool {
  action "NotebookEdit" @description(#"
    Completely replaces the contents of a specific cell in a Jupyter notebook (.ipynb file) with new source. Jupyter notebooks are interactive documents that combine code, text, and visualizations, commonly used for data analysis and scientific computing. The notebook_path parameter must be an absolute path, not a relative path. The cell_number is 0-indexed. Use edit_mode=insert to add a new cell at the index specified by cell_number. Use edit_mode=delete to delete the cell at the index specified by cell_number.
  "#)
  notebook_path string @description("The absolute path to the Jupyter notebook file to edit (must be absolute, not relative)")
  cell_number int @description("The index of the cell to edit (0-based)")
  new_source string @description("The new source for the cell")
  cell_type string? @description("The type of the cell (code or markdown). If not specified, it defaults to the current cell type. If using edit_mode=insert, this is required.")
  edit_mode string? @description("The type of edit to make (replace, insert, delete). Defaults to replace.")
}

class WebFetchTool {
  action "WebFetch" @description(#"
    - Fetches content from a specified URL and processes it using an AI model
    - Takes a URL and a prompt as input
    - Fetches the URL content, converts HTML to markdown
    - Processes the content with the prompt using a small, fast model
    - Returns the model's response about the content
    - Use this tool when you need to retrieve and analyze web content

    Usage notes:
      - IMPORTANT: If an MCP-provided web fetch tool is available, prefer using that tool instead of this one, as it may have fewer restrictions. All MCP-provided tools start with "mcp__".
      - The URL must be a fully-formed valid URL
      - HTTP URLs will be automatically upgraded to HTTPS
      - The prompt should describe what information you want to extract from the page
      - This tool is read-only and does not modify any files
      - Results may be summarized if the content is very large
      - Includes a self-cleaning 15-minute cache for faster responses when repeatedly accessing the same URL
  "#)
  url string @description("The URL to fetch content from")
  prompt string @description("The prompt to run on the fetched content")
  save_to_file string? @description("Path to save the fetched content to a file. Defaults to null, which means no file will be saved.")
}

class TodoItem {
  content string
  status "pending" | "in_progress" | "completed"
  priority "high" | "medium" | "low"
  id string
}

class TodoReadTool {
  action "TodoRead" @description(#"
    Use this tool to read the current to-do list for the session. This tool should be used proactively and frequently to ensure that you are aware of
    the status of the current task list. You should make use of this tool as often as possible, especially in the following situations:
    - At the beginning of conversations to see what's pending
    - Before starting new tasks to prioritize work
    - When the user asks about previous tasks or plans
    - Whenever you're uncertain about what to do next
    - After completing tasks to update your understanding of remaining work
    - After every few messages to ensure you're on track

    Usage:
    - This tool takes in no parameters. So leave the input blank or empty. DO NOT include a dummy object, placeholder string or a key like "input" or "empty". LEAVE IT BLANK.
    - Returns a list of todo items with their status, priority, and content
    - Use this information to track progress and plan next steps
    - If no todos exist yet, an empty list will be returned
  "#)
}

class TodoWriteTool {
  action "TodoWrite" @description(#"
    Use this tool to create and manage a structured task list for your current coding session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.
    It also helps the user understand the progress of the task and overall progress of their requests.

    When to Use This Tool
    Use this tool proactively in these scenarios:

    1. Complex multi-step tasks - When a task requires 3 or more distinct steps or actions
    2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
    3. User explicitly requests todo list - When the user directly asks you to use the todo list
    4. User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)
    5. After receiving new instructions - Immediately capture user requirements as todos
    6. When you start working on a task - Mark it as in_progress BEFORE beginning work. Ideally you should only have one todo as in_progress at a time
    7. After completing a task - Mark it as completed and add any new follow-up tasks discovered during implementation

    When NOT to Use This Tool

    Skip using this tool when:
    1. There is only a single, straightforward task
    2. The task is trivial and tracking it provides no organizational benefit
    3. The task can be completed in less than 3 trivial steps
    4. The task is purely conversational or informational

    NOTE that you should not use this tool if there is only one trivial task to do. In this case you are better off just doing the task directly.

    Task States and Management

    1. Task States: Use these states to track progress:
       - pending: Task not yet started
       - in_progress: Currently working on (limit to ONE task at a time)
       - completed: Task finished successfully

    2. Task Management:
       - Update task status in real-time as you work
       - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
       - Only have ONE task in_progress at any time
       - Complete current tasks before starting new ones
       - Remove tasks that are no longer relevant from the list entirely

    3. Task Completion Requirements:
       - ONLY mark a task as completed when you have FULLY accomplished it
       - If you encounter errors, blockers, or cannot finish, keep the task as in_progress
       - When blocked, create a new task describing what needs to be resolved
       - Never mark a task as completed if:
         - Tests are failing
         - Implementation is partial
         - You encountered unresolved errors
         - You couldn't find necessary files or dependencies

    4. Task Breakdown:
       - Create specific, actionable items
       - Break complex tasks into smaller, manageable steps
       - Use clear, descriptive task names

    When in doubt, use this tool. Being proactive with task management demonstrates attentiveness and ensures you complete all requirements successfully.
  "#)
  todos TodoItem[] @description("The updated todo list")
}

class WebSearchTool {
  action "WebSearch" @description(#"
    - Allows Claude to search the web and use the results to inform responses
    - Provides up-to-date information for current events and recent data
    - Returns search result information formatted as search result blocks
    - Use this tool for accessing information beyond Claude's knowledge cutoff
    - Searches are performed automatically within a single API call

    Usage notes:
      - Domain filtering is supported to include or block specific websites
      - Web search is only available in the US
  "#)
  query string @description("The search query to use")
  allowed_domains string[]? @description("Only include search results from these domains")
  blocked_domains string[]? @description("Never include search results from these domains")
}

class PytestRunTool {
  action "PytestRun" @description(#"
    Run pytest tests and return results with detailed output formatting.

    Usage:
    - Executes pytest with specified options and paths
    - Returns formatted test results including passed/failed counts
    - Supports various pytest options like verbose mode, specific test selection
    - Handles test discovery and execution with proper working directory context
    - Provides truncated output with recovery instructions for large test suites
    - Includes coverage information when available

    Parameters:
    - test_path: Optional path to specific test file or directory (defaults to discovering all tests)
    - verbose: Enable verbose output (-v flag)
    - capture: Control output capturing (default 'no' shows print statements)
    - markers: Run only tests matching given mark expression
    - keywords: Run only tests matching given keyword expression
    - max_failures: Stop after N failures (--maxfail option)
    - timeout: Override default timeout for long-running test suites

    Examples:
    - Run all tests: PytestRun with no parameters
    - Run specific test: PytestRun with test_path="tests/test_agent.py"
    - Run with verbose output: PytestRun with verbose=true
    - Run tests matching keyword: PytestRun with keywords="test_function_name"
  "#)
  test_path string? @description("Path to test file or directory to run (defaults to test discovery)")
  verbose bool? @description("Enable verbose output (-v flag)")
  capture string? @description("Output capture mode: 'sys' (default), 'no', 'fd'")
  markers string? @description("Run tests matching given mark expression (-m option)")
  keywords string? @description("Run tests matching keyword expression (-k option)")
  max_failures int? @description("Stop after N test failures (--maxfail option)")
  timeout int? @description("Override timeout in milliseconds (default 120000)")
}

class LintTool {
  action "Lint" @description(#"
    Run Ruff linter for code quality checking with optional auto-fixing.

    Usage:
    - Performs fast Python linting using Ruff
    - Supports auto-fixing of common issues
    - Can target specific files or entire project
    - Returns formatted lint results with line numbers and issue descriptions
    - Handles large codebases with truncated output
    - Provides helpful suggestions for fixing issues

    Parameters:
    - target_path: Path to file or directory to lint (defaults to current directory)
    - fix: Automatically fix fixable lint issues
    - show_fixes: Show what fixes would be applied without making changes
    - select_codes: Comma-separated list of error codes to check (e.g. 'E,W,F')
    - ignore: Comma-separated list of error codes to ignore
    - format: Output format ('text', 'json', 'github', 'gitlab', 'junit', 'sarif')

    Examples:
    - Lint current directory: Lint with no parameters
    - Lint specific file: Lint with target_path="main.py"
    - Auto-fix issues: Lint with fix=true
    - Show potential fixes: Lint with show_fixes=true
  "#)
  target_path string? @description("Path to lint (file or directory, defaults to '.')")
  fix bool? @description("Automatically fix fixable issues")
  show_fixes bool? @description("Show fixes without applying them")
  select_codes string? @description("Comma-separated error codes to check (e.g. 'E,W,F')")
  ignore string? @description("Comma-separated error codes to ignore")
  format string? @description("Output format: 'text' (default), 'json', 'github', 'gitlab'")
}

class TypeCheckTool {
  action "TypeCheck" @description(#"
    Run static type checking using mypy or pyright for Python code analysis.

    Usage:
    - Performs static type analysis to catch type-related errors
    - Supports both mypy and pyright type checkers
    - Can target specific files or entire project
    - Returns formatted type check results with error locations
    - Handles incremental checking for faster results
    - Provides clear error messages with file and line numbers

    Parameters:
    - target_path: Path to type check (file or directory, defaults to '.')
    - checker: Type checker to use ('mypy' or 'pyright', defaults to 'mypy')
    - strict: Enable strict type checking mode
    - ignore_missing_imports: Ignore errors from missing type stubs
    - incremental: Use incremental mode for faster checking (mypy only)
    - config_file: Path to configuration file (mypy.ini, pyproject.toml, etc.)

    Examples:
    - Type check current directory: TypeCheck with no parameters
    - Type check specific file: TypeCheck with target_path="main.py"
    - Strict type checking: TypeCheck with strict=true
    - Use pyright instead: TypeCheck with checker="pyright"
  "#)
  target_path string? @description("Path to type check (defaults to '.')")
  checker string? @description("Type checker: 'mypy' (default) or 'pyright'")
  strict bool? @description("Enable strict type checking")
  ignore_missing_imports bool? @description("Ignore missing import errors")
  incremental bool? @description("Use incremental mode (mypy only)")
  config_file string? @description("Path to configuration file")
}

class FormatTool {
  action "Format" @description(#"
    Format Python code using Black formatter with consistent style.

    Usage:
    - Formats Python code according to Black's style guide
    - Can format specific files or entire directories
    - Supports diff preview before applying changes
    - Returns summary of formatting changes made
    - Handles large codebases efficiently
    - Ensures consistent code style across the project

    Parameters:
    - target_path: Path to format (file or directory, defaults to '.')
    - check_only: Only check if files would be reformatted without changing them
    - diff: Show diff of changes that would be made
    - line_length: Override maximum line length (default 88)
    - skip_string_normalization: Don't normalize string quotes
    - target_version: Python target version (e.g. 'py38', 'py39', 'py310')

    Examples:
    - Format current directory: Format with no parameters
    - Check formatting only: Format with check_only=true
    - Show formatting diff: Format with diff=true
    - Custom line length: Format with line_length=100
  "#)
  target_path string? @description("Path to format (defaults to '.')")
  check_only bool? @description("Check formatting without making changes")
  diff bool? @description("Show diff of formatting changes")
  line_length int? @description("Maximum line length (default 88)")
  skip_string_normalization bool? @description("Don't normalize string quotes")
  target_version string? @description("Python target version (py38, py39, py310, etc.)")
}

class DependencyTool {
  action "Dependency" @description(#"
    Check and manage Python dependencies and package versions.

    Usage:
    - Compares installed packages with requirements
    - Identifies outdated or missing dependencies
    - Can check if specific packages can be imported
    - Can show dependency tree and conflicts
    - Supports multiple requirements file formats
    - Returns formatted dependency analysis
    - Helps maintain project dependency health

    Parameters:
    - check_type: Type of check ('outdated', 'missing', 'tree', 'imports')
    - requirements_file: Path to requirements file (defaults to 'pyproject.toml')
    - packages: List of package names to check (for 'imports' check_type)
    - update_available: Show available updates for packages
    - include_dev: Include development dependencies in analysis

    Examples:
    - Check missing deps: Dependency with check_type="missing"
    - Find outdated packages: Dependency with check_type="outdated"
    - Show dependency tree: Dependency with check_type="tree"
    - Check imports: Dependency with check_type="imports", packages=["pandas", "numpy"]
    - Include dev deps: Dependency with include_dev=true
  "#)
  check_type string? @description("Check type: 'outdated', 'missing', 'tree', 'imports'")
  requirements_file string? @description("Requirements file path (default 'pyproject.toml')")
  packages string[]? @description("Package names to check (for 'imports' check_type)")
  update_available bool? @description("Show available package updates")
  include_dev bool? @description("Include development dependencies")
}

class GitDiffTool {
  action "GitDiff" @description(#"
    Compare files or directories against git HEAD or other references.

    Usage:
    - Shows differences between working directory and git references
    - Can compare specific files or entire directories
    - Supports various diff formats and context options
    - Handles large diffs with intelligent truncation
    - Useful for code review and change analysis
    - Provides clear context about what has changed

    Parameters:
    - target_path: Path to diff (file or directory, defaults to all changes)
    - reference: Git reference to compare against (default 'HEAD')
    - staged: Show staged changes instead of working directory
    - stat: Show diffstat summary instead of full diff
    - context_lines: Number of context lines around changes
    - ignore_whitespace: Ignore whitespace changes

    Examples:
    - Show all changes: GitDiff with no parameters
    - Diff specific file: GitDiff with target_path="main.py"
    - Compare to different branch: GitDiff with reference="main"
    - Show staged changes: GitDiff with staged=true
  "#)
  target_path string? @description("Path to diff (defaults to all changes)")
  reference string? @description("Git reference to compare (default 'HEAD')")
  staged bool? @description("Show staged changes")
  stat bool? @description("Show diffstat summary")
  context_lines int? @description("Context lines around changes (default 3)")
  ignore_whitespace bool? @description("Ignore whitespace changes")
}

class InstallPackagesTool {
  action "InstallPackages" @description(#"
    Install PYTHON PACKAGES ONLY using uv or pip with user permission.

    PYTHON PACKAGES ONLY - This tool is restricted to Python packages available on PyPI.
    DO NOT use for system dependencies like:
    - brew packages (homebrew)
    - node packages (npm)
    - system binaries (apt, yum, etc.)
    - compiled tools (git, docker, etc.)

    For non-Python dependencies, prefer Python alternatives or use WebSearch to find them:
    - Instead of 'git' → use 'GitPython'
    - Instead of 'node tools' → find Python equivalents
    - Instead of 'system tools' → search for Python implementations

    Usage:
    - Automatically detects whether to use uv or pip
    - Installs Python packages with proper dependency resolution
    - Validates packages are Python-compatible before installation
    - Provides clear feedback on installation success/failure
    - Can install multiple packages at once
    - Handles both production and development dependencies

    IMPORTANT: This tool should only be used after the agent has:
    1. Detected missing PYTHON packages needed for a task
    2. Asked the user for permission to install packages
    3. Received explicit user approval
    4. Verified packages are available on PyPI (Python packages only)

    Parameters:
    - packages: List of PYTHON package names to install (required)
    - dev: Install as development dependencies (optional, defaults to false)
    - upgrade: Upgrade packages if already installed (optional, defaults to false)
    - user_confirmed: Confirmation that user approved installation (required)

    Examples:
    - Install plotting libs: InstallPackages with packages=["pandas", "matplotlib", "seaborn"], user_confirmed=true
    - Install dev deps: InstallPackages with packages=["pytest", "black"], dev=true, user_confirmed=true
    - Install web tools: InstallPackages with packages=["requests", "beautifulsoup4"], user_confirmed=true
  "#)
  packages string[] @description("PYTHON package names to install (PyPI packages only)")
  dev bool? @description("Install as development dependencies (default false)")
  upgrade bool? @description("Upgrade packages if already installed (default false)")
  user_confirmed bool @description("User has confirmed installation (required for safety)")
}

class ArtifactManagementTool {
  action "ArtifactManagement" @description(#"
    Manage and organize project artifacts in standard folders to avoid duplication.

    Standard Folder Structure:
    - scripts/ : Python scripts, code generators, analysis tools
    - data/ : CSV files, datasets, JSON files, text data
    - visualization/ : Plots, charts, images, visual outputs
    - plots/ : Legacy plot folder (use visualization/ for new plots)

    Usage:
    - Check what artifacts already exist before creating new ones
    - Find related outputs from previous work
    - Organize new artifacts in appropriate folders
    - Prevent token waste by reusing existing scripts/data
    - Maintain clean project structure

    IMPORTANT: Always check existing artifacts before creating new ones!
    This saves tokens and builds on previous work instead of duplicating effort.

    Parameters:
    - action_type: What to do ('list', 'find', 'organize', 'clean')
    - folder: Specific folder to work with (optional)
    - pattern: File pattern to search for (optional)
    - artifact_type: Type of artifact ('script', 'data', 'visualization', 'any')

    Examples:
    - List all scripts: ArtifactManagement with action_type="list", artifact_type="script"
    - Find plotting scripts: ArtifactManagement with action_type="find", pattern="*plot*"
    - Check data files: ArtifactManagement with action_type="list", folder="data"
    - Organize outputs: ArtifactManagement with action_type="organize"
  "#)
  action_type string @description("Action to perform: 'list', 'find', 'organize', 'clean'")
  folder string? @description("Specific folder to work with (scripts/data/visualization/plots)")
  pattern string? @description("File pattern to search for (e.g., '*plot*', '*.csv')")
  artifact_type string? @description("Type of artifact: 'script', 'data', 'visualization', 'any'")
}

// Union type for all tools
type ScaryTools =  EditTool | MultiEditTool | WriteTool | NotebookEditTool | TodoWriteTool
type CodingTools = PytestRunTool | LintTool | TypeCheckTool | FormatTool | DependencyTool | GitDiffTool | InstallPackagesTool | ArtifactManagementTool
type AgentTools = SubAgentTools | AgentTool
type SubAgentTools = BashTool | GlobTool | GrepTool | LSTool | ExitPlanModeTool | ReadTool | WebFetchTool | TodoReadTool | TodoWriteTool | WebSearchTool | ScaryTools | CodingTools
