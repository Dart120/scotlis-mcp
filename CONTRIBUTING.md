# Developing scotlis-mcp

## Setup

Clone the repository, then install dependencies with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

## Run the MCP server locally

```bash
uv run server.py
```

Point a client at it with:

```json
{
  "mcpServers": {
    "scotlis-prices": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/scotlis-mcp", "run", "server.py"]
    }
  }
}
```

## Build the Claude Desktop extension (.mcpb)

```bash
npm install -g @anthropic-ai/mcpb
cp -R .venv venv   # bundles a real, self-contained interpreter — not a symlink
mcpb pack . scotlis-mcp.mcpb
```

## Publish to PyPI

```bash
uv build
uv publish
```

## Plugin

`.claude-plugin/plugin.json` and `.mcp.json` at the repository root make this a Claude plugin. The MCP server launches via `uv run --locked`, pinned against the committed `uv.lock`.
