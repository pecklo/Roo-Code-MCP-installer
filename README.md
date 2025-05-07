# Roo MCP Installer

## Description

A command-line utility designed to streamline the installation and management of Roo Model Context Protocol (MCP) servers. It fetches MCP server code from Git repositories, handles dependencies, configuration, and registration within the Roo environment.

## Features

*   **Git Repository Installation:** Installs MCPs directly from GitHub repository URLs (e.g., `https://github.com/user/repo.git`) or shorthand slugs (`user/repo`).
*   **Subdirectory Support:** Allows installation from a specific subdirectory within a repository using a colon separator (e.g., `user/repo:subdir`).
*   **Installation Scopes:** Supports both `global` (shared across projects, typically in `~/.roo/mcps`) and `project` (specific to the current directory, in `./.roo/mcps`) installation scopes.
*   **Automatic Project Type Detection:** Identifies project types based on standard configuration files:
    *   Node.js (`package.json`)
    *   Python (`requirements.txt`, `pyproject.toml`)
    *   Go (`go.mod`, `main.go`)
    *   Rust (`Cargo.toml`) (Still in progress) (may not work)
*   **Dependency Management:** Automatically installs project dependencies using the detected package manager:
    *   `npm install` (with fallback checks for `yarn install` or `pnpm install`)
    *   `pip install -r requirements.txt` (with fallback check for `pip3`)
    *   `poetry install` (with fallback check for `pip install -e .`)
    *   `go mod download`
    *   `cargo build` (also serves as dependency fetching)
*   **Build Step Execution:** Automatically runs build commands if necessary:
    *   Go: `go build -o <output_path> <target>`
    *   Node.js: `npm run build` (or `yarn`/`pnpm`) if a build script exists and seems necessary based on `main`/`bin` fields.
*   **Environment Variable Configuration:**
    *   Detects required environment variables by checking `mcp.json` (highest priority), `.env.example`, or JSON code blocks within the repository's `README.md` file.
    *   Interactively prompts the user to enter values for detected variables.
    *   Masks input for variables with names suggesting sensitivity (e.g., containing `KEY`, `SECRET`, `TOKEN`, `PASSWORD`).
    *   Allows skipping the interactive configuration using the `--skip-env` flag.
*   **Automatic Tool Checking & Installation:**
    *   Checks for the presence of essential command-line tools (`git`, `npm`, `node`, `python`, `go`, `cargo`, `bun`, `tsc`, etc.).
    *   Prompts the user to automatically install missing tools globally if a known installation command exists (e.g., `npm install -g bun`).
*   **List Installed MCPs:** The `list` command displays all MCPs installed in both global and project scopes, showing their names and installation paths.
*   **Log Viewing:** The `logs` command allows viewing the application's log files.
    *   `--lines` / `-n`: Show only the last N lines.
    *   `--follow` / `-f`: Continuously monitor the log file for new entries (similar to `tail -f`).
*   **Rich TUI:** Utilizes the `rich` library to provide an enhanced terminal user interface with spinners, progress bars, styled text, tables, and interactive prompts.
*   **Debug Mode:** The `--debug` flag enables verbose logging to the console and log files for troubleshooting.
*   **Demo Mode:** The `--demo` flag (for the `install` command) simulates the installation process, showing the UI and intended actions without actually modifying the file system or running commands.

## Usage

The script is run using `python roo.py <command> [options]`.

**Commands:**

*   `install <repo_input> [options]`
    *   Installs or updates an MCP server.
    *   `<repo_input>`: The repository URL, `user/repo` slug, or `user/repo:subdir`.
    *   `--scope <global|project>`: Set the installation scope (default: `global`).
    *   `--skip-env`: Skip interactive prompt for environment variables.
    *   `--demo`: Run installation in demo mode (no actual changes).
    *   `--debug`: Enable debug logging.
*   `list [options]`
    *   Lists installed MCP servers.
    *   `--debug`: Enable debug logging.
*   `logs [options]`
    *   Shows log files.
    *   `--lines N` or `-n N`: Show the last N lines.
    *   `--follow` or `-f`: Follow log output in real-time.
    *   `--debug`: Enable debug logging.

## Examples

**Install an MCP globally:**
```bash
python roo.py install username/my-cool-mcp
```

**Install an MCP into the current project:**
```bash
python roo.py install https://github.com/username/project-specific-mcp.git --scope project
```

**Install an MCP from a subdirectory, skipping environment variable setup:**
```bash
python roo.py install username/mono-repo:tools/my-mcp --skip-env
```

**Simulate an installation with debug output:**
```bash
python roo.py install username/test-mcp --demo --debug
```

**List all installed MCPs:**
```bash
python roo.py list
```

**View the latest log entries:**
```bash
python roo.py logs
```

**View the last 100 lines of the logs:**
```bash
python roo.py logs --lines 100
```

**Follow the logs in real-time:**
```bash
python roo.py logs --follow
```

## Dependencies

*   **Python:** Version 3.11 or higher is required (due to the use of `tomllib`).
*   **Git:** Must be installed and accessible in the system's PATH.
*   **Third-Party Python Packages:** See `requirements.txt` below. Specific project types may require additional tools (like Node.js/npm, Go, Rust/Cargo) to be installed.

## Requirements File (`requirements.txt`)

```text
rich
```

## License

MIT License

Copyright (c) 2025 [Your Name or Organization]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
