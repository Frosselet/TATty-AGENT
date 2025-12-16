"""
Artifact management tools for TATty Agent

This module contains artifact and package management tools extracted from main.py:
- ArtifactManagement: Manage and organize project artifacts in standard folders
- InstallPackages: Install Python packages using uv or pip with safety checks
"""
import subprocess
import glob
import os
from pathlib import Path

from ..baml_client import types
from .registry import register_tool


@register_tool("ArtifactManagement")
def execute_artifact_management(tool: types.ArtifactManagementTool, working_dir: str = ".") -> str:
    """Manage and organize project artifacts in standard folders"""
    try:
        # Define standard artifact folders
        artifact_folders = {
            "script": ["scripts"],
            "data": ["data"],
            "visualization": ["visualization", "plots"],  # Include legacy plots folder
            "any": ["scripts", "data", "visualization", "plots"]
        }

        output_lines = []
        output_lines.append(f"🗂️ Artifact Management: {tool.action_type}")

        if tool.folder:
            output_lines.append(f"Target folder: {tool.folder}")
        if tool.pattern:
            output_lines.append(f"Search pattern: {tool.pattern}")
        if tool.artifact_type:
            output_lines.append(f"Artifact type: {tool.artifact_type}")

        output_lines.append(f"Working directory: {working_dir}")
        output_lines.append("")

        action_type = tool.action_type.lower()

        if action_type == "list":
            # List artifacts in specified folders
            folders_to_check = []

            if tool.folder:
                folders_to_check = [tool.folder]
            elif tool.artifact_type and tool.artifact_type in artifact_folders:
                folders_to_check = artifact_folders[tool.artifact_type]
            else:
                folders_to_check = artifact_folders["any"]

            total_files = 0
            for folder in folders_to_check:
                folder_path = os.path.join(working_dir, folder)
                if os.path.exists(folder_path):
                    pattern = tool.pattern or "*"
                    search_path = os.path.join(folder_path, pattern)
                    files = glob.glob(search_path, recursive=True)

                    if files:
                        output_lines.append(f"📁 {folder}/ ({len(files)} files):")
                        for file_path in sorted(files):
                            relative_path = os.path.relpath(file_path, working_dir)
                            file_size = os.path.getsize(file_path)
                            size_str = f"({file_size:,} bytes)" if file_size < 10000 else f"({file_size//1024:,} KB)"
                            output_lines.append(f"  - {relative_path} {size_str}")
                        total_files += len(files)
                        output_lines.append("")
                    else:
                        output_lines.append(f"📁 {folder}/ (empty)")
                        output_lines.append("")
                else:
                    output_lines.append(f"📁 {folder}/ (folder does not exist)")
                    output_lines.append("")

            output_lines.append(f"📊 Summary: {total_files} total artifacts found")

        elif action_type == "find":
            # Find specific artifacts across all folders
            if not tool.pattern:
                return "❌ Error: pattern parameter required for 'find' action"

            all_matches = []
            for folder in artifact_folders["any"]:
                folder_path = os.path.join(working_dir, folder)
                if os.path.exists(folder_path):
                    search_path = os.path.join(folder_path, "**", tool.pattern)
                    matches = glob.glob(search_path, recursive=True)
                    all_matches.extend(matches)

            if all_matches:
                output_lines.append(f"🔍 Found {len(all_matches)} matches for '{tool.pattern}':")
                output_lines.append("")

                # Group by folder
                by_folder = {}
                for match in sorted(all_matches):
                    relative_path = os.path.relpath(match, working_dir)
                    folder_name = relative_path.split('/')[0]
                    if folder_name not in by_folder:
                        by_folder[folder_name] = []
                    by_folder[folder_name].append(relative_path)

                for folder_name, files in by_folder.items():
                    output_lines.append(f"📁 {folder_name}/:")
                    for file_path in files:
                        file_size = os.path.getsize(os.path.join(working_dir, file_path))
                        size_str = f"({file_size:,} bytes)" if file_size < 10000 else f"({file_size//1024:,} KB)"
                        output_lines.append(f"  - {file_path} {size_str}")
                    output_lines.append("")
            else:
                output_lines.append(f"🔍 No matches found for pattern '{tool.pattern}'")
                output_lines.append("")
                output_lines.append("💡 Tip: Try broader patterns like '*plot*', '*.py', '*.csv'")

        elif action_type == "organize":
            # Ensure all standard folders exist and provide organization tips
            created_folders = []
            for folder in artifact_folders["any"]:
                folder_path = os.path.join(working_dir, folder)
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path, exist_ok=True)
                    created_folders.append(folder)

            if created_folders:
                output_lines.append(f"✅ Created missing folders: {', '.join(created_folders)}")
                output_lines.append("")

            # Check for files in root that should be organized
            root_files = glob.glob(os.path.join(working_dir, "*"))
            root_files = [f for f in root_files if os.path.isfile(f)]

            suggestions = []
            for file_path in root_files:
                filename = os.path.basename(file_path)
                if filename.endswith(('.py', '.ipynb')) and not filename.startswith(('main.', 'tui.', 'agent_runtime.')):
                    suggestions.append(f"  mv {filename} scripts/")
                elif filename.endswith(('.csv', '.json', '.txt', '.xlsx')):
                    suggestions.append(f"  mv {filename} data/")
                elif filename.endswith(('.png', '.jpg', '.svg', '.pdf', '.html')):
                    suggestions.append(f"  mv {filename} visualization/")

            if suggestions:
                output_lines.append("💡 Organization suggestions for root directory files:")
                output_lines.extend(suggestions[:10])  # Show first 10 suggestions
                if len(suggestions) > 10:
                    output_lines.append(f"  ... and {len(suggestions) - 10} more files")
                output_lines.append("")

            output_lines.append("📋 Standard folder structure:")
            output_lines.append("  scripts/       - Python scripts, code generators, analysis tools")
            output_lines.append("  data/          - CSV files, datasets, JSON files, text data")
            output_lines.append("  visualization/ - Plots, charts, images, visual outputs")
            output_lines.append("  plots/         - Legacy plot folder")

        elif action_type == "clean":
            # Clean up empty folders and provide cleanup suggestions
            empty_folders = []
            for folder in artifact_folders["any"]:
                folder_path = os.path.join(working_dir, folder)
                if os.path.exists(folder_path) and not os.listdir(folder_path):
                    empty_folders.append(folder)

            if empty_folders:
                output_lines.append(f"🗑️ Empty folders found: {', '.join(empty_folders)}")
                output_lines.append("These folders are kept for future artifact organization")
                output_lines.append("")

            # Check for duplicate files
            output_lines.append("🔍 Checking for potential duplicates...")
            # This is a basic check - could be enhanced with content comparison
            all_files = []
            for folder in artifact_folders["any"]:
                folder_path = os.path.join(working_dir, folder)
                if os.path.exists(folder_path):
                    files = glob.glob(os.path.join(folder_path, "**/*"), recursive=True)
                    all_files.extend([f for f in files if os.path.isfile(f)])

            filenames = {}
            for file_path in all_files:
                filename = os.path.basename(file_path)
                if filename not in filenames:
                    filenames[filename] = []
                filenames[filename].append(file_path)

            duplicates = {name: paths for name, paths in filenames.items() if len(paths) > 1}
            if duplicates:
                output_lines.append(f"⚠️ Found {len(duplicates)} potential duplicate filenames:")
                for filename, paths in list(duplicates.items())[:5]:  # Show first 5
                    output_lines.append(f"  {filename}:")
                    for path in paths:
                        relative_path = os.path.relpath(path, working_dir)
                        output_lines.append(f"    - {relative_path}")
                if len(duplicates) > 5:
                    output_lines.append(f"  ... and {len(duplicates) - 5} more")
            else:
                output_lines.append("✅ No duplicate filenames found")

        else:
            return f"❌ Error: Unknown action_type '{tool.action_type}'. Use 'list', 'find', 'organize', or 'clean'"

        return "\n".join(output_lines)

    except Exception as e:
        return f"❌ Error managing artifacts: {str(e)}"


@register_tool("InstallPackages")
def execute_install_packages(tool: types.InstallPackagesTool, working_dir: str = ".") -> str:
    """Install Python packages using uv or pip with user permission"""
    try:
        # Safety check - require user confirmation
        if not tool.user_confirmed:
            return "❌ Error: Installation requires user confirmation. Set user_confirmed=true to proceed."

        packages = tool.packages
        if not packages:
            return "❌ Error: No packages specified for installation"

        # Validate Python packages only
        non_python_indicators = [
            'brew', 'homebrew', 'apt', 'yum', 'pacman',  # Package managers
            'node', 'npm', 'yarn',  # Node.js
            'docker', 'kubernetes', 'helm',  # Container tools
            'git', 'svn', 'mercurial',  # VCS (use GitPython instead)
            'redis', 'mongodb', 'postgresql',  # Databases (use Python clients)
            'nginx', 'apache', 'mysql',  # Servers
            'terraform', 'ansible',  # Infrastructure
            'ruby', 'go', 'rust', 'java',  # Other languages
        ]

        invalid_packages = []
        python_alternatives = {
            'git': 'GitPython',
            'redis': 'redis-py',
            'mongodb': 'pymongo',
            'postgresql': 'psycopg2-binary',
            'mysql': 'PyMySQL',
            'sqlite': 'sqlite3 (built-in)',
            'docker': 'docker-py',
            'kubernetes': 'kubernetes-client',
            'node': 'pynode or find Python equivalent',
            'npm': 'find Python equivalent',
        }

        for package in packages:
            package_lower = package.lower()

            # Check if package name exactly matches or starts with non-Python indicators
            # But allow Python wrappers that contain these terms (e.g., GitPython, redis-py)
            is_invalid = False
            for indicator in non_python_indicators:
                # Exact match
                if package_lower == indicator:
                    is_invalid = True
                    break
                # Package starts with indicator followed by non-letter character
                elif package_lower.startswith(indicator + "-") or package_lower.startswith(indicator + "_"):
                    # Exception: allow common Python wrapper patterns
                    python_wrapper_patterns = [
                        "redis-py", "redis_py", "docker-py", "docker_py",
                        "postgresql-py", "mysql-py"
                    ]
                    if package_lower not in python_wrapper_patterns:
                        is_invalid = True
                        break
                # Standalone tool names (but allow Python wrappers like GitPython)
                elif indicator in ["git", "node", "npm", "docker", "redis"] and package_lower == indicator:
                    is_invalid = True
                    break

            if is_invalid:
                invalid_packages.append(package)

        if invalid_packages:
            output_lines = []
            output_lines.append("❌ Error: Non-Python packages detected!")
            output_lines.append("This tool only installs Python packages from PyPI.")
            output_lines.append("")
            output_lines.append("Invalid packages:")
            for pkg in invalid_packages:
                output_lines.append(f"  - {pkg}")
                if pkg.lower() in python_alternatives:
                    output_lines.append(f"    💡 Try instead: {python_alternatives[pkg.lower()]}")

            output_lines.append("")
            output_lines.append("For system dependencies:")
            output_lines.append("1. Use WebSearch to find Python equivalents")
            output_lines.append("2. Look for Python wrappers or clients")
            output_lines.append("3. Consider pure-Python implementations")
            output_lines.append("")
            output_lines.append("Examples:")
            output_lines.append("  - git → GitPython")
            output_lines.append("  - redis → redis-py")
            output_lines.append("  - docker → docker-py")
            return "\n".join(output_lines)

        # Format output
        output_lines = []
        output_lines.append("📦 Installing packages...")
        output_lines.append(f"Packages: {', '.join(packages)}")
        output_lines.append(f"Development: {'Yes' if tool.dev else 'No'}")
        output_lines.append(f"Upgrade: {'Yes' if tool.upgrade else 'No'}")
        output_lines.append(f"Working directory: {working_dir}")
        output_lines.append("")

        # Try uv first (preferred), then fallback to pip
        uv_available = False
        pip_available = False

        # Check if uv is available
        try:
            uv_result = subprocess.run(["uv", "--version"], capture_output=True, timeout=5, cwd=working_dir)
            if uv_result.returncode == 0:
                uv_available = True
                output_lines.append("✅ Using uv (preferred package manager)")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check if pip is available if uv isn't
        if not uv_available:
            try:
                pip_result = subprocess.run(["pip", "--version"], capture_output=True, timeout=5, cwd=working_dir)
                if pip_result.returncode == 0:
                    pip_available = True
                    output_lines.append("✅ Using pip (fallback package manager)")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        if not uv_available and not pip_available:
            return "❌ Error: Neither uv nor pip are available. Please install a package manager."

        # Build installation command
        if uv_available:
            cmd = ["uv", "add"]
            if tool.dev:
                cmd.append("--dev")
            if tool.upgrade:
                cmd.append("--upgrade")
            cmd.extend(packages)
        else:
            cmd = ["pip", "install"]
            if tool.upgrade:
                cmd.append("--upgrade")
            cmd.extend(packages)

        # Execute installation
        output_lines.append(f"Command: {' '.join(cmd)}")
        output_lines.append("")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout for installs
            cwd=working_dir
        )

        if result.returncode == 0:
            output_lines.append("✅ Installation completed successfully!")
            if result.stdout.strip():
                stdout_lines = result.stdout.strip().split('\n')
                # Show relevant output (truncated for large installs)
                if len(stdout_lines) > 50:
                    output_lines.append("\nInstallation output (truncated):")
                    output_lines.extend(stdout_lines[-20:])  # Show last 20 lines
                    output_lines.append(f"... (showing last 20 of {len(stdout_lines)} lines)")
                else:
                    output_lines.append("\nInstallation output:")
                    output_lines.extend(stdout_lines)
        else:
            output_lines.append("❌ Installation failed!")
            if result.stderr:
                output_lines.append("\nError details:")
                error_lines = result.stderr.strip().split('\n')
                # Show error details (truncated for very long errors)
                if len(error_lines) > 30:
                    output_lines.extend(error_lines[:20])
                    output_lines.append(f"... (showing first 20 of {len(error_lines)} error lines)")
                else:
                    output_lines.extend(error_lines)

            # Provide helpful suggestions
            output_lines.append("\n💡 Troubleshooting suggestions:")
            if uv_available:
                output_lines.append("   - Check package names are correct")
                output_lines.append("   - Try: uv sync to refresh dependencies")
                output_lines.append("   - Try: uv lock --upgrade to update lockfile")
            else:
                output_lines.append("   - Check package names are correct")
                output_lines.append("   - Try: pip install --upgrade pip")
                output_lines.append("   - Consider using uv for better dependency management")

        return "\n".join(output_lines)

    except subprocess.TimeoutExpired:
        return "❌ Error: Package installation timed out (5 minute limit)"
    except Exception as e:
        return f"❌ Error installing packages: {str(e)}"