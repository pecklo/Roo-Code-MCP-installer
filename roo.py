#!/usr/bin/env python3

import sys
import subprocess
from importlib.util import find_spec
from importlib import metadata
from typing import List, Tuple, Dict, Optional
import os
import logging_config # Keep for file logging setup
import threading
import time
from datetime import datetime, timedelta
import shutil
import re
import json
import ctypes
import argparse
import stat
import errno
import platform
from pathlib import Path
from urllib.parse import urlparse
from collections import deque
import logging
import tomllib
from getpass import getpass # Keep for potential non-rich fallback? Or remove if Prompt handles all.
import shlex
import warnings

# Rich imports
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.logging import RichHandler # For routing logs through rich

from rich.theme import Theme

# Define colors based on SVG analysis and assumptions
# Define colors based on SVG analysis and assumptions

# Create the Rich Theme
# Create the Rich Theme
# New theme based on user specifications
roo_tui_theme = Theme({
    # Core colors based on example
    "default": "grey93",           # Off-white/light grey main text
    "text": "grey93",              # Off-white/light grey main text
    "background": "black",         # Very dark/black background

    # Status & diagnostics & Symbols
    "error": "red",                # Red for errors, error symbol (✗, !)
    "warning": "yellow",           # Yellow for warnings, warning symbol (?)
    "info": "cyan",                # Cyan for info prompts/messages
    "success": "green",            # Green for success symbol (✓)
    "notice": "red",               # Style for the red notice symbol (*) - same as error

    # Prompt UI
    "prompt": "cyan",              # Prompt text color (e.g., "Enter value for...")
    "prompt.default": "yellow",    # Default value highlight in prompts (if any)
    "prompt.choices": "cyan",      # Choices in prompts (y/n)

    # Panel and table elements (using box drawing chars, default color)
    "panel.border": "grey93",      # Default text color for borders
    "table.header": "bold grey93", # Bold default text color header
    "table.cell": "grey93",        # Default text color cell text
    "table.border": "grey93",      # Default text color border for tables
    "box": "grey93",               # General box color for borders

    # Syntax Highlighting (Basic TUI focus)
    "string": "yellow",            # Used for user input highlights
    "number": "magenta",
    "keyword": "blue",
    "operator": "grey93",
    "comment": "italic grey50",
    "function": "bright_cyan",
    "variable": "cyan",            # Cyan for variable names in prompts/tables (matches prompt color)
    "constant": "magenta",
    "class": "underline bright_cyan",
    "type": "bright_cyan",
    "parameter": "italic grey70",

    # Rich component-specific
    "highlight": "yellow on black", # Highlight user input or selections (yellow text on black bg)
    "repr.str": "yellow",
    "repr.bool_true": "bold green",
    "repr.bool_false": "bold red",
    "repr.none": "dim grey93",
    "repr.url": "underline cyan",
    "repr.uuid": "bright_blue",
    "repr.ipv4": "yellow",
    "repr.ipv6": "yellow",
    "repr.mac": "yellow",

    # Custom invalid marker
    "invalid": "bold red on default", # Red on default background
    "invalid.deprecated": "bold magenta on default",

    # Specific symbols (can be overridden in print calls too)
    # These might not be strictly necessary if using styles like [success]✓[/success]
    "symbol.success": "green",
    "symbol.error": "red",
    "symbol.notice": "red",
    "symbol.prompt": "cyan", # For prompt symbols like '?' or '>'
})

# --- Initialize Rich Console ---
# Use stderr to avoid interfering with potential stdout redirection or JSON output
console = Console(stderr=True, highlight=False, theme=roo_tui_theme) # Apply the NEW theme here, highlight=False to avoid issues with brackets in messages

# --- Suppress DeprecationWarning ---
# Capture the specific DeprecationWarning and log it instead of printing
warnings.filterwarnings("always", category=DeprecationWarning, module='roo') # Adjust module if needed
original_showwarning = warnings.showwarning

def _log_warning(message, category, filename, lineno, file=None, line=None):
   if category == DeprecationWarning and 'datetime.utcnow()' in str(message):
       log_event(f"DeprecationWarning captured: {message} at {filename}:{lineno}", level='warning')
   else:
       # Call the original handler for other warnings
       original_showwarning(message, category, filename, lineno, file, line)

warnings.showwarning = _log_warning
# --- End Suppress DeprecationWarning ---


# --- Configuration File Handling ---
# (Keep existing logic, logging uses log_event)
def get_settings_path(scope: str) -> Path:
    """Gets the path to the MCP settings file based on scope."""
    if scope == "global":
        if os.name == 'nt':
            settings_path = Path(os.getenv('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json'
        else:
            settings_path = Path.home() / '.config' / 'Code' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json'
            if not settings_path.parent.exists():
                 settings_path = Path.home() / '.vscode-server' / 'data' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json'

        if not settings_path.parent.exists():
             settings_path = Path.home() / '.roo' / 'mcp_settings.json'

    else: # project scope
        settings_path = Path.cwd() / '.roo' / 'mcp.json'

    log_event(f"Determined settings path ({scope}): {settings_path}", level='debug')
    settings_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
    return settings_path

def read_settings(settings_path: Path) -> Dict:
    """Reads the JSON settings file, ensuring the mcpServers object structure."""
    default_config = {"mcpServers": {}}
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                content = f.read()
                if not content.strip(): # Handle empty file
                    log_event(f"Settings file {settings_path} is empty. Returning default config.", level='debug')
                    return default_config
                data = json.loads(content)

                if not isinstance(data, dict):
                    log_event(f"Settings file {settings_path} does not contain a JSON object. Returning default config.", level='warning')
                    return default_config

                if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
                    log_event(f"'mcpServers' key missing or not an object in {settings_path}. Initializing.", level='warning')
                    data["mcpServers"] = {}

                if "servers" in data:
                     log_event(f"Found legacy 'servers' list in {settings_path}. It will be ignored.", level='info')

                return data
        except json.JSONDecodeError as e:
            log_event(f"Error decoding JSON from settings file {settings_path}: {e}. Returning default config.", level='error')
            return default_config
        except Exception as e:
            log_event(f"Unexpected error reading settings file {settings_path}: {e}. Returning default config.", level='error')
            return default_config
    log_event(f"Settings file {settings_path} not found. Returning default config.", level='debug')
    return default_config

def write_settings(settings_path: Path, settings_data: Dict):
    """Writes the JSON settings file."""
    try:
        with open(settings_path, 'w') as f:
            json.dump(settings_data, f, indent=2)
        log_event(f"Successfully wrote settings to {settings_path}", level='debug')
    except Exception as e:
        log_event(f"Error writing settings file {settings_path}: {e}", level='error')
        raise # Re-raise the exception to indicate failure

def detect_run_command(mcp_dir: Path) -> Optional[List[str]]:
    """Attempts to detect the command to run the MCP server (Node, Python, Go)."""
    log_event(f"Attempting to detect run command in {mcp_dir}", level='debug')

    # Node.js check
    package_json_path = mcp_dir / 'package.json'
    if package_json_path.exists():
        log_event("Found package.json", level='debug')
        try:
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
                if 'scripts' in package_data and 'start' in package_data['scripts']:
                    log_event("Found 'start' script in package.json", level='debug')
                    # return ['npm', 'run', 'start'] # Requires npm check
                if 'bin' in package_data and isinstance(package_data['bin'], dict):
                    log_event(f"Found 'bin' field in package.json: {package_data['bin']}", level='debug')
                    for bin_name, script_rel_path in package_data['bin'].items():
                        script_abs_path = mcp_dir / script_rel_path
                        if script_abs_path.exists():
                            log_event(f"Using 'bin' script '{bin_name}': {script_rel_path}", level='debug')
                            return ['node', script_rel_path, 'stdio']
                        else:
                            log_event(f"'bin' script '{script_rel_path}' not found.", level='warning')

                if 'main' in package_data:
                    main_script_rel_path = package_data['main']
                    main_script_abs_path = mcp_dir / main_script_rel_path
                    if main_script_abs_path.exists():
                        log_event(f"Using 'main' field from package.json: {main_script_rel_path}", level='debug')
                        return ['node', main_script_rel_path, 'stdio']
                    else:
                         log_event(f"'main' script '{main_script_rel_path}' not found.", level='warning')

                common_node_files = ['dist/index.js', 'index.js', 'src/index.js', 'server.js']
                for file_rel_path in common_node_files:
                    script_abs_path = mcp_dir / file_rel_path
                    if script_abs_path.exists():
                        log_event(f"Found common Node.js file: {file_rel_path}", level='debug')
                        return ['node', file_rel_path, 'stdio']

        except Exception as e:
            log_event(f"Error reading or parsing package.json: {e}", level='warning')

    # Python check
    common_python_files = ['main.py', 'app.py', 'server.py', 'run.py']
    for file in common_python_files:
        script_path = mcp_dir / file
        if script_path.exists():
            log_event(f"Found common Python file: {file}", level='debug')
            python_exe = shutil.which('python3') or shutil.which('python')
            if python_exe:
                 return [python_exe, file, 'stdio']
            else:
                 log_event("Could not find python or python3 executable.", level='warning')
                 return None

    # Go check
    go_mod_path = mcp_dir / 'go.mod'
    main_go_path = mcp_dir / 'main.go'
    if go_mod_path.exists():
        log_event("Found go.mod", level='debug')
        if check_command_exists('go'):
            log_event("Using 'go run .' as the command for Go project.", level='debug')
            return ['go', 'run', '.', 'stdio']
        else:
            log_event("Go project detected, but 'go' command not found.", level='warning')
            return None
    elif main_go_path.exists():
        log_event("Found main.go (no go.mod)", level='debug')
        if check_command_exists('go'):
            log_event("Using 'go run main.go' as the command.", level='debug')
            return ['go', 'run', 'main.go', 'stdio']
        else:
            log_event("Go project detected (main.go), but 'go' command not found.", level='warning')
            return None

    # Cargo check (Basic)
    cargo_toml_path = mcp_dir / 'Cargo.toml'
    if cargo_toml_path.exists():
        log_event("Found Cargo.toml", level='debug')
        if check_command_exists('cargo'):
            log_event("Detected Rust project, add 'cargo run -- stdio' as placeholder.", level='info')
            return ['cargo', 'run', '--', 'stdio'] # Placeholder
        else:
            log_event("Cargo project detected, but 'cargo' command not found.", level='warning')


    log_event("Could not automatically detect a run command for Node, Python, or Go.", level='warning')
    return None

# --- End Configuration File Handling ---


# Check for debug flag before configuring logging
# This sets the initial state based on argv BEFORE argparse runs
debug_mode = '--debug' in sys.argv
logging_config.configure_logging(debug=debug_mode)
log_event = logging_config.log_event

# --- Configure Rich Logging Handler ---
# Remove standard console handlers first to avoid duplicate messages
root_logger = logging.getLogger()
console_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler) and h.stream in (sys.stdout, sys.stderr)]
for handler in console_handlers:
   log_event(f"Removing standard console log handler: {handler}", level='debug')
   root_logger.removeHandler(handler)

# Add RichHandler - show only WARNING and above on console by default
# Use console=console to ensure it writes to stderr like other rich output
rich_log_level = logging.DEBUG if debug_mode else logging.WARNING
rich_handler = RichHandler(
    level=rich_log_level,
    console=console,
    show_time=False, # Keep logs concise
    show_path=False,
    markup=True # Enable markup in log messages if needed
)
root_logger.addHandler(rich_handler)
log_event(f"Added RichHandler with level {logging.getLevelName(rich_log_level)}", level='debug')
# --- End Rich Logging Handler ---


# Log initial debug status
if debug_mode:
    log_event("Debug mode enabled initially", level='debug')

def check_command_exists(cmd: str) -> bool:
    """Check if a command exists in the system path"""
    if os.name == 'nt':  # Windows
        cmd_path = shutil.which(cmd + '.exe') or shutil.which(cmd + '.cmd') or shutil.which(cmd + '.bat') or shutil.which(cmd)
    else:
        cmd_path = shutil.which(cmd)
    log_event(f"Checking command availability: {cmd} -> {'Found' if cmd_path else 'Not found'}", level='debug')
    return bool(cmd_path)

class ProjectSetup:
    """Handles project type detection and setup configuration"""

    PACKAGE_MANAGERS = {
        'npm': {
            'detect_file': 'package.json',
            'command': 'npm install',
            'alternatives': [
                {'command': 'yarn install', 'detect_cmd': 'yarn'},
                {'command': 'pnpm install', 'detect_cmd': 'pnpm'}
            ]
        },
        'pip': {
            'detect_file': 'requirements.txt',
            'command': 'pip install -r requirements.txt',
            'alternatives': [
                {'command': 'pip3 install -r requirements.txt', 'detect_cmd': 'pip3'},
            ]
        },
        'poetry': {
            'detect_file': 'pyproject.toml',
            'command': 'poetry install',
            'alternatives': [
                {'command': 'pip install -e .', 'detect_cmd': 'pip'}
            ]
        },
        'cargo': {
            'detect_file': 'Cargo.toml',
            'command': 'cargo build',
            'alternatives': []
        },
         'go': { # Add Go detection
            'detect_file': 'go.mod',
            'command': 'go mod download', # Command to download dependencies
            'alternatives': []
        }
    }

    @staticmethod
    def detect_project_type(repo_dir: Path) -> Optional[Dict]:
        """
        Detect project type and return appropriate setup configuration.
        Returns dict with setup command and any additional configuration, or None if no known project type detected.
        """
        log_event(f"Detecting project type in: {repo_dir}")

        for pm_name, config in ProjectSetup.PACKAGE_MANAGERS.items():
            detect_file = repo_dir / config['detect_file']

            if detect_file.exists():
                log_event(f"Found {config['detect_file']} - detected {pm_name} project", level='debug')

                primary_cmd = config['command'].split()[0]
                if check_command_exists(primary_cmd):
                    log_event(f"Primary package manager {primary_cmd} is available", level='debug')
                    return {
                        'type': pm_name,
                        'command': config['command'],
                        'detect_file': str(detect_file)
                    }

                log_event(f"Primary package manager {primary_cmd} not found, checking alternatives", level='debug')
                for alt in config['alternatives']:
                    if check_command_exists(alt['detect_cmd']):
                        log_event(f"Found alternative package manager: {alt['detect_cmd']}", level='debug')
                        return {
                            'type': pm_name,
                            'command': alt['command'],
                            'detect_file': str(detect_file),
                            'using_alternative': True
                        }

                log_event(f"No viable package manager found for {pm_name} project", level='warning')
                return {
                    'type': pm_name,
                    'error': f"Required package manager {pm_name} not found. Please install {primary_cmd} or one of: " +
                            ', '.join(alt['detect_cmd'] for alt in config['alternatives'])
                }

        log_event("No known project type detected", level='debug')
        return None

def handle_remove_readonly(func, path, exc):
    """Handle permission error by changing file attributes."""
    excvalue = exc[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
        func(path)
    else:
        raise

# Refactored helper function
def check_and_install_tool(tool_name: str, debug: bool = False) -> bool:
    """Checks if a tool exists, prompts to install if missing using Rich, and returns success status."""
    # Use the global debug_mode state for logging within this function if debug arg isn't explicitly passed differently
    current_debug_mode = debug if debug is not None else debug_mode
    log_event(f"Checking for tool: {tool_name}", level='debug')
    tool_path = shutil.which(tool_name)

    if not tool_path and os.name == 'nt':
        tool_path = shutil.which(f"{tool_name}.cmd") or shutil.which(f"{tool_name}.exe")

    if tool_path:
        log_event(f"Tool '{tool_name}' found at: {tool_path}", level='debug')
        return True

    log_event(f"Required tool '{tool_name}' not found in PATH.", level='warning')

    install_cmd_str = None
    INSTALL_COMMANDS = {
        'bun': 'npm install -g bun',
        'npm': 'npm install -g npm',
        'tsc': 'npm install -g typescript',
        'webpack': 'npm install -g webpack webpack-cli',
        'git': None, # Cannot install git easily/reliably cross-platform
        # Add more tools here
    }

    if tool_name.lower() in INSTALL_COMMANDS:
        install_cmd_str = INSTALL_COMMANDS[tool_name.lower()]

        if install_cmd_str is None: # Handle tools we know but can't auto-install
             console.print(f"[red]![/red] [default]Required tool '{tool_name}' is missing.[/default]")
             console.print(f"   [default]Automatic installation is not supported for '{tool_name}'.[/default]")
             console.print(f"   [bold red]Please install it manually and ensure it's in your PATH.[/bold red]")
             log_event(f"Automatic installation not supported for '{tool_name}'.", level='warning')
             return False

        console.print(f"[yellow]?[/yellow] [default]Required tool '{tool_name}' seems to be missing.[/default]")
        try:
            # Use Rich Confirm for y/n questions - matches example style
            confirm = Confirm.ask(f"[prompt]Attempt to install it globally using '[cyan]{install_cmd_str}[/cyan]'?[/prompt]", default=False)
            log_event(f"User prompt for installing '{tool_name}': {'Yes' if confirm else 'No'}", level='info')
        except Exception as e: # Catch potential issues with Confirm in non-interactive
            log_event(f"Error during Confirm.ask for '{tool_name}': {e}. Assuming 'No'.", level='warning')
            console.print("[yellow]![/yellow] [default]Skipping installation (assuming non-interactive environment or error).[/default]")
            confirm = False


        if confirm:
            console.print(f"  [cyan]>[/cyan] [default]Attempting installation: [cyan]{install_cmd_str}[/cyan][/default]") # Use cyan prompt symbol
            log_event(f"Executing installation command: {install_cmd_str}", level='info')
            try:
                cmd_to_run = install_cmd_str
                if os.name == 'nt' and cmd_to_run.startswith('npm '):
                     npm_path = shutil.which('npm.cmd') or shutil.which('npm.exe') or shutil.which('npm')
                     if npm_path:
                         parts = shlex.split(cmd_to_run)
                         parts[0] = npm_path
                         cmd_to_run = parts
                     else:
                          log_event("npm command not found for global install on Windows.", level='warning')
                          console.print(f"  [red]![/red] [default]Error: 'npm' command not found. Cannot run installation.[/default]")
                          return False # Cannot proceed if npm is missing

                # Use Rich Progress for the command execution
                with Progress(
                    SpinnerColumn(spinner_name="dots", style="default"), # Match example spinner
                    TextColumn("[default]{task.description}[/default]"), # Use theme default color
                    TimeElapsedColumn(),
                    console=console,
                    transient=True # Clear progress on completion
                ) as progress:
                    task_id = progress.add_task(f"Installing {tool_name}...", total=None) # Indeterminate

                    install_result = subprocess.run(
                        cmd_to_run,
                        shell=isinstance(cmd_to_run, str),
                        check=False, # Check manually below
                        capture_output=True,
                        text=True,
                        env=os.environ.copy()
                    )
                    progress.update(task_id, completed=True) # Mark as completed visually

                log_event(f"Installation command stdout:\n{install_result.stdout}", level='debug')
                if install_result.stderr:
                    log_event(f"Installation command stderr:\n{install_result.stderr}", level='debug')

                if install_result.returncode != 0:
                     raise subprocess.CalledProcessError(install_result.returncode, cmd_to_run, output=install_result.stdout, stderr=install_result.stderr)

                # Indent success message (Green check, default text)
                console.print(f"  [green]✓[/green] [default]Installation command finished.[/default]")
                # Re-check if the tool is now available
                tool_path_after_install = shutil.which(tool_name)
                if not tool_path_after_install and os.name == 'nt':
                     tool_path_after_install = shutil.which(f"{tool_name}.cmd") or shutil.which(f"{tool_name}.exe")

                if not tool_path_after_install:
                    log_event(f"Installation command ran, but '{tool_name}' still not found in PATH.", level='error')
                    # Indent error (Red !, default text)
                    console.print(f"  [red]![/red] [default]Installation command ran, but '{tool_name}' still not found.[/default]")
                    console.print(f"    [default]Please check the output and install manually.[/default]")
                    return False
                else:
                    log_event(f"Successfully installed '{tool_name}'. Path: {tool_path_after_install}", level='info')
                    # Indent success (Green check, default text)
                    console.print(f"  [green]✓[/green] [default]'{tool_name}' seems to be installed now.[/default]")
                    return True # Installation successful

            except subprocess.CalledProcessError as install_err:
                log_event(f"Installation command failed. Return code: {install_err.returncode}", level='error')
                log_event(f"Installation stdout:\n{install_err.stdout}", level='error')
                log_event(f"Installation stderr:\n{install_err.stderr}", level='error')
                # Indent error (Red !, default text)
                console.print(f"  [red]![/red] [default]Installation failed.[/default]")
                error_output = install_err.stderr.strip() if install_err.stderr else install_err.stdout.strip()
                if error_output:
                    console.print(f"    [red]Error:[/red] {error_output}") # Keep error details red
                console.print(f"  [default]Please install '{tool_name}' manually and ensure it's in your PATH.[/default]")
                return False # Installation failed
            except Exception as install_e:
                log_event(f"Unexpected error during installation attempt: {install_e}", level='error')
                # Indent error (Red !, default text)
                console.print(f"  [red]![/red] [default]An unexpected error occurred during installation: {install_e}[/default]")
                console.print(f"  [default]Please install '{tool_name}' manually and ensure it's in your PATH.[/default]")
                return False # Installation failed
        else:
            log_event(f"User declined installation of '{tool_name}'.", level='info')
            # Indent messages (Default text)
            console.print(f"  [default]Skipping installation of '{tool_name}'.[/default]")
            console.print(f"  [red]![/red] [default]Error: Required tool '{tool_name}' is missing and installation was skipped.[/default]")
            return False # User skipped install
    else:
        log_event(f"Automatic installation not supported for '{tool_name}'.", level='warning')
        # Indent messages (Yellow !, default text)
        console.print(f"  [yellow]![/yellow] [default]Automatic installation not supported for '{tool_name}'.[/default]")
        console.print(f"  [red]![/red] [default]Error: Required tool '{tool_name}' is missing. Please install it manually and ensure it's in your PATH.[/default]")
        return False # Cannot install automatically


# Refactored run_command (incorporates check_and_install_tool)
def run_command(cmd, cwd=None, debug=None, use_progress=False, progress_description=None):
    """
    Run a command using Rich for progress/output, handle missing tools via check_and_install_tool.
    Returns the subprocess result object. Raises exceptions on failure.
    """
    # Use the global debug_mode state if debug arg isn't explicitly passed
    current_debug_mode = debug if debug is not None else debug_mode
    cmd_list: List[str] = []
    executable: Optional[str] = None
    cmd_str: str = ""

    try:
        if isinstance(cmd, str):
            cmd_list = shlex.split(cmd)
            cmd_str = cmd
        elif isinstance(cmd, list) and cmd:
            cmd_list = cmd
            cmd_str = ' '.join(shlex.quote(str(c)) for c in cmd)
        else:
            raise ValueError("Invalid command format. Must be string or list.")

        if not cmd_list:
             raise ValueError("Command cannot be empty.")

        executable = cmd_list[0]
        log_event(f"Attempting to execute command: {cmd_str} in directory: {cwd or 'current'}", level='debug')

        # --- Check for executable using the helper ---
        # Pass the determined debug mode state
        if not check_and_install_tool(executable, debug=current_debug_mode):
            # Error message already printed by check_and_install_tool
            raise FileNotFoundError(f"Required tool '{executable}' not found or installation failed/skipped.")
        # --- End Check/Install ---

        # If we reach here, the tool should exist. Proceed with execution.
        log_event(f"Executing verified command: {cmd_str}", level='debug')

        resolved_cmd_list = list(cmd_list)
        if os.name == 'nt' and executable.lower() in ['npm', 'yarn', 'pnpm', 'node']: # Added node
             # Use shutil.which again AFTER potential install by check_and_install_tool
             resolved_path = shutil.which(f"{executable}.cmd") or shutil.which(f"{executable}.exe") or shutil.which(executable)
             if resolved_path:
                 resolved_cmd_list[0] = resolved_path
                 log_event(f"Resolved Windows command path: {resolved_path}", level='debug')
             else:
                 # This case should ideally not happen if check_and_install_tool succeeded
                 log_event(f"Command '{executable}' was confirmed but not found by shutil.which after install check.", level='error')
                 raise FileNotFoundError(f"Internal error: Command '{executable}' verification inconsistency.")

        # --- Execute with Rich Progress ---
        result = None
        description = progress_description or f"Running: {shlex.quote(executable)}..."

        if use_progress:
            with Progress(
                SpinnerColumn(spinner_name="dots", style="default"), # Match example spinner
                TextColumn("[default]{task.description}[/default]"), # Use theme default color
                TimeElapsedColumn(),
                console=console,
                transient=True # Usually transient for single commands
            ) as progress:
                task_id = progress.add_task(description, total=None)
                try:
                    result = subprocess.run(
                        resolved_cmd_list,
                        cwd=cwd,
                        capture_output=True, # Capture stdout/stderr
                        text=True,
                        shell=False,
                        check=False, # Check manually
                        env=os.environ.copy()
                    )
                finally:
                     # Ensure progress stops even if subprocess errors out
                     progress.update(task_id, completed=True)
        else:
             # Execute without progress bar but still capture output
             result = subprocess.run(
                 resolved_cmd_list,
                 cwd=cwd,
                 capture_output=True,
                 text=True,
                 shell=False,
                 check=False,
                 env=os.environ.copy()
             )

        # --- Process Result ---
        if result.stdout:
             log_event(f"Command stdout:\n{result.stdout}", level='debug')
        if result.stderr:
            log_event(f"Command stderr:\n{result.stderr}",
                     level='warning' if result.returncode != 0 else 'debug')

        if result.returncode != 0:
            # Raise CalledProcessError for consistency with check=True behavior
            raise subprocess.CalledProcessError(
                result.returncode, resolved_cmd_list, output=result.stdout, stderr=result.stderr
            )

        return result # Return the completed process object on success

    except FileNotFoundError as fnf_error:
        # This catches errors from check_and_install_tool failing
        error_msg = f"Command execution failed: {str(fnf_error)}"
        log_event(error_msg, level='error')
        # User-friendly message printed by check_and_install_tool
        raise # Re-raise the specific error

    except subprocess.CalledProcessError as cpe:
        # Logged by caller or handled specifically there
        log_event(f"Command '{cmd_str}' failed with exit code {cpe.returncode}", level='error')
        # Don't print here, let the caller (install_mcp) handle user message
        raise # Re-raise

    except Exception as e:
        error_msg = f"Command execution failed unexpectedly: {str(e)}"
        log_event(error_msg, level='error')
        if current_debug_mode: # Use the determined debug mode
            import traceback
            tb = traceback.format_exc()
            log_event(f"Stack trace:\n{tb}", level='debug')
        # Print a generic error message using Rich Console
        console.print(f"[red][red]![/red] An unexpected error occurred while trying to run the command:[/red] {e}")
        raise # Re-raise other unexpected errors


def safe_remove_directory(path, debug=None):
    """Safely remove a directory and its contents."""
    current_debug_mode = debug if debug is not None else debug_mode
    try:
        if path.exists():
            log_event(f"Removing directory: {path}", level='debug' if current_debug_mode else 'info')
            # No direct Rich UI needed here, it's a background task
            shutil.rmtree(path, onerror=handle_remove_readonly)
    except Exception as e:
        log_event(f"Error removing directory {path}: {e}", level='error')
        console.print(f"[yellow]![/yellow] [default]Warning: Could not completely remove previous directory {path}: {e}[/default]")


def get_install_dir(scope, repo_name):
    """Determine installation directory based on scope."""
    if scope == "global":
        base_dir = Path.home() / ".roo" / "mcps"
    else:  # project scope
        base_dir = Path.cwd() / ".roo" / "mcps"

    return base_dir / repo_name

def parse_repo_input(repo_input):
    """
    Parses GitHub repository input (URL or slug like 'user/repo')
    and an optional subdirectory separated by a colon (':').
    Returns the normalized Git URL, the inferred repository name, and the subdirectory string.
    """
    log_event(f"Parsing repository input: {repo_input}", level='debug')

    repo_input = repo_input.strip()
    if not repo_input:
        error_msg = "Repository input cannot be empty"
        log_event(error_msg, level='error')
        raise ValueError(error_msg)

    repo_part = repo_input
    subdir = ""

    # Split repository and subdirectory on colon if present
    # Ensure it's not part of the protocol (http://...)
    # Basic check: colon exists and is not immediately after 'http' or 'https'
    colon_index = repo_input.find(':')
    if colon_index > 0 and repo_input[colon_index-1] != 'p' and repo_input[colon_index-1] != 's':
        log_event(f"Found colon separator in non-URL input", level='debug')
        parts = repo_input.split(":", 1)
        repo_part, subdir = parts
        log_event(f"Detected subdirectory specification - repo: '{repo_part}', subdir: '{subdir}'", level='debug')

    # Handle HTTP/HTTPS URLs
    if repo_part.startswith(("http://", "https://")):
        log_event(f"Processing URL format repository: {repo_part}", level='debug')
        try:
            # Use the original repo_input for URL parsing if subdir wasn't split off yet
            url_to_parse = repo_input if not subdir else repo_part
            parsed = urlparse(url_to_parse)
            log_event(f"URL parsing result - scheme: {parsed.scheme}, netloc: {parsed.netloc}, path: {parsed.path}", level='debug')

            if parsed.netloc == 'github.com':
                path_parts = parsed.path.strip('/').split('/')
                if len(path_parts) >= 2:
                    owner = path_parts[0] # First part is owner
                    repo = path_parts[1].replace('.git', '') # Second part is repo
                    log_event(f"Extracted owner: {owner}, repo: {repo} from URL path", level='debug')
                    git_url = f"https://github.com/{owner}/{repo}.git"
                    repo_name = repo
                    log_event(f"Successfully parsed GitHub URL - user: {owner}, repo: {repo_name}", level='debug')
                    return git_url, repo_name, subdir
                else:
                    error_msg = "Invalid GitHub URL path structure (expected owner/repo)"
                    log_event(error_msg, level='error')
                    raise ValueError(error_msg)
            else:
                # Allow other git hosts, infer repo name from last path component
                path_parts = parsed.path.strip('/').split('/')
                if path_parts:
                    repo_name = path_parts[-1].replace('.git', '')
                    git_url = url_to_parse # Assume the full URL is the git URL
                    log_event(f"Parsed non-GitHub URL - host: {parsed.netloc}, repo: {repo_name}", level='debug')
                    return git_url, repo_name, subdir
                else:
                    error_msg = f"Invalid Git URL - cannot determine repository name from path: {parsed.path}"
                    log_event(error_msg, level='error')
                    raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Invalid Git URL: {e}"
            log_event(error_msg, level='error')
            raise ValueError(error_msg)

    # Handle username/repo format (or just repo name for default owner?)
    elif '/' in repo_part:
        log_event(f"Processing owner/repo format: {repo_part}", level='debug')
        try:
            owner, repo = repo_part.split('/', 1)
            owner = owner.strip()
            repo = repo.strip().replace('.git', '')
            log_event(f"Split repo_part into owner: '{owner}', repo: '{repo}'", level='debug')

            if owner and repo:
                git_url = f"https://github.com/{owner}/{repo}.git"
                log_event(f"Successfully parsed owner/repo format - owner: {owner}, repo: {repo}", level='debug')
                return git_url, repo, subdir
            else:
                error_msg = "Invalid owner/repo format - empty owner or repo name"
                log_event(error_msg, level='error')
                raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Failed to parse owner/repo format: {str(e)}"
            log_event(error_msg, level='error')
            raise ValueError(error_msg)

    # Fallback: Assume it's just a repo name, default to a predefined owner if desired, or raise error
    # For now, raise error if format is unclear
    error_msg = "Invalid repository input format - must be URL (https://...) or owner/repo"
    log_event(error_msg, level='error')
    raise ValueError(error_msg)


def list_installed():
    """List all installed MCPs using Rich."""
    try:
        global_dir = Path.home() / ".roo" / "mcps"
        project_dir = Path.cwd() / ".roo" / "mcps"

        mcps_found = False
        output = []

        if global_dir.exists():
            output.append("\n[bold cyan]Global MCPs:[/bold cyan]")
            count = 0
            for mcp_path in global_dir.iterdir():
                if mcp_path.is_dir():
                    output.append(f"  • [green]{mcp_path.name}[/green] ([dim]{mcp_path}[/dim])")
                    count += 1
            if count == 0:
                 output.append("  [dim]None found.[/dim]")
            mcps_found = mcps_found or (count > 0)


        if project_dir.exists():
            output.append("\n[bold cyan]Project MCPs:[/bold cyan] ([dim]in current directory[/dim])")
            count = 0
            for mcp_path in project_dir.iterdir():
                if mcp_path.is_dir():
                    output.append(f"  • [green]{mcp_path.name}[/green] ([dim]{mcp_path}[/dim])")
                    count += 1
            if count == 0:
                 output.append("  [dim]None found.[/dim]")
            mcps_found = mcps_found or (count > 0)


        if not mcps_found:
            console.print("[yellow]No MCPs installed in global or project scope.[/yellow]")
        else:
            console.print("\n".join(output)) # Output already contains styled strings


        return True

    except Exception as e:
        log_event(f"Failed to list installed MCPs: {e}", level='error')
        console.print(f"[red]Error listing installed MCPs:[/red] {e}")
        return False

def show_logs(follow=False, lines=None):
    """Show Roo logs using Rich."""
    try:
        log_dir = Path.home() / ".roo" / "logs"
        if not log_dir.exists():
            console.print("[yellow]Log directory not found.[/yellow]")
            return True # Not an error, just no logs

        log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not log_files:
            console.print("[yellow]No log files found.[/yellow]")
            return True

        current_log = log_files[0]
        console.print(f"[orange]Displaying logs from: [cyan]{current_log}[/cyan][/orange]")

        if follow:
            console.print("[dim](Press Ctrl+C to stop following)[/dim]")
            try:
                with current_log.open() as f:
                    # Go to the end of the file initially
                    if lines: # If lines specified, show tail first
                         log_lines = deque(f, lines)
                         console.print(''.join(log_lines), end='')
                    else: # Otherwise, just go to end
                         f.seek(0, 2)

                    # Start following
                    while True:
                        line = f.readline()
                        if line:
                            console.print(line, end='')
                        else:
                            time.sleep(0.1)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped following logs.[/yellow]")
                return True
        else:
            with current_log.open() as f:
                if lines:
                    log_lines = deque(f, lines)
                    console.print(''.join(log_lines), end='')
                else:
                    # Read whole file - consider using Syntax for large files?
                    # For simplicity, keep direct print for now.
                    console.print(f.read(), end='')

        return True

    except Exception as e:
        log_event(f"Failed to show logs: {e}", level='error')
        console.print(f"[red]Error showing logs:[/red] {e}")
        return False

def parse_env_example(file_path: Path) -> List[str]:
    """Parses a .env.example file to extract variable names."""
    variables = []
    log_event(f"Parsing .env.example file: {file_path}", level='debug')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    match = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=", line)
                    if match:
                        var_name = match.group(1)
                        variables.append(var_name)
                        log_event(f"Found potential env var: {var_name}", level='debug')
    except Exception as e:
        log_event(f"Error reading or parsing {file_path}: {e}", level='warning')
    return variables


JSON_CODE_BLOCK_RE = re.compile(r"```json\s*([\s\S]*?)\s*```", re.MULTILINE)

def _find_env_keys_recursive(data, found_keys):
    """Recursively search for 'env' dictionaries and add their keys."""
    if isinstance(data, dict):
        if 'env' in data and isinstance(data['env'], dict):
            env_keys = data['env'].keys()
            log_event(f"Found nested 'env' block with keys: {list(env_keys)}", level='debug')
            valid_keys = {key for key in env_keys if isinstance(key, str)}
            found_keys.update(valid_keys)
            # Don't stop here, continue searching deeper in case of multiple env blocks
        for key, value in data.items():
            _find_env_keys_recursive(value, found_keys)
    elif isinstance(data, list):
        for item in data:
            _find_env_keys_recursive(item, found_keys)


def parse_readme_for_env_vars(readme_path: Path) -> List[str]:
    """Parses a README file for JSON code blocks containing 'env' keys (recursively)."""
    variables = set()
    log_event(f"Parsing README file for env vars: {readme_path}", level='debug')
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()

        matches = JSON_CODE_BLOCK_RE.findall(content)
        log_event(f"Found {len(matches)} potential JSON code blocks in README.", level='debug')

        for block_content in matches:
            try:
                clean_block_content = block_content.strip()
                if not clean_block_content:
                    continue

                json_data = json.loads(clean_block_content)
                _find_env_keys_recursive(json_data, variables) # Use recursive helper

            except json.JSONDecodeError:
                log_event(f"Could not parse a JSON code block in README: {block_content[:100]}...", level='debug')
            except Exception as e:
                log_event(f"Error processing JSON block from README: {e}", level='warning')

    except FileNotFoundError:
        log_event(f"README file not found at {readme_path}", level='debug')
        return []
    except Exception as e:
        log_event(f"Error reading or parsing README {readme_path}: {e}", level='warning')

    found_vars = sorted(list(variables))
    log_event(f"Extracted env vars from README: {found_vars}", level='debug')
    return found_vars


# --- Main Installation Logic (Refactored with Rich) ---
def install_mcp(repo_input, scope="global", debug=None, skip_env_config=False, demo_mode=False):
    """Install or update an MCP server using Rich UI."""
    # Use the global debug_mode state if debug arg isn't explicitly passed
    current_debug_mode = debug if debug is not None else debug_mode
    if demo_mode:
        console.print("[bold yellow]*** DEMO MODE ACTIVE ***[/bold yellow]")
        log_event("Running install_mcp in DEMO mode.", level='warning')
    log_event("=== Starting MCP Installation ===", level='info')
    repo_name = "unknown" # Initialize for error messages

    try:
        # --- 1. Parse Repo Input ---
        repo_url, repo_name, subdir = parse_repo_input(repo_input) # repo_name is updated here
        # Use console.rule for the header
        console.print("\n") # Add space before rule
        console.rule(f"[bold default] Installing '[cyan]{repo_name}[/cyan]' [/bold default]", characters="─", style="default")
        console.print("\n") # Add space after rule

        if subdir:
            # Indent subtask/detail
            console.print(f"  [default]↳ Installing from subdirectory: [yellow]{subdir}[/yellow][/default]")

        # --- 2. Determine Install Directory & Clean ---
        install_dir = get_install_dir(scope, repo_name)
        install_dir.parent.mkdir(parents=True, exist_ok=True)
        if install_dir.exists():
            # Indent subtask
            console.print(f"  [default]Cleaning up previous installation at [dim]{install_dir}[/dim]...[/default]")
            if not demo_mode:
                safe_remove_directory(install_dir, debug=current_debug_mode) # Logs internally
            else:
                log_event("[DEMO] Skipping directory removal.", level='debug')
                time.sleep(0.5) # Simulate work
                console.print("    [dim](Skipped in demo mode)[/dim]")

        # --- 3. Git Clone ---
        # Use Progress for cloning
        with Progress(
            SpinnerColumn(spinner_name="dots", style="default"),
            TextColumn("[default]{task.description}[/default]"),
            TimeElapsedColumn(),
            console=console,
            transient=True # Keep transient for single step
        ) as progress:
            task_id = progress.add_task(f"Cloning repository...", total=None)
            clone_success = False
            if not demo_mode:
                try:
                    run_command(
                        ["git", "clone", repo_url, str(install_dir)],
                        debug=current_debug_mode,
                        use_progress=False # Progress is handled externally now
                    )
                    clone_success = True
                except subprocess.CalledProcessError as e:
                    progress.stop() # Stop progress before printing error
                    # Keep error messages red/default, indent details
                    console.print(f"[red]! Failed to clone repository from {repo_url}.[/red]")
                    error_output = e.stderr.strip() if e.stderr else e.stdout.strip()
                    if error_output:
                         console.print(f"  [red]Error:[/red] {error_output}")
                    console.print("  [default]Please check the URL, your network connection, and Git setup.[/default]")
                    return False # Critical failure
                except FileNotFoundError as e:
                     progress.stop()
                     # Specific error for git missing
                     console.print(f"[red]! Error: 'git' command not found.[/red]")
                     console.print(f"  [default]Please install Git and ensure it's in your PATH.[/default]")
                     return False # Critical failure
                except Exception as e: # Catch other potential run_command errors
                     progress.stop()
                     console.print(f"[red]! An unexpected error occurred during git clone: {e}[/red]")
                     return False
            else:
                log_event("[DEMO] Skipping git clone.", level='debug')
                time.sleep(1.5) # Simulate cloning time
                clone_success = True
                # Create dummy directory for subsequent steps in demo mode
                working_dir_demo = install_dir / subdir if subdir else install_dir
                working_dir_demo.mkdir(parents=True, exist_ok=True)
                # Create dummy files needed for detection logic in demo mode
                if not (working_dir_demo / 'package.json').exists(): (working_dir_demo / 'package.json').touch()
                if not (working_dir_demo / 'requirements.txt').exists(): (working_dir_demo / 'requirements.txt').touch()
                if not (working_dir_demo / 'pyproject.toml').exists(): (working_dir_demo / 'pyproject.toml').touch()
                if not (working_dir_demo / 'Cargo.toml').exists(): (working_dir_demo / 'Cargo.toml').touch()
                if not (working_dir_demo / 'go.mod').exists(): (working_dir_demo / 'go.mod').touch()
                if not (working_dir_demo / 'README.md').exists(): (working_dir_demo / 'README.md').touch()

            progress.update(task_id, completed=100) # Mark as complete

        # Print success message after progress finishes
        if clone_success:
            console.print(f"[green]✓[/green] [default]Repository cloned.[/default]")
            if demo_mode: console.print("  [dim](Demo)[/dim]")


        working_dir = install_dir / subdir if subdir else install_dir

        # --- 4. Project Setup (Dependencies & Build) ---
        console.print("[default]Analyzing project structure...[/default]")
        setup_config = ProjectSetup.detect_project_type(working_dir)
        package_data = {} # To store package.json content if needed

        if setup_config:
            if 'error' in setup_config:
                log_event(setup_config['error'], level='error')
                console.print(f"[red]! Could not determine how to install dependencies.[/red]")
                console.print(f"  [red]Error:[/red] {setup_config['error']}")
                return False

            setup_command_str = setup_config['command']
            project_type = setup_config['type']
            console.print(f"[default]Identified project type: [yellow]{project_type}[/yellow][/default]")

            # --- 4a. Pre-check Tools (npm only for now) ---
            if project_type == 'npm':
                log_event("Performing pre-check for npm lifecycle script tools...", level='debug')
                package_json_path = working_dir / 'package.json'
                if package_json_path.exists():
                    try:
                        with open(package_json_path, 'r', encoding='utf-8') as f_pkg:
                            package_data = json.load(f_pkg)
                    except Exception as e_pkg:
                        log_event(f"Error reading package.json for pre-check: {e_pkg}", level='warning')

                scripts_to_check = ['prepare', 'preinstall', 'postinstall', 'build']
                potentially_required_tools = set()
                known_tools_patterns = { 'bun': r'\bbun\b', 'tsc': r'\btsc\b', 'webpack': r'\bwebpack\b', 'node-gyp': r'\bnode-gyp\b' }

                if 'scripts' in package_data and isinstance(package_data['scripts'], dict):
                    for script_name in scripts_to_check:
                        if script_name in package_data['scripts']:
                            script_command = package_data['scripts'][script_name]
                            if isinstance(script_command, str):
                                log_event(f"Analyzing script '{script_name}': {script_command}", level='debug')
                                for tool, pattern in known_tools_patterns.items():
                                    if re.search(pattern, script_command):
                                        log_event(f"Potential requirement found: '{tool}' in script '{script_name}'", level='debug')
                                        potentially_required_tools.add(tool)

                if potentially_required_tools:
                    log_event(f"Potentially required tools from scripts: {list(potentially_required_tools)}", level='info')
                    all_tools_ok = True
                    for tool in sorted(list(potentially_required_tools)):
                        # check_and_install_tool handles its own Rich output
                        if not check_and_install_tool(tool, debug=current_debug_mode):
                            log_event(f"Pre-check failed: Required tool '{tool}' is missing.", level='error')
                            # Error message already printed by check_and_install_tool
                            console.print(f"  [red]! Pre-installation check failed: Required tool '{tool}' is missing or install failed.[/red]",)
                            console.print(f"    [default]This tool might be needed during dependency installation or build. Halting installation.[/default]")
                            all_tools_ok = False
                            break
                        else:
                             # Success message printed by check_and_install_tool
                             console.print(f"  [green]✓[/green] [default]Tool '[cyan]{tool}[/cyan]' is available.[/default]") # Explicit success message here

                    if not all_tools_ok:
                        return False # Halt installation

            # --- 4b. Install Dependencies ---
            with Progress(
                SpinnerColumn(spinner_name="dots", style="default"),
                TextColumn("[default]{task.description}[/default]"),
                TimeElapsedColumn(),
                console=console,
                transient=True
            ) as progress:
                task_id = progress.add_task(f"Installing dependencies...", total=None)
                deps_success = False
                if not demo_mode:
                    try:
                        run_command(
                            setup_command_str.split(),
                            cwd=working_dir,
                            debug=current_debug_mode,
                            use_progress=False # Handled externally
                        )
                        deps_success = True
                    except subprocess.CalledProcessError as e:
                        progress.stop()
                        console.print(f"[red]! Dependency installation failed during `[cyan]{setup_command_str}[/cyan]`.[/red]")
                        error_output = e.stderr.strip() if e.stderr else e.stdout.strip()
                        if error_output:
                            console.print(f"  [red]Error details:[/red]\n{error_output}")
                        console.print(f"  [default]Please check the logs and ensure '{project_type}' tools are correctly installed.[/default]")
                        return False
                    except FileNotFoundError as e:
                        progress.stop()
                        console.print(f"[red]! Dependency installation failed: {e}[/red]")
                        return False
                    except Exception as e:
                        progress.stop()
                        console.print(f"[red]! An unexpected error occurred during dependency installation: {e}[/red]")
                        return False
                else:
                    log_event(f"[DEMO] Skipping dependency installation: {setup_command_str}", level='debug')
                    time.sleep(2) # Simulate install time
                    deps_success = True

                progress.update(task_id, completed=100)

            if deps_success:
                console.print(f"[green]✓[/green] [default]Dependencies installed.[/default]")
                if demo_mode: console.print("  [dim](Demo)[/dim]")


            # --- 4c. Run Build Step (if needed, Go or npm) ---
            built_executable_path = None # Initialize variable to store path if built
            build_step_needed = False
            build_command_list = []
            build_command_str = ""
            build_description = "Building project..."

            # Determine if build is needed and what command to use
            if setup_config and setup_config.get('type') == 'go':
                 if check_command_exists('go'):
                     cmd_dir = working_dir / 'cmd' / repo_name
                     main_go_path_cmd = cmd_dir / 'main.go'
                     main_go_path_root = working_dir / 'main.go'
                     build_target = '.'
                     if main_go_path_cmd.exists(): build_target = f"./cmd/{repo_name}"
                     elif main_go_path_root.exists(): build_target = '.'

                     output_name = f"{repo_name}_server"
                     if os.name == 'nt': output_name += ".exe"
                     output_path = working_dir / output_name

                     build_command_list = ["go", "build", "-o", str(output_path), build_target]
                     build_command_str = ' '.join(shlex.quote(c) for c in build_command_list)
                     build_step_needed = True
                     build_description = "Building Go project..."
                     log_event(f"Go build needed. Command: {build_command_str}", level='info')
                 else:
                     log_event("Go project detected, but 'go' command not found for build.", level='error')
                     console.print("[red]! Cannot build Go project: 'go' command not found.[/red]")
                     return False

            elif setup_config and setup_config.get('type') == 'npm' and 'build' in package_data.get('scripts', {}):
                 entry_point = None
                 if 'bin' in package_data and isinstance(package_data['bin'], dict):
                     entry_point = next(iter(package_data['bin'].values()), None)
                 elif 'main' in package_data:
                     entry_point = package_data['main']

                 if entry_point and ('dist/' in entry_point or 'build/' in entry_point):
                     build_command_base = setup_command_str.split()[0] # npm, yarn, pnpm
                     build_command_str = f"{build_command_base} run build"
                     build_command_list = build_command_str.split()
                     build_step_needed = True
                     build_description = "Building project..."
                     log_event(f"NPM build needed. Command: {build_command_str}", level='info')

            # Execute build step if needed
            if build_step_needed:
                with Progress(
                    SpinnerColumn(spinner_name="dots", style="default"),
                    TextColumn("[default]{task.description}[/default]"),
                    TimeElapsedColumn(),
                    console=console,
                    transient=True
                ) as progress:
                    task_id = progress.add_task(build_description, total=None)
                    build_success = False
                    if not demo_mode:
                        try:
                            run_command(
                                build_command_list,
                                cwd=working_dir,
                                debug=current_debug_mode,
                                use_progress=False # Handled externally
                            )
                            build_success = True
                            if setup_config.get('type') == 'go': # Store path only on success
                                built_executable_path = str(output_path)
                                log_event(f"Go build successful. Executable path: {built_executable_path}", level='info')

                        except subprocess.CalledProcessError as e:
                             progress.stop() # Stop progress before printing error
                             is_windows = sys.platform == 'win32'
                             chmod_error_present = e.stderr and "'chmod' is not recognized" in e.stderr.lower()

                             if is_windows and chmod_error_present and setup_config.get('type') == 'npm':
                                 warning_msg = f"Build step warning (Windows): 'chmod' failed but continuing. Stderr: {e.stderr.strip()}"
                                 log_event(warning_msg, level='warning')
                                 # Print warning but allow success
                                 console.print("  [yellow]![/yellow] [default]Warning: 'chmod' command failed (expected on Windows). Proceeding.[/default]")
                                 build_success = True # Treat as success for flow
                             else:
                                 # Handle other genuine build errors
                                 log_event(f"Build step failed: {e.stderr.strip() if e.stderr else e.stdout.strip()}", level='error')
                                 console.print(f"[red]! Build step failed during `[cyan]{build_command_str}[/cyan]`.[/red]")
                                 error_output = e.stderr.strip() if e.stderr else e.stdout.strip()
                                 if error_output:
                                     console.print(f"  [red]Error details:[/red]\n{error_output}")
                                 console.print(f"  [default]Please check the logs for details.[/default]")
                                 return False # Halt on genuine build failure
                        except FileNotFoundError as e:
                            progress.stop()
                            console.print(f"[red]! Build step failed: {e}[/red]")
                            return False # Halt if build tool missing
                        except Exception as e:
                            progress.stop()
                            log_event(f"Build command execution failed unexpectedly: {str(e)}", level='error')
                            console.print(f"[red]! Build step failed during `[cyan]{build_command_str}[/cyan]`.[/red]")
                            console.print(f"  [red]Error:[/red] {str(e)}")
                            console.print(f"  [default]Please check the logs for details.[/default]")
                            return False # Halt on unexpected error
                    else:
                        log_event(f"[DEMO] Skipping build: {build_command_str}", level='debug')
                        time.sleep(1.5) # Simulate build time
                        build_success = True
                        if setup_config.get('type') == 'go': # Simulate path in demo
                            built_executable_path = str(output_path)
                            log_event(f"[DEMO] Simulated Go build. Executable path: {built_executable_path}", level='info')

                    progress.update(task_id, completed=100)

                if build_success:
                    console.print(f"[green]✓[/green] [default]Project built successfully.[/default]")
                    if demo_mode: console.print("  [dim](Demo)[/dim]")

        else: # This else corresponds to 'if setup_config:'
            log_event("No package manager configuration detected - skipping setup", level='debug')
            console.print("  [dim]i No standard dependency file found (like package.json or requirements.txt). Skipping automatic dependency installation.[/dim]")
            # Still check for package.json for build script info
            package_json_path_fallback = working_dir / 'package.json'
            if package_json_path_fallback.exists():
                try:
                    with open(package_json_path_fallback, 'r', encoding='utf-8') as f_fallback:
                        package_data = json.load(f_fallback)
                        if 'scripts' in package_data and 'build' in package_data['scripts']:
                            log_event("Found build script even without detected package manager, might need manual build.", level='warning')
                            console.print("  [yellow]![/yellow] [default]Found a 'build' script in package.json, but no package manager was detected. Build step skipped; may require manual execution.[/default]")
                except Exception as e_fallback:
                    log_event(f"Error reading package.json during fallback check: {e_fallback}", level='warning')

        # --- 5. Configure Settings ---
        # No specific header needed here, flows into env var section
        settings_path = get_settings_path(scope)
        settings_data = read_settings(settings_path)

        if "mcpServers" not in settings_data or not isinstance(settings_data["mcpServers"], dict):
             log_event(f"Critical error: 'mcpServers' is not a dictionary after read_settings in {settings_path}. Re-initializing.", level='error')
             settings_data["mcpServers"] = {}

        # --- Determine Run Command (after potential build) ---
        run_command_list = None
        if built_executable_path: # Prioritize using the built executable if available
             run_command_list = [built_executable_path, "stdio"]
             log_event(f"Using built executable for run command: {run_command_list}", level='info')
        else: # Fallback to detection if no build happened or failed, or not a Go project
             run_command_list = detect_run_command(working_dir)
             if run_command_list:
                  log_event(f"Using detected run command: {run_command_list}", level='info')
             else:
                  log_event("Could not determine run command (no build and no detection).", level='warning')

        install_time = datetime.utcnow().isoformat() + "Z"

        mcp_entry = {
            "command": "# TODO: Specify command", # Default placeholder
            "args": [],
            "cwd": str(working_dir),
            "env": {},
            "metadata": {
                "name": repo_name,
                "type": "stdio",
                "source": repo_url,
                "installTime": install_time,
                "subdir": subdir if subdir else None
            },
            "disabled": False,
            "alwaysAllow": [],
            "initializationOptions": {},
            "settings": {}
        }

        if run_command_list:
            # Set command/args based on determined run_command_list (either built exe or detected)
            mcp_entry["command"] = run_command_list[0]
            mcp_entry["args"] = run_command_list[1:]
            # Don't print run command here, it's implicit

            # Set metadata type based on command
            cmd_lower = os.path.basename(run_command_list[0]).lower() # Use basename for built executables
            if built_executable_path and setup_config and setup_config.get('type') == 'go':
                 mcp_entry["metadata"]["type"] = "go-stdio" # Explicitly set for built Go exe
            elif "node" in cmd_lower: mcp_entry["metadata"]["type"] = "node-stdio"
            elif "python" in cmd_lower: mcp_entry["metadata"]["type"] = "python-stdio"
            elif "cargo" in cmd_lower: mcp_entry["metadata"]["type"] = "rust-stdio"
            # Add other types if needed
            else:
                 # Keep default 'stdio' or try to infer further if necessary
                 log_event(f"Could not determine specific stdio type for command: {run_command_list[0]}", level='debug')

        else:
            # This path is taken if built_executable_path is None AND detect_run_command failed
            console.print(f"  [yellow]![/yellow] [default]Could not automatically determine run command for {repo_name}.[/default]")
            console.print(f"    [default]Please manually update the 'command' and 'args' in [dim]{settings_path}[/dim] for server '[cyan]{repo_name}[/cyan]'[/default]")


        # --- 6. Environment Variable Handling ---
        env_vars_to_set = {}
        required_vars_list = []
        env_source_file = None # Track source ('mcp.json', '.env.example', 'readme')

        if not skip_env_config:
            # Search message is implicit now
            # console.print("  [default]Searching for environment variable definitions...[/default]")

            # Priority: mcp.json > .env.example > README
            mcp_json_path = working_dir / 'mcp.json'
            env_example_path = working_dir / '.env.example'
            readme_path = None
            for name in ["README.md", "README.rst", "README"]:
                p = working_dir / name
                if p.exists():
                    readme_path = p
                    break

            # 1. Check mcp.json
            if mcp_json_path.exists():
                log_event(f"Found mcp.json at {mcp_json_path}", level='debug')
                # console.print(f"  [default]Found '[yellow]mcp.json[/yellow]'. Checking for 'env' section...[/default]")
                try:
                    with open(mcp_json_path, 'r', encoding='utf-8') as f_mcp:
                        mcp_data = json.load(f_mcp)
                        if isinstance(mcp_data, dict) and 'env' in mcp_data and isinstance(mcp_data['env'], dict):
                            required_vars_list = list(mcp_data['env'].keys())
                            if required_vars_list:
                                env_source_file = 'mcp.json'
                                log_event(f"Found variables defined in 'mcp.json'.", level='debug')
                                # console.print(f"    [default]Found variables defined in '[yellow]mcp.json[/yellow]'.[/default]")
                except Exception as e:
                    log_event(f"Error reading or parsing mcp.json: {e}", level='warning')
                    console.print(f"  [yellow]![/yellow] [default]Could not read or parse 'mcp.json': {e}[/default]")

            # 2. Fallback to .env.example
            if not env_source_file and env_example_path.exists():
                log_event(f"Found .env.example at {env_example_path}", level='debug')
                # console.print(f"  [default]Found '[yellow].env.example[/yellow]'. Parsing variables...[/default]")
                required_vars_list = parse_env_example(env_example_path)
                if required_vars_list:
                    env_source_file = '.env.example'
                    log_event(f"Found variables defined in '.env.example'.", level='debug')
                    # console.print(f"    [default]Found variables defined in '[yellow].env.example[/yellow]'.[/default]")

            # 3. Fallback to README
            if not env_source_file and readme_path:
                log_event(f"Checking README at {readme_path}", level='debug')
                # console.print(f"  [default]Found '[yellow]{readme_path.name}[/yellow]'. Parsing for JSON 'env' blocks...[/default]")
                required_vars_list = parse_readme_for_env_vars(readme_path)
                if required_vars_list:
                    env_source_file = readme_path.name
                    log_event(f"Found potential variables in '{readme_path.name}'.", level='debug')
                    # console.print(f"    [default]Found potential variables in '[yellow]{readme_path.name}[/yellow]'.[/default]")

            # Prompt user if variables were found
            if required_vars_list and env_source_file:
                log_event(f"Prompting for {len(required_vars_list)} env vars found in {env_source_file}", level='info')
                # console.print(f"\n  [default]This MCP requires the following environment variables (found in [yellow]{env_source_file}[/yellow]):[/default]") # Removed, prompt is enough

                # Use Rich Prompt directly, no need for preliminary table
                console.print("\n") # Add space before prompts

                for var in required_vars_list:
                    is_sensitive = any(k in var.lower() for k in ['key', 'secret', 'token', 'password'])
                    # Prompt format matches example
                    prompt_text = f"[prompt]Enter value for [variable]{var}[/variable][/prompt]" # Use theme colors
                    if is_sensitive:
                        prompt_text += "[red]*[/red]"
                    prompt_text += " []: " # Add brackets and colon as in example

                    # Use Rich Prompt, hide input if sensitive
                    value = Prompt.ask(prompt_text, password=is_sensitive, default="") # Default to empty string

                    if value: # Only add if user provided a value
                        env_vars_to_set[var] = value
                        log_event(f"Received value for env var '{var}'", level='debug')
                    else:
                        log_event(f"Skipped env var '{var}'", level='debug')
                        # No explicit "Skipped" message needed

            elif not skip_env_config:
                 log_event("No environment variables found or needed.", level='info')
                 # console.print("  [dim]✓ No environment variable definitions found or needed.[/dim]") # Too verbose

        else:
            log_event("Skipping environment variable configuration due to --skip-env flag.", level='info')
            console.print("  [dim]i Skipping environment variable configuration as requested.[/dim]")

        mcp_entry["env"] = env_vars_to_set

        # --- 7. Save Settings ---
        settings_data["mcpServers"][repo_name] = mcp_entry
        log_event(f"Prepared MCP entry for '{repo_name}': {json.dumps(mcp_entry, indent=2)}", level='debug')

        if "servers" in settings_data:
            log_event(f"Removing legacy 'servers' list from {settings_path}", level='info')
            del settings_data["servers"]

        if not demo_mode:
            try:
                write_settings(settings_path, settings_data)
                log_event(f"Configuration saved to {settings_path}", level='info')
                # No explicit console message needed here, success shown at end
            except Exception as e:
                log_event(f"Failed to write updated settings to {settings_path}: {e}", level='error')
                console.print(f"[red]![/red] [default]Failed to update configuration file at {settings_path}.[/default]")
                console.print(f"  [default]The MCP might be installed but not registered correctly.[/default]")
                console.print(f"  [red]Error:[/red] {e}")
                return False
        else:
            log_event("[DEMO] Skipping writing settings.", level='debug')
            # No explicit console message needed here

        # --- 8. Final Success Message ---
        # Display configured env vars in a table if they exist
        if env_vars_to_set:
             console.print("\n") # Add space before final env table
             from rich import box
             # Use theme styles, SQUARE box, match example
             env_table_final = Table(
                 title="Required Environment Variables",
                 show_header=True,
                 header_style="bold default",
                 box=box.SQUARE, # Match example box
                 border_style="panel.border", # Use theme border color
                 style="default",
                 padding=(0, 1) # Reduce padding slightly if needed
             )
             env_table_final.add_column("Variable", style="variable", no_wrap=True) # Use theme variable style (cyan)
             env_table_final.add_column("Value", style="default") # Use default text color for value
             for k, v in env_vars_to_set.items():
                  is_sensitive = any(k_sens in k.lower() for k_sens in ['key', 'secret', 'token', 'password'])
                  display_val = "[dim]***************[/dim]" if is_sensitive else v # Use dim stars
                  env_table_final.add_row(k, display_val)
             console.print(env_table_final, justify="center") # Center the final table


        # Use Panel for final success message, matching example box style
        from rich import box
        success_title = f"Installation and configuration"
        success_body = f"completed successfully!"
        if demo_mode:
            success_body += " [yellow](Demo)[/yellow]"

        # Center text within the panel content itself
        success_panel_content = f"[bold green center]{success_title}\n{success_body}[/bold green center]"

        console.print("\n") # Add space before final panel
        console.print(Panel(
            success_panel_content,
            expand=False,
            border_style="panel.border", # Use theme border color
            box=box.SQUARE, # Use square box style
            # title_align="center", # Title is part of content now
            # justify="center" # Justify handled by content style
        ))


        log_event(f"Installation completed: {repo_name} ({scope}) at {working_dir}", level='info')
        return True

    except Exception as e:
        # --- Main Error Handling ---
        error_msg = f"Installation failed: {str(e)}"
        log_event(error_msg, level='error')

        # Use rule for error header
        console.print("\n")
        console.rule(f"[bold red] Installation Failed [/bold red]", style="red", characters="─")

        # Print details below rule
        console.print(f"  [default]MCP '[bold cyan]{repo_name}[/bold cyan]' could not be installed.[/default]")
        console.print(f"  [red]Error:[/red] {str(e)}")
        console.print(f"\n  [default]Please check the logs for more details.[/default]")

        if current_debug_mode: # Use the determined debug mode
            import traceback
            tb = traceback.format_exc()
            log_event(f"Stack trace:\n{tb}", level='debug')
            # Optionally print traceback to console in debug mode
            # console.print_exception(show_locals=True)
        return False


def main():
    """Main entry point."""
    # Declare global here, before it's potentially used
    global debug_mode

    parser = argparse.ArgumentParser(
        description="Roo MCP Installer - Manage Model Context Protocol servers.",
        formatter_class=argparse.RawTextHelpFormatter # Preserve formatting in help
        )
    # Add global debug flag early
    parser.add_argument("--debug", action="store_true", help="Enable detailed debug logging.")

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # Install command
    parser_install = subparsers.add_parser(
        "install",
        help="Install or update an MCP server from a Git repository.",
        description=(
            "Installs an MCP server from a GitHub repository URL (e.g., https://github.com/user/repo.git) "
            "or a shorthand format (e.g., user/repo).\n"
            "Optionally specify a subdirectory within the repo using a colon (e.g., user/repo:subdir)."
        )
    )
    parser_install.add_argument("repo_input", help="Repository URL, user/repo slug, or user/repo:subdir")
    parser_install.add_argument("--scope", choices=["global", "project"], default="global", help="Install scope (default: global)")
    parser_install.add_argument("--skip-env", action="store_true", help="Skip interactive environment variable configuration.")
    parser_install.add_argument("--demo", action="store_true", help="Run in demo mode: show UI without performing actions.")
    # Debug is now global

    # List command
    parser_list = subparsers.add_parser("list", help="List installed MCP servers.")

    # Logs command
    parser_logs = subparsers.add_parser("logs", help="Show Roo logs.")
    parser_logs.add_argument("--lines", "-n", type=int, help="Show the last N lines.")
    parser_logs.add_argument("--follow", "-f", action="store_true", help="Follow log output.")

    # Parse known args first to handle global debug flag before command execution
    args, unknown = parser.parse_known_args()

    # Reconfigure logging if debug flag was set globally *after* initial check
    # The initial check happens before main() is called
    if args.debug and not debug_mode: # If --debug is present AND debug_mode wasn't already True
        logging_config.configure_logging(debug=True)
        # Update RichHandler level too
        for handler in logging.getLogger().handlers:
            if isinstance(handler, RichHandler):
                handler.setLevel(logging.DEBUG)
        log_event("Debug mode enabled via command line flag.", level='debug')
        # Update global flag so other functions see the change
        debug_mode = True
    elif not args.debug and debug_mode:
        # This case handles if --debug was NOT passed, but debug_mode was somehow true initially
        # (e.g. hardcoded or from env var in future). Reset to non-debug.
        logging_config.configure_logging(debug=False)
        for handler in logging.getLogger().handlers:
             if isinstance(handler, RichHandler):
                 handler.setLevel(logging.WARNING)
        log_event("Debug mode disabled (no --debug flag).", level='debug')
        debug_mode = False
    # If args.debug and debug_mode are both true, or both false, no change needed.


    exit_code = 0

    try:
        if args.command == "install":
            # Pass the potentially updated debug flag and the new demo flag
            if not install_mcp(
                args.repo_input,
                scope=args.scope,
                debug=debug_mode,
                skip_env_config=args.skip_env,
                demo_mode=args.demo # Pass demo flag
            ):
                exit_code = 1
        elif args.command == "list":
            if not list_installed():
                exit_code = 1
        elif args.command == "logs":
            if not show_logs(follow=args.follow, lines=args.lines):
                exit_code = 1
    except Exception as e:
        # Log the exception using the configured logger
        log_event(f"An unexpected error occurred in main: {e}", level='critical')
        # Print user-friendly error using Rich Console
        console.print(f"\n[bold red]Critical Error:[/bold red] {e}")
        if debug_mode: # Use the final state of debug_mode
            # Print traceback using Rich for better formatting
            console.print_exception(show_locals=True)
        exit_code = 1

    sys.exit(exit_code)

if __name__ == "__main__":
    main()