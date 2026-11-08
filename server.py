#!/usr/bin/env python3
"""MCP server exposing ScotLIS property-price search as tools for Claude Desktop.

Wraps scotlis_prices.py (the standalone CLI) so Claude can call it directly
instead of a human running it in a terminal.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from scotlis_prices import (
    ScotLISError,
    search_prices,
    sort_sales,
    normalise_postcode,
)

mcp = FastMCP("scotlis-prices")


@mcp.tool()
def search_property_prices(
    postcode: str,
    sort_by: str = "address",
    descending: bool = False,
) -> dict:
    """Search registered property sale prices in Scotland by postcode.

    Queries ScotLIS (Registers of Scotland's public land register) for every
    registered title at a postcode and returns, for each, the title number,
    address, sale date, and consideration (sale price, or a non-monetary
    reason such as a gift between family members).

    Only covers Scotland, and only titles on the Land Register (older
    properties still on the Sasine Register, or recently transferred for
    non-monetary consideration, may show no price).

    Args:
        postcode: A UK postcode, e.g. "EH1 1RE" (spacing/case don't matter).
        sort_by: One of "address", "date", "price". Defaults to "address".
        descending: Sort highest/latest/Z-first when true.

    Returns:
        A dict with the normalised postcode, result count, a list of sales
        (title_number, address, date, price, consideration, explanation,
        url), and summary stats (count with a price, median/min/max price)
        when at least one sale has a recorded price.
    """
    try:
        postcode_norm = normalise_postcode(postcode)
        sales = sort_sales(search_prices(postcode_norm), sort_by, descending)
    except ValueError as exc:
        return {"error": str(exc)}
    except ScotLISError as exc:
        return {"error": str(exc)}

    priced = sorted(s.price for s in sales if s.price is not None)
    summary = {}
    if priced:
        mid = len(priced) // 2
        median = priced[mid] if len(priced) % 2 else (priced[mid - 1] + priced[mid]) // 2
        summary = {
            "priced_count": len(priced),
            "median_price": median,
            "min_price": priced[0],
            "max_price": priced[-1],
        }

    return {
        "postcode": postcode_norm,
        "result_count": len(sales),
        "summary": summary,
        "sales": [s.as_dict() for s in sales],
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
