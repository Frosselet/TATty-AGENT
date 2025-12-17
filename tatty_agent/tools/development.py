"""
Development tools for TATty Agent

This module contains development-related tools extracted from main.py:
- PytestRun: Run pytest tests with comprehensive options
- Lint: Run Ruff linter with auto-fixing capabilities
- TypeCheck: Run static type checking (mypy/pyright)
- Format: Run code formatting (Ruff/Black)
- Dependency: Manage Python dependencies (uv/pip)
- GitDiff: View git diff information
"""
import subprocess
from pathlib import Path

from ..baml_client import types
from .registry import register_tool


@register_tool("PytestRun")
def execute_pytest_run(tool: types.PytestRunTool, working_dir: str = ".") -> str:
    """Run pytest tests and return formatted results"""
    try:
        # Build pytest command
        cmd = ["python", "-m", "pytest"]

        # Add test path if specified
        if tool.test_path:
            cmd.append(tool.test_path)

        # Add pytest options
        if tool.verbose:
            cmd.append("-v")

        if tool.capture:
            cmd.extend(["-s"] if tool.capture == "no" else [f"--capture={tool.capture}"])

        if tool.markers:
            cmd.extend(["-m", tool.markers])

        if tool.keywords:
            cmd.extend(["-k", tool.keywords])

        if tool.max_failures:
            cmd.extend(["--maxfail", str(tool.max_failures)])

        # Add output formatting
        cmd.extend(["--tb=short", "--no-header"])

        # Execute with timeout
        timeout = (tool.timeout / 1000) if tool.timeout else 120
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir
        )

        # Format output
        output_lines = []

        # Add command info
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append(f"Working directory: {working_dir}")
        output_lines.append("")

        # Process stdout
        if result.stdout:
            stdout_lines = result.stdout.strip().split('\n')

            # Extract test summary
            summary_line = None
            for line in stdout_lines:
                if " passed" in line or " failed" in line or " error" in line:
                    summary_line = line
                    break

            if summary_line:
                output_lines.append(f"Test Summary: {summary_line}")
                output_lines.append("")

            # Add detailed output (truncated if needed)
            if len(stdout_lines) > 100:
                output_lines.extend(stdout_lines[:50])
                output_lines.append(f"\n... [Truncated: showing first 50 of {len(stdout_lines)} lines]")
                output_lines.append("To see full output, run PytestRun with specific test_path")
                output_lines.extend(stdout_lines[-20:])  # Show last 20 lines
            else:
                output_lines.extend(stdout_lines)

        # Add stderr if present
        if result.stderr:
            output_lines.append("\nErrors:")
            stderr_lines = result.stderr.strip().split('\n')
            if len(stderr_lines) > 20:
                output_lines.extend(stderr_lines[:20])
                output_lines.append(f"... [Error output truncated: {len(stderr_lines)} total lines]")
            else:
                output_lines.extend(stderr_lines)

        # Add exit code
        output_lines.append(f"\nExit code: {result.returncode}")

        return "\n".join(output_lines)

    except FileNotFoundError:
        return "Error: pytest not found. Install with: pip install pytest"
    except subprocess.TimeoutExpired:
        return f"Error: pytest timed out after {timeout}s. Consider using max_failures or specific test_path"
    except Exception as e:
        return f"Error running pytest: {str(e)}"


@register_tool("Lint")
def execute_lint(tool: types.LintTool, working_dir: str = ".") -> str:
    """Run Ruff linter with optional auto-fixing"""
    try:
        # Build ruff command
        cmd = ["ruff", "check"]

        # Add target path
        target = tool.target_path or "."
        cmd.append(target)

        # Add options
        if tool.fix:
            cmd.append("--fix")

        if tool.show_fixes:
            cmd.extend(["--diff", "--preview"])

        if tool.select_codes:
            cmd.extend(["--select", tool.select_codes])

        if tool.ignore:
            cmd.extend(["--ignore", tool.ignore])

        if tool.format and tool.format != "text":
            cmd.extend(["--format", tool.format])

        # Execute ruff
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # Ruff is fast, 60s should be plenty
            cwd=working_dir
        )

        # Format output
        output_lines = []
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append(f"Target: {target}")
        output_lines.append("")

        if result.returncode == 0:
            if tool.fix:
                output_lines.append("✅ All fixable issues have been resolved")
            else:
                output_lines.append("✅ No lint issues found")

            if result.stdout and result.stdout.strip():
                output_lines.append("Details:")
                output_lines.append(result.stdout.strip())
        else:
            # Process lint issues
            if result.stdout:
                stdout_lines = result.stdout.strip().split('\n')

                # Count issues
                issue_count = len([line for line in stdout_lines if line.strip() and not line.startswith("Found")])

                if issue_count > 0:
                    if tool.fix:
                        output_lines.append(f"🔧 Fixed {issue_count} issues:")
                    else:
                        output_lines.append(f"⚠️  Found {issue_count} lint issues:")

                    output_lines.append("")

                # Truncate if too many issues
                if len(stdout_lines) > 50:
                    output_lines.extend(stdout_lines[:40])
                    output_lines.append(f"\n... [Truncated: showing first 40 of {len(stdout_lines)} lines]")
                    output_lines.append("Run with specific target_path to focus analysis")
                    output_lines.extend(stdout_lines[-10:])
                else:
                    output_lines.extend(stdout_lines)

        if result.stderr:
            output_lines.append("\nErrors:")
            output_lines.append(result.stderr)

        output_lines.append(f"\nExit code: {result.returncode}")

        return "\n".join(output_lines)

    except FileNotFoundError:
        return "Error: ruff not found. Install with: pip install ruff"
    except subprocess.TimeoutExpired:
        return "Error: ruff timed out. Consider using a more specific target_path"
    except Exception as e:
        return f"Error running ruff: {str(e)}"


@register_tool("TypeCheck")
def execute_type_check(tool: types.TypeCheckTool, working_dir: str = ".") -> str:
    """Run static type checking"""
    try:
        checker = tool.checker or "mypy"
        target = tool.target_path or "."

        if checker == "mypy":
            cmd = ["mypy", target]

            if tool.strict:
                cmd.append("--strict")

            if tool.ignore_missing_imports:
                cmd.append("--ignore-missing-imports")

            if tool.incremental:
                cmd.extend(["--incremental", "--cache-dir", ".mypy_cache"])

            if tool.config_file:
                cmd.extend(["--config-file", tool.config_file])

        elif checker == "pyright":
            cmd = ["pyright", target]

            if tool.strict:
                cmd.append("--level=error")

            # Pyright reads configuration from pyrightconfig.json or pyproject.toml
            if tool.config_file:
                cmd.extend(["--project", tool.config_file])

        else:
            return f"Error: Unknown type checker '{checker}'. Use 'mypy' or 'pyright'"

        # Execute type checker
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # Type checking can be slow
            cwd=working_dir
        )

        # Format output
        output_lines = []
        output_lines.append(f"Type Checker: {checker}")
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append(f"Target: {target}")
        output_lines.append("")

        if result.returncode == 0:
            output_lines.append("✅ No type errors found")
            if result.stdout:
                # Sometimes mypy outputs success info
                output_lines.append(result.stdout.strip())
        else:
            # Process type errors
            if result.stdout:
                stdout_lines = result.stdout.strip().split('\n')

                # Count errors
                error_count = sum(1 for line in stdout_lines if 'error:' in line.lower())

                if error_count > 0:
                    output_lines.append(f"Found {error_count} type errors:")
                    output_lines.append("")

                # Truncate if too many errors
                if len(stdout_lines) > 30:
                    output_lines.extend(stdout_lines[:25])
                    output_lines.append(f"\n... [Truncated: showing first 25 of {len(stdout_lines)} lines]")
                    output_lines.append("Run with specific target_path to focus analysis")
                    output_lines.extend(stdout_lines[-5:])
                else:
                    output_lines.extend(stdout_lines)

        if result.stderr:
            output_lines.append("\nWarnings/Errors:")
            output_lines.append(result.stderr)

        output_lines.append(f"\nExit code: {result.returncode}")

        return "\n".join(output_lines)

    except FileNotFoundError:
        return f"Error: {checker} not found. Install with: pip install {checker}"
    except subprocess.TimeoutExpired:
        return f"Error: {checker} timed out after 120s. Consider using specific target_path"
    except Exception as e:
        return f"Error running {checker}: {str(e)}"


@register_tool("Format")
def execute_format(tool: types.FormatTool, working_dir: str = ".") -> str:
    """Run code formatting"""
    try:
        formatter = tool.formatter or "ruff"
        target = tool.target_path or "."

        if formatter == "ruff":
            cmd = ["ruff", "format"]

            if tool.check_only:
                cmd.append("--check")

            if tool.diff:
                cmd.append("--diff")

            cmd.append(target)

        elif formatter == "black":
            cmd = ["black"]

            if tool.check_only:
                cmd.append("--check")

            if tool.diff:
                cmd.append("--diff")

            if tool.line_length:
                cmd.extend(["--line-length", str(tool.line_length)])

            cmd.append(target)

        else:
            return f"Error: Unknown formatter '{formatter}'. Use 'ruff' or 'black'"

        # Execute formatter
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=working_dir
        )

        # Format output
        output_lines = []
        output_lines.append(f"Formatter: {formatter}")
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append(f"Target: {target}")
        output_lines.append("")

        if result.returncode == 0:
            if tool.check_only:
                output_lines.append("✅ Code is already properly formatted")
            else:
                output_lines.append("✅ Code has been formatted successfully")

            if result.stdout:
                output_lines.append("Details:")
                output_lines.append(result.stdout.strip())
        else:
            if tool.check_only:
                output_lines.append("⚠️  Code formatting issues detected:")
            else:
                output_lines.append("⚠️  Formatting completed with issues:")

            if result.stdout:
                stdout_lines = result.stdout.strip().split('\n')
                if len(stdout_lines) > 30:
                    output_lines.extend(stdout_lines[:25])
                    output_lines.append(f"\n... [Truncated: showing first 25 of {len(stdout_lines)} lines]")
                    output_lines.extend(stdout_lines[-5:])
                else:
                    output_lines.extend(stdout_lines)

        if result.stderr:
            output_lines.append("\nErrors:")
            output_lines.append(result.stderr)

        output_lines.append(f"\nExit code: {result.returncode}")

        return "\n".join(output_lines)

    except FileNotFoundError:
        return f"Error: {formatter} not found. Install with: pip install {formatter}"
    except subprocess.TimeoutExpired:
        return f"Error: {formatter} timed out"
    except Exception as e:
        return f"Error running {formatter}: {str(e)}"


@register_tool("Dependency")
def execute_dependency(tool: types.DependencyTool, working_dir: str = ".") -> str:
    """Check and manage Python dependencies"""
    try:
        check_type = tool.check_type or "imports"
        packages = tool.packages or []

        output_lines = []
        output_lines.append(f"Dependency Check: {check_type}")
        output_lines.append("")

        if check_type == "imports":
            # Check if packages can be imported
            if not packages:
                return "Error: No packages specified for import check"

            import_results = []
            for package in packages:
                try:
                    __import__(package)
                    import_results.append(f"✅ {package}: Available")
                except ImportError:
                    import_results.append(f"❌ {package}: Not available")

            output_lines.append("Import Check Results:")
            output_lines.extend(import_results)

        elif check_type == "list" or check_type == "missing":
            # List installed packages
            result = subprocess.run(
                ["pip", "list"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=working_dir
            )

            if result.returncode == 0:
                output_lines.append("Installed packages:")
                output_lines.append(result.stdout.strip())
            else:
                output_lines.append("Failed to list packages")
                output_lines.append(result.stderr.strip())

        elif check_type == "outdated":
            # Check for outdated packages
            result = subprocess.run(
                ["pip", "list", "--outdated"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=working_dir
            )

            if result.returncode == 0:
                output_lines.append("Outdated packages:")
                output_lines.append(result.stdout.strip())
            else:
                output_lines.append("Failed to check outdated packages")
                output_lines.append(result.stderr.strip())

        elif check_type == "tree":
            # Show dependency tree (simplified)
            output_lines.append("Dependency tree check not implemented yet")

        else:
            return f"Error: Unknown check_type '{check_type}'. Use 'imports', 'list', 'missing', 'outdated', or 'tree'"

        return "\n".join(output_lines)

    except Exception as e:
        return f"Error checking dependencies: {str(e)}"


@register_tool("GitDiff")
def execute_git_diff(tool: types.GitDiffTool, working_dir: str = ".") -> str:
    """View git diff information"""
    try:
        cmd = ["git", "diff"]

        # Add options based on tool parameters
        if tool.cached:
            cmd.append("--cached")

        if tool.name_only:
            cmd.append("--name-only")

        if tool.stat:
            cmd.append("--stat")

        if tool.no_color:
            cmd.append("--no-color")

        # Add file paths if specified
        if tool.paths:
            cmd.extend(tool.paths)

        # Execute git diff
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=working_dir
        )

        # Format output
        output_lines = []
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append(f"Working directory: {working_dir}")
        output_lines.append("")

        if result.returncode == 0:
            if result.stdout:
                stdout_lines = result.stdout.strip().split('\n')

                # Truncate very large diffs
                if len(stdout_lines) > 200:
                    output_lines.extend(stdout_lines[:150])
                    output_lines.append(f"\n... [Diff truncated: showing first 150 of {len(stdout_lines)} lines]")
                    output_lines.append("Use GitDiff with specific paths or --name-only for focused view")
                    output_lines.extend(stdout_lines[-20:])
                else:
                    output_lines.extend(stdout_lines)
            else:
                output_lines.append("No differences found")
        else:
            output_lines.append("❌ Git diff failed")
            if result.stderr:
                output_lines.append("Error:")
                output_lines.append(result.stderr.strip())

        output_lines.append(f"\nExit code: {result.returncode}")

        return "\n".join(output_lines)

    except FileNotFoundError:
        return "Error: git not found. Please install git"
    except subprocess.TimeoutExpired:
        return "Error: git diff timed out"
    except Exception as e:
        return f"Error running git diff: {str(e)}"