# Understanding MCP Server Registration in Roo Code vs Cline

## Global vs Project MCP Configuration Files

**Global Settings:** Both Roo Code and Cline use a JSON config file in the extension’s storage to register MCP servers. Cline’s file is called **`cline_mcp_settings.json`**, while Roo Code uses effectively the same file often referenced as **`mcp_settings.json`**. For example, on Windows the file lives at:

```
%APPDATA%\Code\User\globalStorage\rooveterinaryinc.roo-cline\settings\cline_mcp_settings.json
```

**Project Settings:** Both editors support project-specific MCP configs that override or extend the global config. Roo Code (3.11+) introduced support for a **`.roo/mcp.json`** file in your project workspace. Project-level JSON entries take precedence or add to the global settings.

---

## JSON Structure for MCP Server Entries

The top-level JSON object must contain a **`"mcpServers"`** property, which is a dictionary of server entries:

```json
{
  "mcpServers": {
    "my-server": {
      // server configuration
    }
  }
}
```

### Local (STDIO) Servers

Required fields:

- `"command"` (string): Executable or command (e.g., `"python"` or `"bunx"`).
- `"args"` (array of strings): Arguments for the command, typically including the script path or package.
- `"env"` (object, optional): Environment variables.
- `"disabled"` (boolean, optional): If `false` (default), the server is active.
- `"alwaysAllow"` or `"autoApprove"` (array, optional): Tools to auto-approve.

**Example:**

```json
{
  "mcpServers": {
    "gitlab-mcp": {
      "command": "bunx",
      "args": ["@modelcontextprotocol/server-gitlab", "--port", "3000"],
      "env": {
        "GITLAB_TOKEN": "your-token-here"
      },
      "alwaysAllow": [],
      "disabled": false
    }
  }
}
```

### Remote (SSE/HTTP) Servers

Required fields:

- `"url"` (string): Endpoint for SSE stream.
- `"headers"` (object, optional): HTTP headers for connection.
- `"disabled"` (boolean, optional).
- `"alwaysAllow"`/`"autoApprove"` (array, optional).

**Example:**

```json
{
  "mcpServers": {
    "remote-server": {
      "url": "https://your-server-url.com/mcp",
      "headers": {
        "Authorization": "Bearer your-token"
      },
      "alwaysAllow": ["tool3"],
      "disabled": false
    }
  }
}
```

---

## Detection and Loading of MCP Servers

- **Automatic reload:** Cline’s marketplace applies changes immediately. Roo Code may require a **Reload Window**.
- **Process launch:** Local servers are spawned by the extension; remote connections are established automatically.
- **Error handling:** Roo Code 3.9.x had a bug where failed processes could disappear from the UI. Ensure the server runs successfully in a terminal first.
- **File naming:** Confirm you’re editing the correct file (`cline_mcp_settings.json` vs. `mcp_settings.json`).

---

## Differences Between Roo Code and Cline

- **Marketplace integration:** Cline automates cloning, building, and JSON updates. Roo Code relies on manual config edits.
- **Validation and errors:** Both require valid JSON. Cline might show errors immediately; Roo Code may need a restart.
- **Config file names:** Roo Code sometimes uses both names—use the built-in **Edit MCP Settings** command to ensure consistency.
- **Settings option:** There’s an “MCP Mode” setting in Cline to globally enable/disable MCP usage. Roo Code has a similar user-preference.

---

## Using Bunx Instead of NPX on Windows

Bunx is Bun’s equivalent of NPX, offering:

1. **Faster startup** (no Node cold boot).  
2. **Predictable path handling** on Windows.  
3. **Non-interactive installs** by default.

**Switching NPX → Bunx:**

```json
{
  "mcpServers": {
    "gitlab-mcp": {
      "command": "bunx",
      "args": ["@modelcontextprotocol/server-gitlab", "--port", "3000"],
      "env": {
        "GITLAB_TOKEN": "your-token-here"
      },
      "alwaysAllow": [],
      "disabled": false
    }
  }
}
```

To install Bun on Windows (PowerShell):

```powershell
iwr https://bun.sh/install | iex
```

After saving the updated JSON, reload Roo Code/VS Code to see the MCP listed and running.

---

*End of Guide*