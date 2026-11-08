# scotlis-mcp

An MCP server exposing [ScotLIS](https://scotlis.ros.gov.uk) (Registers of Scotland) property price search as a tool Claude can call directly.

Given a UK postcode, it returns every registered title at that address with its sale date, price (or non-monetary reason, e.g. a gift between family members), and a link to the property summary.

Only covers Scotland, and only titles on the Land Register — older properties still on the Sasine Register may show no price.

## Data

Reads public ScotLIS listings for the postcode you give it and returns that result to Claude. Nothing is stored, logged, or sent anywhere else.

## Install as a Claude plugin

Search the plugin directory in Claude Code or on claude.ai for **ScotLIS Property Prices** and add it. This gives Claude the `search_property_prices` tool with no local setup.

## Install as a Claude Desktop extension (one click, macOS only for now)

Download `scotlis-mcp.mcpb` from the [latest release](https://github.com/Dart120/scotlis-mcp/releases/latest), then double-click it, drag it into the Claude Desktop window, or use **Settings > Extensions > Advanced settings > Install Extension…**. This bundle embeds its own Python 3.13 runtime, so it works even if your Mac's system Python is older.

## Add manually to an MCP client

Published on PyPI as [`scotlis-mcp`](https://pypi.org/project/scotlis-mcp/). With [uv](https://docs.astral.sh/uv/) installed, add this to your client's MCP server config:

```json
{
  "mcpServers": {
    "scotlis-prices": {
      "command": "uvx",
      "args": ["scotlis-mcp==1.0.0"]
    }
  }
}
```

## Use as a standalone CLI

From a checkout of this repository:

```bash
python3 scotlis_prices.py "EH1 1RE"
python3 scotlis_prices.py "EH1 1RE" --sort price --desc
python3 scotlis_prices.py "EH1 1RE" --format csv > prices.csv
python3 scotlis_prices.py "EH1 1RE" --format json
```

## Disclaimer

Unofficial tool, not affiliated with Registers of Scotland. Queries ScotLIS's public search form directly — be a good citizen and don't hammer it.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for building and packaging this project from source.
