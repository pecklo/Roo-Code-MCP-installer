# Guide: Porting roo.py CLI to a VS Code Extension (Node.js/TypeScript)

This guide details the steps and logic required to port the Python-based `roo.py` MCP server management tool into a Visual Studio Code extension using Node.js and TypeScript. It aims to replicate the original functionality as closely as possible within the VS Code environment.

**Core Technologies & Concepts:**

*   **Node.js:** `fs` (file system), `path` (path manipulation), `child_process` (running external commands).
*   **TypeScript:** For type safety and modern JavaScript features.
*   **VS Code API:** `vscode` namespace, including `commands`, `window`, `workspace`, `Uri`, `extensions`, `ProgressLocation`, `OutputChannel`.
*   **Libraries:** `simple-git` (for Git operations), potentially a logging library like `winston`.

**Extension Structure (Conceptual):**

*   `src/extension.ts`: Main activation file, command registration.
*   `src/commands/`: Directory for command handlers (install, list, logs).
*   `src/utils/`: Helper functions (file system, command execution, config management, logging).
*   `src/constants.ts`: Paths, configuration keys, etc.
*   `package.json`: Extension manifest, dependencies, command contributions.

---

## 1. MCP Server Installation (`install` command)

*   **Python Feature:** Clones repo, detects type, installs dependencies, detects run command, configures environment variables, registers server.
*   **VS Code/Node.js Mapping:**
    *   Command Registration: `vscode.commands.registerCommand('roo.installMcp')`.
    *   UI: `vscode.window.showInputBox` (for repo URL), `vscode.window.withProgress` (for long operations), `vscode.window.showQuickPick` (for scope), `vscode.window.showInformationMessage` (for prompts/confirmations).
    *   File System: `fs` module (`promises` API preferred), `path` module.
    *   Process Execution: `child_process.exec` or `child_process.spawn`.
    *   Git: `simple-git` library.
    *   Configuration: `vscode.workspace.getConfiguration` or custom JSON file handling (see Section 4).
*   **Implementation Strategy:**
    1.  Register the `roo.installMcp` command in `extension.ts`.
    2.  The command handler function will orchestrate the installation flow.
    3.  Use `vscode.window.showInputBox` to get the repository input (URL or slug).
    4.  Use `vscode.window.showQuickPick` to select scope ('global' or 'project').
    5.  Wrap the entire process in `vscode.window.withProgress` to show status updates.
*   **Detailed Logic Replication:**
    *   **`parse_repo_input(repo_input)` Logic:**
        *   Implement a TypeScript function `parseRepoInput(repoInput: string): { gitUrl: string; subdir: string | null; repoName: string }`.
        *   Use regular expressions or string manipulation to check if it's a full URL or a `owner/repo[:subdir]` slug.
        *   If it's a slug, construct the GitHub URL (`https://github.com/${owner}/${repo}.git`).
        *   Extract the optional `:subdir` part.
        *   Extract the `repoName`.
        *   Return an object containing the full Git URL, the subdirectory (or null), and the repository name.
    *   **`get_install_dir(scope, repo_name)` Logic:**
        *   Implement `getInstallDir(scope: 'global' | 'project', repoName: string, context: vscode.ExtensionContext): vscode.Uri`.
        *   Use `path.join`.
        *   For `global` scope: Use `context.globalStorageUri.fsPath` (or a dedicated subdirectory within it like `mcps`) combined with `repoName`. Ensure the global storage directory exists using `fs.promises.mkdir`.
        *   For `project` scope: Check `vscode.workspace.workspaceFolders`. If available, use `path.join(vscode.workspace.workspaceFolders[0].uri.fsPath, '.roo', 'mcps', repoName)`. Handle the case where no workspace is open.
        *   Return a `vscode.Uri` object for the target directory.
    *   **`safe_remove_directory(path, debug)` Logic:**
        *   Implement `safeRemoveDirectory(dirUri: vscode.Uri)`.
        *   Use `fs.promises.rm(dirUri.fsPath, { recursive: true, force: true })`. Add logging for debug purposes.
    *   **`run_command(...)` Logic (Core Adaptation):**
        *   Implement an async function `runCommand(command: string, cwd: string, progress: vscode.Progress<{ message?: string; increment?: number }>, options?: { env?: NodeJS.ProcessEnv, logOutput?: boolean, outputChannel?: vscode.OutputChannel }): Promise<{ stdout: string; stderr: string; code: number | null }>`.
        *   Use `child_process.spawn` for better control over stdio and streaming output.
        *   Pipe `stdout` and `stderr` to an `vscode.OutputChannel` if `logOutput` is true.
        *   Update `progress.report({ message: 'Running command...' })`.
        *   Capture `stdout` and `stderr` streams into strings.
        *   Return a promise that resolves with the output and exit code when the process finishes, or rejects on error.
        *   **Crucially:** Before running commands like `npm install`, `go build`, etc., call the `checkAndInstallTool` equivalent (see below).
    *   **`check_and_install_tool(tool_name, debug)` Logic:**
        *   Implement `checkCommandExists(command: string): Promise<boolean>`. Use `child_process.exec` (e.g., `command --version` or `where command` / `which command`) and check the exit code. Handle errors gracefully (command not found).
        *   Implement `checkAndInstallTool(toolName: string, installCommandSuggestion: string | null, progress: vscode.Progress<{ message?: string; increment?: number }>): Promise<boolean>`.
        *   Call `checkCommandExists`.
        *   If the tool doesn't exist, use `vscode.window.showWarningMessage` to ask the user if they want to attempt installation (e.g., "Tool 'npm' not found. Attempt to install Node.js (which includes npm)?"). Provide "Yes" / "No" options.
        *   If yes and `installCommandSuggestion` is provided, potentially run the suggested command using `runCommand` (use with caution, maybe just guide the user). For common tools like Node.js, Git, Go, provide links or instructions.
        *   Return `true` if the tool exists or was successfully handled, `false` otherwise. Stop the installation if a required tool is missing and not installed.
    *   **`ProjectSetup.detect_project_type(repo_dir)` Logic:**
        *   Implement `detectProjectType(repoDirUri: vscode.Uri): Promise<'npm' | 'pip' | 'poetry' | 'cargo' | 'go' | 'unknown'>`.
        *   Use `fs.promises.stat` or `fs.promises.access` to check for the existence of marker files (`package.json`, `requirements.txt`, `pyproject.toml` (check for `[tool.poetry]`), `Cargo.toml`, `go.mod`) within `repoDirUri.fsPath`.
        *   Return the detected type string.
    *   **Dependency Installation:**
        *   Based on the detected project type, determine the install command (`npm install`, `pip install -r requirements.txt`, `poetry install`, `go mod download`, `cargo build`).
        *   Call `checkAndInstallTool` for the required build tool (`npm`, `pip`, `poetry`, `go`, `cargo`).
        *   Call `runCommand` with the appropriate install command and the cloned repo directory as `cwd`.
    *   **`detect_run_command(mcp_dir)` Logic:**
        *   Implement `detectRunCommand(mcpDirUri: vscode.Uri, projectType: string): Promise<string | null>`.
        *   **npm:** Check `package.json` for a `scripts.start:mcp` or `scripts.start` script that includes `stdio`. If not found, default to `node dist/index.js stdio` or `node index.js stdio` (check if `index.js` or `dist/index.js` exists). Check for build scripts (`build`, `compile`) and potentially run them first using `runCommand` if source files (`.ts`) exist but distribution files (`.js`) don't. May need `checkAndInstallTool('tsc')` or build tools like `webpack`.
        *   **pip/poetry:** Look for common entry points like `main.py`, `app.py`, `run.py`. Default to `python main.py stdio` or similar, checking file existence.
        *   **go:** Check for `main.go`. Default to `go run . stdio`. Consider running `go build -o <repoName> . stdio` and using the executable path `./<repoName> stdio`. Requires `checkAndInstallTool('go')`.
        *   **cargo:** Check for `src/main.rs`. Default to `cargo run -- stdio`. Consider running `cargo build --release` and using the executable path `./target/release/<repoName> stdio`. Requires `checkAndInstallTool('cargo')`.
        *   Return the detected command string or `null`.
    *   **Environment Variable Parsing & Configuration:**
        *   Implement `parseEnvExample(filePath: string): Promise<string[]>`. Read the file using `fs.promises.readFile`, split into lines, filter lines that look like variable assignments (e.g., `VAR_NAME=`), and extract the `VAR_NAME`.
        *   Implement `parseReadmeForEnvVars(readmePath: string): Promise<string[]>`. Read the README using `fs.promises.readFile`. Use a regex to find JSON code blocks (```json ... ```). Parse the JSON using `JSON.parse` (inside a try-catch). Recursively find all string keys in the parsed JSON object (similar to `_find_env_keys_recursive`).
        *   **Discovery Logic:** Check for `mcp.json` first (if it exists and defines env vars). Then check for `.env.example`. Then check `README.md`.
        *   **User Input:** For each required environment variable found:
            *   Use `vscode.window.showInputBox({ prompt: \`Enter value for \${varName}:\`, ignoreFocusOut: true, password: varName.toLowerCase().includes('secret') || varName.toLowerCase().includes('key') || varName.toLowerCase().includes('token') })`.
            *   Store the collected key-value pairs.
        *   **Saving:** Store these environment variables securely. Options:
            *   **VS Code Secrets API:** `context.secrets.store(secretKey, value)` - Best for sensitive data. The `secretKey` could be `roo.mcp.${serverName}.${envVarName}`.
            *   **.env file:** Write a `.env` file inside the specific MCP server's installation directory (`path.join(installDirUri.fsPath, '.env')`). Use `fs.promises.writeFile`. **Warning:** Less secure for sensitive tokens if the directory isn't properly protected.
            *   **Configuration File:** Store non-sensitive variables directly in the `mcp_settings.json` (see Section 4). Less ideal for secrets.
        *   Choose the Secrets API for sensitive data and potentially the `.env` file for non-sensitive ones needed directly by the server process.
    *   **Registration:** Update the configuration file (see Section 4) with the server's name, installation path, detected run command, and potentially paths to env vars or references to stored secrets.

---

## 2. MCP Server Listing (`list` command)

*   **Python Feature:** Displays MCPs installed globally and in the current project.
*   **VS Code/Node.js Mapping:**
    *   Command Registration: `vscode.commands.registerCommand('roo.listMcps')`.
    *   UI: `vscode.window.showQuickPick` or a custom Webview for richer display. `vscode.OutputChannel` for simple text list.
    *   File System: `fs.promises.readdir`, `fs.promises.stat`.
    *   Configuration: Reading the config files (see Section 4).
*   **Implementation Strategy:**
    1.  Register the `roo.listMcps` command.
    2.  The handler will read server details from both global and project configuration scopes (see Section 4).
    3.  Format the list for display.
    4.  Use `vscode.window.showQuickPick` with server names as items, potentially adding descriptions (path, scope) or use an `OutputChannel`.
*   **Detailed Logic Replication:**
    *   Implement `listInstalledMcps(context: vscode.ExtensionContext): Promise<Array<{ name: string; path: string; scope: 'global' | 'project'; runCommand: string | null }>>`.
    *   Get global settings path (`getSettingsPath('global', context)`). Read settings using `readSettings`.
    *   Get project settings path (`getSettingsPath('project', context)`). Read settings using `readSettings`.
    *   Combine the `mcpServers` entries from both, adding a `scope` property to each.
    *   Validate that the directories listed in the settings still exist using `fs.promises.stat`. Filter out entries with missing directories.
    *   Return the combined, validated list.
    *   In the command handler, call `listInstalledMcps`. Format the results. Display using `vscode.OutputChannel.appendLine` or format for `showQuickPick`.

---

## 3. Log Viewing (`logs` command)

*   **Python Feature:** Shows the latest log file content, supports tailing (`-f`) and showing last N lines (`-n`).
*   **VS Code/Node.js Mapping:**
    *   Command Registration: `vscode.commands.registerCommand('roo.showLogs')`.
    *   UI: `vscode.OutputChannel`, `vscode.window.showInputBox` (for lines), `vscode.window.showQuickPick` (for follow yes/no).
    *   File System: `fs.promises.readFile`, `fs.watchFile` or `fs.watch`.
    *   Logging Config: Need to know the log file path (see Section 5).
*   **Implementation Strategy:**
    1.  Register the `roo.showLogs` command.
    2.  Determine the log file path (e.g., `path.join(context.logUri.fsPath, 'roo-extension.log')`).
    3.  Ask user for number of lines and follow option using `showInputBox` / `showQuickPick`.
    4.  Create or get a dedicated `vscode.OutputChannel` (e.g., "Roo MCP Logs").
    5.  Implement logic to read and display the log content.
*   **Detailed Logic Replication:**
    *   Implement `showLogs(logFilePath: string, follow: boolean, lines: number | undefined, outputChannel: vscode.OutputChannel, context: vscode.ExtensionContext)`.
    *   Clear the `outputChannel`.
    *   Use `fs.promises.readFile(logFilePath, 'utf-8')` to get content.
    *   Split content into lines.
    *   If `lines` is specified, take the last `lines` number of lines (`.slice(-lines)`).
    *   Append the selected lines to the `outputChannel`.
    *   Make the `outputChannel` visible using `.show()`.
    *   **Follow Logic (`-f`):**
        *   If `follow` is true:
            *   Store the initial size of the file.
            *   Use `fs.watchFile(logFilePath, { interval: 500 }, (curr, prev) => { ... })`. **Note:** `fs.watch` might be preferred but can be less reliable across platforms. `fs.watchFile` polls.
            *   Inside the watcher callback: If `curr.size > prev.size`, open the file for reading (`fs.createReadStream`) starting from `prev.size`.
            *   Read the new content chunk by chunk.
            *   Append the new content to the `outputChannel`.
            *   Keep track of the watcher; provide a way to stop it (e.g., a status bar item, another command, or when the output channel is closed/hidden). Register the watcher in `context.subscriptions` so it's disposed automatically.

---

## 4. Configuration Management

*   **Python Feature:** Manages MCP server registration in global (`~/.roo/mcp_settings.json`) and project (`./.roo/mcp.json`) JSON files.
*   **VS Code/Node.js Mapping:**
    *   Storage: `context.globalStorageUri`, `vscode.workspace.workspaceFolders[0].uri` combined with `.roo` or `.vscode`.
    *   File System: `fs.promises` for reading/writing JSON.
    *   VS Code Settings API: `vscode.workspace.getConfiguration` / `update` could be an alternative for *simpler* config, but replicating the exact file structure requires direct `fs` access. Let's stick to `fs` for parity.
*   **Implementation Strategy:**
    1.  Define the structure of the settings JSON (e.g., `{ "mcpServers": { "serverName": { "path": "...", "runCommand": "...", "envSecrets": ["VAR1", "VAR2"] } } }`).
    2.  Implement helper functions equivalent to Python's `get_settings_path`, `read_settings`, `write_settings`.
*   **Detailed Logic Replication:**
    *   **`get_settings_path(scope)` Logic:**
        *   Implement `getSettingsUri(scope: 'global' | 'project', context: vscode.ExtensionContext): vscode.Uri | null`.
        *   `global`: Return `vscode.Uri.joinPath(context.globalStorageUri, 'mcp_settings.json')`. Ensure `context.globalStorageUri` exists first using `fs.promises.mkdir`.
        *   `project`: Check `vscode.workspace.workspaceFolders`. If exists, return `vscode.Uri.joinPath(vscode.workspace.workspaceFolders[0].uri, '.roo', 'mcp.json')`. If not, return `null`.
    *   **`read_settings(settings_path)` Logic:**
        *   Implement `async readSettings(settingsUri: vscode.Uri): Promise<{ mcpServers: Record<string, { path: string; runCommand: string | null; envSecrets?: string[] }> }>`.
        *   Use a `try-catch` block.
        *   Inside `try`: `const content = await fs.promises.readFile(settingsUri.fsPath, 'utf-8'); const data = JSON.parse(content);`.
        *   Validate the structure: ensure `data` is an object and `data.mcpServers` exists and is an object. If not, return a default structure `{ mcpServers: {} }`.
        *   Return the parsed and validated data.
        *   Inside `catch`: If the error is `ENOENT` (file not found), return the default structure. Otherwise, log the error and return the default structure or re-throw.
    *   **`write_settings(settings_path, settings_data)` Logic:**
        *   Implement `async writeSettings(settingsUri: vscode.Uri, settingsData: any): Promise<void>`.
        *   Ensure the directory exists: `await fs.promises.mkdir(path.dirname(settingsUri.fsPath), { recursive: true });`.
        *   Convert data to JSON: `const content = JSON.stringify(settingsData, null, 2);` (pretty-print).
        *   Write the file: `await fs.promises.writeFile(settingsUri.fsPath, content, 'utf-8');`.
        *   Add error handling.
    *   **Usage:** Call these functions within the `install` and `list` command handlers to read/update the MCP server registrations. When installing, get the appropriate URI, read existing settings, add/update the entry for the new server, and write back.

---

## 5. Logging (`logging_config.py`)

*   **Python Feature:** Configures standard Python logging to a rotating file, integrates with `rich` for console output, provides `log_event`.
*   **VS Code/Node.js Mapping:**
    *   Logging Library: `winston` or similar Node.js library.
    *   VS Code Output: `vscode.OutputChannel`.
    *   Log File Path: `context.logUri`.
*   **Implementation Strategy:**
    1.  Choose a logging library (e.g., `winston`).
    2.  Configure it in `extension.ts` or a dedicated `logging.ts` module during activation.
    3.  Set up a file transport pointing to `vscode.Uri.joinPath(context.logUri, 'roo-extension.log').fsPath`. Configure rotation if needed (e.g., `winston-daily-rotate-file`).
    4.  Create a dedicated `vscode.OutputChannel` ("Roo Extension Logs").
    5.  Optionally, create a custom transport for the logger that writes to the `OutputChannel` based on log level (e.g., INFO and above).
    6.  Export a logger instance or helper function (`logEvent`) for use throughout the extension.
*   **Detailed Logic Replication:**
    *   **Configuration:**
        ```typescript
        // src/logging.ts
        import * as winston from 'winston';
        import * as path from 'path';
        import * as vscode from 'vscode';

        let logger: winston.Logger;
        let outputChannel: vscode.OutputChannel;

        export function configureLogging(context: vscode.ExtensionContext, level: string = 'info') {
            if (logger) return logger; // Already configured

            outputChannel = vscode.window.createOutputChannel("Roo Extension Logs");
            context.subscriptions.push(outputChannel); // Dispose channel on deactivation

            const logFilePath = vscode.Uri.joinPath(context.logUri, 'roo-extension.log').fsPath;
            // Ensure log directory exists
            vscode.workspace.fs.createDirectory(context.logUri);

            // Custom transport for VS Code Output Channel
            const outputChannelTransport = new winston.transports.Console({
                level: 'warn', // Only show warnings and errors in the channel by default
                format: winston.format.combine(
                    winston.format.timestamp(),
                    winston.format.printf(({ level, message, timestamp }) => {
                        return `${timestamp} [${level.toUpperCase()}]: ${message}`;
                    })
                ),
                log: (info, callback) => {
                    outputChannel.appendLine(info[Symbol.for('message')]);
                    callback();
                }
            });


            logger = winston.createLogger({
                level: level, // 'info' or 'debug'
                format: winston.format.combine(
                    winston.format.timestamp(),
                    winston.format.errors({ stack: true }), // Log stack traces
                    winston.format.json() // Log as JSON to file
                ),
                transports: [
                    new winston.transports.File({
                        filename: logFilePath,
                        maxsize: 5 * 1024 * 1024, // 5MB
                        maxFiles: 3,
                        tailable: true,
                    }),
                    outputChannelTransport // Add the custom transport
                ],
            });

             // Optional: Capture console.log/warn/error
             // console.log = (...args) => logger.info(args.join(' '));
             // console.warn = (...args) => logger.warn(args.join(' '));
             // console.error = (...args) => logger.error(args.join(' '));


            logger.info('Logging configured.');
            return logger;
        }

        // Helper like Python's log_event
        export function logEvent(level: 'info' | 'warn' | 'error' | 'debug', message: string, data?: any) {
            if (!logger) {
                console.error("Logger not configured!");
                return;
            }
            logger.log(level, message, data);
        }

        export function getLogger(): winston.Logger {
             if (!logger) {
                 throw new Error("Logger not configured!");
             }
             return logger;
        }
        ```
    *   **Activation:** Call `configureLogging(context, debugLevel)` early in the `activate` function in `extension.ts`. Determine `debugLevel` based on a launch argument or configuration setting.
    *   **Usage:** Import `logEvent` or `getLogger` and use it throughout the codebase: `logEvent('info', 'Starting MCP installation', { repo: repoInput });`.
    *   **Deprecation Warnings:** Node.js handles deprecation warnings differently. They usually log to stderr. You can capture stderr from `child_process` if needed, but replicating the specific Python `warnings.catch_warnings` is not directly applicable.

---

## 6. TUI/CLI Interface (`rich` and `argparse`)

*   **Python Feature:** Uses `argparse` for command structure and `rich` for enhanced terminal UI.
*   **VS Code/Node.js Mapping:**
    *   Command Structure: `package.json` (`contributes.commands`) and `vscode.commands.registerCommand`.
    *   UI Elements: `vscode.window` methods (`showInputBox`, `showQuickPick`, `showInformationMessage`, `withProgress`), `vscode.OutputChannel`, potentially `vscode.WebviewPanel` for complex UIs like tables.
*   **Implementation Strategy:**
    1.  Define commands in `package.json` with titles.
    2.  Register handlers using `vscode.commands.registerCommand`.
    3.  Replace `rich` components with their VS Code API equivalents within the command handlers.
*   **Detailed Logic Replication:**
    *   **`argparse` -> `vscode.commands`:** Each subcommand (`install`, `list`, `logs`) becomes a separate `vscode.commands.registerCommand` call linked to a handler function. Arguments like `--scope` or `--lines` are handled using `vscode.window.showQuickPick` or `vscode.window.showInputBox` within the handler. The `--debug` flag can be a launch configuration option or a VS Code setting.
    *   **`rich.Progress` -> `vscode.window.withProgress`:** Use `vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "MCP Task", cancellable: true }, (progress, token) => { ... })`. Update progress using `progress.report({ message: '...', increment: ... })`. Handle cancellation using the `token`.
    *   **`rich.Confirm` -> `vscode.window.showInformationMessage`:** Use `vscode.window.showInformationMessage('Are you sure?', { modal: true }, 'Yes', 'No')`. Check the returned value.
    *   **`rich.Prompt` -> `vscode.window.showInputBox`:** Use `vscode.window.showInputBox({ prompt: 'Enter value:', password: isSensitive })`.
    *   **`rich.Panel`, `rich.Table`, `rich.Syntax` -> `vscode.OutputChannel` / `vscode.WebviewPanel`:**
        *   For simple formatted text (like panels or basic lists), use Markdown formatting within an `OutputChannel` or `showInformationMessage`.
        *   For complex tables or syntax highlighting, create a `vscode.WebviewPanel`. Generate HTML content (potentially using a library for tables) and use CSS for styling. For syntax highlighting, use a JavaScript library like Prism.js or Highlight.js within the webview.
    *   **`rich.Rule` -> `vscode.OutputChannel.appendLine`:** Simply append a line of dashes or similar characters: `outputChannel.appendLine('---');`.
    *   **Theming:** VS Code handles theming. Use standard API elements, which adapt to the user's theme. For webviews, use VS Code CSS variables (`--vscode-editor-background`, etc.) for theme consistency.

---

## 7. Dependency/Tool Management

*   **Python Feature:** Detects project type, runs install commands, checks/installs required tools.
*   **VS Code/Node.js Mapping:** Already covered substantially within Section 1 (Installation).
    *   Project Detection: `fs.promises.access` / `fs.promises.stat`.
    *   Install Commands: `child_process.spawn` via `runCommand` helper.
    *   Tool Checking: `child_process.exec` via `checkCommandExists` helper.
    *   Tool Installation Prompt: `vscode.window.showWarningMessage` via `checkAndInstallTool` helper.
*   **Implementation Strategy:** Integrate the `detectProjectType`, `checkAndInstallTool`, and `runCommand` functions into the `install` command's workflow as described in Section 1.
*   **Detailed Logic Replication:** The logic described in Section 1 for `detectProjectType`, `checkAndInstallTool`, `checkCommandExists`, and `runCommand` directly replicates the Python script's functionality using Node.js and VS Code APIs. Ensure robust error handling for failed commands or missing tools.

---

**Conclusion:**

This guide provides a comprehensive plan for porting `roo.py`. The key is mapping Python CLI/TUI concepts to the event-driven, API-based environment of VS Code extensions. Careful implementation of file system operations, process execution, configuration management, and UI interactions using the `vscode` API and standard Node.js modules will allow for a faithful replication of the original tool's features within the VS Code ecosystem. Remember to handle errors gracefully and provide informative feedback to the user via progress notifications, output channels, and messages.