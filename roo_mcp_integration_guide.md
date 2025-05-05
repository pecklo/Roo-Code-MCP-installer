# Guide: Integrating Features into the Roo Code MCP Tab

This guide details the steps and concepts required to adapt an existing software feature or create a new one for integration as an MCP (Model Context Protocol) Server within the Roo Code VS Code extension's MCP tab. It focuses on running your feature as a separate process managed by Roo Code and communicating via the MCP standard.

**Target Audience:** Developers looking to extend Roo Code's capabilities by adding custom tools, data sources, or interactive features accessible through the dedicated MCP tab.

**Core Concepts & Technologies:**

*   **MCP (Model Context Protocol):** A specification for communication between Roo Code and external processes (MCP Servers). Defines how tools and resources are exposed and invoked. (See Roo Code documentation for the full specification).
*   **MCP Server:** Your feature packaged as a standalone executable or script that communicates with Roo Code over standard input/output (stdio).
*   **JSON-RPC 2.0:** The underlying protocol used for messages over stdio between Roo Code and the MCP Server.
*   **Stdio Communication:** The MCP server reads JSON-RPC requests from `stdin` and writes JSON-RPC responses/notifications to `stdout`. Each JSON object must be on a single line, terminated by a newline (`\n`). `stderr` can be used for logging, often captured by Roo Code.
*   **Node.js/TypeScript (Recommended):** While MCP servers can be written in any language, Node.js/TypeScript is often convenient for VS Code integration tasks. Examples may use these.
*   **VS Code Extension Context (for Roo Code):** Understanding how Roo Code itself manages servers, configuration, and the webview UI is helpful context.

**Assumed Structure of an MCP Server Project (Example):**

*   `src/`: Source code for your feature/server logic.
*   `src/main.ts` / `src/index.js` / `main.py` etc.: Main entry point that starts the stdio JSON-RPC listener.
*   `mcp.json`: Manifest file describing your server to Roo Code.
*   `package.json` / `requirements.txt` / `go.mod` etc.: Language-specific dependency files.
*   `.env.example` (Optional): Template for required environment variables.
*   `README.md`: Instructions for users and developers.

---

## 1. Prerequisites

Before integrating a feature as an MCP Server, ensure you have:

*   **Knowledge:**
    *   Proficiency in the programming language you'll use for the server (e.g., Node.js, Python, Go, Rust).
    *   Understanding of standard input/output (stdio) and process management.
    *   Familiarity with JSON-RPC 2.0 concepts (requests, responses, notifications, errors).
    *   Basic understanding of VS Code extension architecture (useful for context, though not strictly required for server development).
    *   Familiarity with Git for version control and installation via repositories.
*   **Tools:**
    *   Visual Studio Code with the Roo Code extension installed.
    *   Runtime environment for your chosen language (e.g., Node.js, Python interpreter).
    *   Build tools for your language if compilation is needed (e.g., `tsc`, `go build`, `cargo build`).
    *   Git command-line tool.

---

## 2. Recommended Libraries

While MCP servers can be built with standard libraries in many languages, certain libraries can simplify development, especially for handling JSON-RPC and stdio.

**Python:**

*   **JSON Handling:**
    *   `json` (Standard Library): Essential for parsing (`json.loads`) and serializing (`json.dumps`) JSON-RPC messages.
*   **Stdio Communication:**
    *   `sys` (Standard Library): Use `sys.stdin.readline()` to read incoming messages line by line and `sys.stdout.write()` followed by `sys.stdout.flush()` to send responses/notifications. Ensure output includes a trailing newline (`\n`).
*   **Environment Variables:**
    *   `os` (Standard Library): Access environment variables via `os.environ.get('VAR_NAME')`.
    *   `python-dotenv` ([PyPI](https://pypi.org/project/python-dotenv/)): Useful for loading variables from a `.env` file if Roo Code creates one (e.g., `load_dotenv()`).
*   **File System & Paths:**
    *   `os`, `pathlib` (Standard Library): For interacting with the file system (checking paths, reading/writing files if needed).
*   **Logging:**
    *   `logging` (Standard Library): Configure logging to output to `sys.stderr`. Roo Code typically captures stderr.
*   **Process Management:**
    *   `subprocess` (Standard Library): If your server needs to launch and manage child processes.
*   **Argument Parsing:**
    *   `argparse` (Standard Library): Useful for parsing command-line arguments, like the `stdio` flag Roo Code might pass.

**Node.js / TypeScript:**

*   **JSON-RPC & Stdio:**
    *   `vscode-jsonrpc` ([npm](https://www.npmjs.com/package/vscode-jsonrpc)): The standard library used by VS Code and many extensions for handling JSON-RPC communication over various transports, including stdio. Highly recommended. It simplifies message parsing, dispatching, and formatting.
    *   `readline` (Built-in Node.js): Can be used manually to read `process.stdin` line by line if not using `vscode-jsonrpc`.
*   **Environment Variables:**
    *   `process.env` (Built-in Node.js): Access environment variables directly (e.g., `process.env.VAR_NAME`).
    *   `dotenv` ([npm](https://www.npmjs.com/package/dotenv)): Standard library for loading variables from a `.env` file (e.g., `require('dotenv').config()`).
*   **File System & Paths:**
    *   `fs`, `path` (Built-in Node.js): Standard modules for file system operations and path manipulation. Use `fs.promises` for async operations.
*   **Logging:**
    *   `console.log`, `console.error` (Built-in Node.js): Direct output to `stdout` (for non-JSON-RPC info, use sparingly) or `stderr` (recommended for logs).
    *   `winston` ([npm](https://www.npmjs.com/package/winston)), `pino` ([npm](https://www.npmjs.com/package/pino)): Popular, more advanced logging libraries if structured logging is needed. Configure them to output to `stderr`.
*   **Process Management:**
    *   `child_process` (Built-in Node.js): For spawning and managing child processes (`spawn`, `exec`).
*   **Git Operations:**
    *   `simple-git` ([npm](https://www.npmjs.com/package/simple-git)): A convenient wrapper around the Git command line if your server needs to perform Git operations.

**General Tip:** When writing to `stdout`, ensure *only* valid, single-line JSON-RPC messages terminated by `\n` are sent. Use `stderr` for all other output like debugging logs.

---

## 3. Setting up the MCP Server (`roo.installMcp` Flow)

Roo Code discovers and manages MCP servers primarily through the `roo.installMcp` command. This command handles cloning the repository, installing dependencies, detecting the run command, and registering the server. Your server project needs to be structured to support this flow.

*   **Repository Structure:** Ensure your code is available in a Git repository (e.g., GitHub, GitLab).
*   **Manifest File (`mcp.json`):** This is crucial for discovery. Create an `mcp.json` file in the root of your repository. Roo Code reads this file after cloning.
    ```json
    // Example mcp.json
    {
      "name": "my-feature-server", // Unique identifier
      "version": "1.0.0",
      "displayName": "My Awesome Feature", // User-friendly name
      "description": "Provides awesome features via MCP.",
      "author": "Your Name <your.email@example.com>",
      "repository": {
        "type": "git",
        "url": "https://github.com/your-username/my-feature-server.git"
      },
      // How Roo Code should run your server
      "run": {
        // Attempt auto-detection first (based on package.json, etc.)
        // Explicit command if detection might fail or needs specifics:
        // "command": "node dist/main.js stdio",
        // "command": "python src/server.py stdio",
        // "command": "./my-feature-binary stdio"
      },
      // Environment variables required by your server
      "environment": [
        {
          "name": "API_KEY",
          "description": "API Key for accessing the awesome service.",
          "secret": true // Prompt user securely if true
        },
        {
          "name": "FEATURE_FLAG_X",
          "description": "Enable experimental feature X.",
          "secret": false,
          "default": "false"
        }
      ],
      // Define the tools your server provides
      "tools": [
        {
          "name": "do_something",
          "description": "Performs an awesome action.",
          "inputSchema": {
            "type": "object",
            "properties": {
              "param1": { "type": "string", "description": "First parameter." },
              "count": { "type": "number", "default": 1 }
            },
            "required": ["param1"]
          }
          // outputSchema can also be defined
        }
      ],
      // Define the resources your server provides
      "resources": [
        {
          "uri": "myfeature://data/{id}", // URI template
          "description": "Access specific data item by ID."
          // schema can also be defined
        }
      ],
      // Define contributions to the MCP Tab UI (Optional)
      "uiContributions": {
         "buttons": [
            {"id": "myfeature.refresh", "label": "Refresh Data"}
         ],
         "initialLayout": [ // Define elements to show on load
             {"type": "text", "content": "Welcome to My Feature!"},
             {"type": "button", "id": "myfeature.refresh"}
         ]
      }
    }
    ```
*   **Dependency Management:** Use standard dependency files for your language (`package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`). The `roo.installMcp` process will attempt to detect the project type and run the appropriate install command (`npm install`, `pip install`, `poetry install`, `go mod download`, `cargo build`).
*   **Build Steps:** If your server requires a build step (e.g., TypeScript compilation), ensure it's runnable via standard commands (e.g., `npm run build`). Roo Code may attempt to run common build scripts if source files are detected but distribution files are missing.
*   **Run Command Detection:** Roo Code attempts to detect the command needed to start your server in stdio mode. It checks:
    1.  The `run.command` field in `mcp.json`.
    2.  `package.json` scripts (`start:mcp`, `start`).
    3.  Common entry points (`main.js`, `index.js`, `main.py`, `app.py`, `main.go`, `src/main.rs`).
    It assumes the command should end with `stdio` to signal the communication mode. Ensure your server correctly handles this argument and starts its JSON-RPC stdio listener.
*   **Environment Variables:** Define required environment variables in `mcp.json`'s `environment` array. Roo Code will prompt the user for values during installation (using secure input for `secret: true`) and store them using VS Code's SecretStorage or a `.env` file within the server's installation directory. Your server should load these variables (e.g., using `dotenv` library or standard environment access).

---

## 4. MCP Communication (JSON-RPC over Stdio)

The core of the integration is the communication between Roo Code and your MCP server.

*   **Startup:** Roo Code launches your server process using the detected or specified `runCommand`. It passes required environment variables.
*   **Stdio:**
    *   Your server **MUST** read JSON-RPC 2.0 request objects from `stdin`.
    *   Your server **MUST** write JSON-RPC 2.0 response or notification objects to `stdout`. Each JSON object must be on a single line, terminated by a newline (`\n`).
    *   `stderr` can be used for logging. Roo Code often captures this and may display it in its own logs.
*   **JSON-RPC:**
    *   **Requests:** Roo Code sends requests to invoke tools or access resources defined in your `mcp.json`. Your server must handle these requests and send back a response (either success with a `result` or error with an `error` object).
        ```json
        // Request from Roo Code -> stdin
        {"jsonrpc": "2.0", "id": 1, "method": "use_tool", "params": {"tool_name": "do_something", "arguments": {"param1": "hello"}}}

        // Response from MCP Server -> stdout
        {"jsonrpc": "2.0", "id": 1, "result": {"message": "Action completed successfully!"}}
        // Or error response
        {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "Something went wrong", "data": { ... }}}
        ```
    *   **Notifications:** Either side can send notifications (requests without an `id`). These are for events or updates that don't require a direct response.
        ```json
        // Notification from MCP Server -> stdout (e.g., for logging or UI update)
        {"jsonrpc": "2.0", "method": "mcp/log", "params": {"level": "info", "message": "Processing data..."}}
        {"jsonrpc": "2.0", "method": "mcp/updateUI", "params": {"elements": [{"type": "text", "content": "Data refreshed!"}]}}
        ```
*   **Initialization (Optional):** You might define a specific initialization method (e.g., `initialize`) that Roo Code calls upon startup to exchange capabilities or configuration.
*   **Tool Invocation (`use_tool`):** Roo Code sends a request with `method: "use_tool"` and `params: {"tool_name": "...", "arguments": {...}}`. Your server executes the corresponding tool logic.
*   **Resource Access (`access_resource`):** Roo Code sends a request with `method: "access_resource"` and `params: {"uri": "..."}`. Your server resolves the URI and returns the resource content.

---

## 5. MCP Tab Integration & UI Interaction

Unlike general VS Code extensions that use the `vscode` API directly for UI, MCP servers interact with the user *indirectly* via the Roo Code MCP tab webview, orchestrated through JSON-RPC messages.

*   **Defining UI Elements:** Use the `uiContributions` section in `mcp.json` to define static elements (buttons, initial layout) that Roo Code should render when your server is active in the MCP tab.
*   **Dynamic UI Updates:** Your server can dynamically update the MCP tab UI by sending JSON-RPC notifications to Roo Code.
    *   **Method:** `mcp/updateUI`
    *   **Params:** An object describing the UI changes (e.g., `{ "elements": [...] }` where `elements` is an array of UI element descriptions like buttons, text blocks, input fields). Roo Code's webview receives this and re-renders accordingly.
*   **Requesting User Input:** Your server can request input from the user via the MCP tab.
    *   **Method:** `mcp/requestInput`
    *   **Params:** An object describing the input required (e.g., `{ "inputId": "uniqueId", "type": "text", "label": "Enter value:", "options": {...} }`).
    *   Roo Code renders the input element in the webview. When the user submits, the webview sends a message back to the extension, which forwards it to your server as a JSON-RPC request (e.g., `mcp/submitInput` with `params: {"inputId": "uniqueId", "value": "..."}`).
*   **Handling UI Actions:** When a user interacts with a UI element defined by your server (e.g., clicks a button), the Roo Code webview sends a message to the extension, which translates it into a JSON-RPC request to your server.
    *   **Method:** `mcp/uiAction` (Example)
    *   **Params:** An object identifying the action (e.g., `{ "actionId": "myfeature.refresh" }`).
    *   Your server handles this request and can respond or send `mcp/updateUI` notifications.

**Flow Example (Button Click):**

1.  User clicks "Refresh Data" button (defined via `uiContributions` or `mcp/updateUI`) in the MCP tab.
2.  MCP Tab Webview sends `postMessage` to Roo Code Extension: `{ command: 'mcpAction', payload: { serverName: 'my-feature-server', actionId: 'myfeature.refresh' } }`.
3.  Roo Code Extension sends JSON-RPC Request to MCP Server (`stdin`): `{"jsonrpc": "2.0", "id": 5, "method": "mcp/uiAction", "params": {"actionId": "myfeature.refresh"}}`.
4.  MCP Server receives request, performs refresh logic.
5.  MCP Server sends JSON-RPC Notification to Roo Code Extension (`stdout`): `{"jsonrpc": "2.0", "method": "mcp/updateUI", "params": {"elements": [{"type": "text", "content": "Data refreshed successfully at " + new Date()}]}}`.
6.  Roo Code Extension receives notification, sends `postMessage` to MCP Tab Webview: `{ command: 'updateUI', payload: { serverName: 'my-feature-server', elements: [...] } }`.
7.  MCP Tab Webview updates its display.

---

## 6. Configuration Management (Server Perspective)

Your MCP server needs access to configuration, including secrets provided by the user during installation.

*   **Environment Variables:** This is the primary mechanism. Roo Code will set environment variables for your server process based on:
    *   Values collected during `roo.installMcp` for variables defined in `mcp.json`.
    *   Values potentially stored in a `.env` file within the server's installation directory (Roo Code might manage this file).
    *   Your server should read these using standard methods for your language (e.g., `process.env` in Node.js, `os.environ` in Python). Use libraries like `dotenv` if Roo Code creates a `.env` file.
*   **Configuration Files:** Your server can read its own configuration files if needed, but rely on environment variables for secrets or settings Roo Code needs to manage.
*   **Initialization Parameters (Optional):** Roo Code could potentially pass configuration data as parameters during an initial `initialize` JSON-RPC call, if defined in the MCP specification used.

---

## 7. Logging (Server Perspective)

Effective logging is crucial for debugging.

*   **Stderr:** The simplest approach is to write log messages directly to `stderr`. Roo Code often captures `stderr` from MCP servers and makes it available through its own logging mechanisms (e.g., the "Roo Extension Logs" output channel or dedicated log files). Use clear, structured logging formats.
*   **JSON-RPC Logging:** A more integrated approach is to send log messages as JSON-RPC notifications to Roo Code.
    *   **Method:** `mcp/log`
    *   **Params:** `{ "level": "info" | "warn" | "error" | "debug", "message": "Log message content", "data": { ... } }` (optional structured data).
    *   Roo Code can then route these logs appropriately within the VS Code UI. This provides better visibility and filtering capabilities for the user.
*   **File Logging:** You can also log to files within your server's installation directory, but this makes logs less accessible through the Roo Code UI unless you also provide a tool/resource to retrieve them.

---

## 8. Testing

*   **Unit/Integration Testing:** Test your server's core logic and JSON-RPC handling independently. You can simulate `stdin` and check `stdout`/`stderr`. Use standard testing frameworks for your language.
*   **Manual Testing with Roo Code:**
    1.  Clone your server repository manually to a test location.
    2.  Install dependencies (`npm install`, `pip install`, etc.).
    3.  Build if necessary (`npm run build`).
    4.  Find the exact command to run your server in stdio mode (e.g., `node dist/main.js stdio`).
    5.  Launch VS Code with the Roo Code extension installed.
    6.  Use the `Roo: Add Local MCP Server (Development)` command (or similar if available) in Roo Code. Provide the path to your server's directory and the exact run command.
    7.  Interact with your server via the MCP tab and Roo Code commands (`use_mcp_tool`, `access_mcp_resource`).
    8.  Check Roo Code's output channels ("Roo Extension Logs", potentially a dedicated channel for your server's stderr) for logs and errors.
*   **Automated Testing with Roo Code (Advanced):** You could potentially use VS Code's extension testing framework (`@vscode/test-electron`) to launch an instance of VS Code with Roo Code, programmatically add your local server, and interact with it via VS Code commands, but this is complex.

---

## 9. Packaging and Distribution

*   **Git Repository:** The primary distribution method is via a Git repository installable with `roo.installMcp`. Ensure your `mcp.json` is accurate and dependencies/build steps work reliably.
*   **Versioning:** Use Git tags and update the `version` in `mcp.json` for different releases.
*   **Marketplace (Future?):** Currently, distribution is mainly via Git URLs or slugs. A dedicated marketplace or registry for Roo MCP servers might be a future possibility.

---

**Conclusion:**

Integrating a feature into the Roo Code MCP tab involves creating a standalone server process that communicates via JSON-RPC over stdio. By defining your server's capabilities, run command, and environment needs in `mcp.json`, and by handling JSON-RPC requests/notifications correctly (especially for UI interaction), you can seamlessly extend Roo Code's functionality. Remember to focus on the indirect UI interaction model mediated by Roo Code and its webview, rather than attempting direct VS Code API calls from your server process.