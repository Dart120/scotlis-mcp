# scotlis-mcp

An MCP server exposing [ScotLIS](https://scotlis.ros.gov.uk) (Registers of Scotland) property price search as a tool Claude can call directly.

Given a UK postcode, it returns every registered title at that address with its sale date, price (or non-monetary reason, e.g. a gift between family members), and a link to the property summary.

Only covers Scotland, and only titles on the Land Register — older properties still on the Sasine Register may show no price.

## Use as a standalone CLI

```bash
python3 scotlis_prices.py "EH1 1RE"
python3 scotlis_prices.py "EH1 1RE" --sort price --desc
python3 scotlis_prices.py "EH1 1RE" --format csv > prices.csv
python3 scotlis_prices.py "EH1 1RE" --format json
```

## Use as an MCP server in Claude Desktop

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Dart120/scotlis-mcp.git
cd scotlis-mcp
uv sync
```

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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

Restart Claude Desktop, and Claude will be able to call `search_property_prices` for any UK postcode.

## Disclaimer

Unofficial tool, not affiliated with Registers of Scotland. Queries ScotLIS's public search form directly — be a good citizen and don't hammer it.
