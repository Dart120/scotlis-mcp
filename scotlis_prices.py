#!/usr/bin/env python3
"""Search Scottish property prices from ScotLIS (Registers of Scotland).

ScotLIS renders its results server-side with Next.js, so the search results are
embedded in the page as a JSON blob (``__NEXT_DATA__``). This script submits the
same query the public search form does and reads that blob, which avoids both
HTML scraping and a browser.

Usage:
    python3 scotlis_prices.py "EH1 1RE"
    python3 scotlis_prices.py "EH1 1RE" --sort price --desc
    python3 scotlis_prices.py "EH1 1RE" --format csv > prices.csv
    python3 scotlis_prices.py "EH1 1RE" --format json

Price searches are postcode-only; title numbers are not accepted by ScotLIS for
this search type.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Iterable

BASE_URL = "https://scotlis.ros.gov.uk"
RESULTS_URL = f"{BASE_URL}/results"
PROPERTY_URL = f"{BASE_URL}/property-summary/{{title}}"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# ScotLIS only populates the price/date fields when sortBy is one of these.
# Anything else (including "price") silently returns results with those fields
# stripped out, so we always request a safe value and sort locally.
_SAFE_SORT_BY = "address"

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
_POSTCODE_RE = re.compile(
    r"^(?P<out>[A-Z]{1,2}\d[A-Z\d]?)\s*(?P<in>\d[A-Z]{2})$", re.I
)
_PRICE_RE = re.compile(r"£\s*([\d,]+)")


class ScotLISError(RuntimeError):
    """Raised when ScotLIS cannot be queried or its response is unusable."""


@dataclass
class Sale:
    """One registered title and its most recent recorded consideration."""

    title_number: str
    address: str
    date: dt.date | None
    price: int | None
    consideration: str
    explanation: str | None
    url: str

    @property
    def price_display(self) -> str:
        return f"£{self.price:,}" if self.price is not None else "—"

    def as_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat() if self.date else None
        return d


def normalise_postcode(raw: str) -> str:
    """Return a postcode as ``EH1 1RE``, or raise ValueError."""
    compact = re.sub(r"\s+", "", raw.upper())
    m = _POSTCODE_RE.match(compact)
    if not m:
        raise ValueError(f"{raw!r} does not look like a UK postcode")
    return f"{m.group('out')} {m.group('in')}".upper()


def _fetch(url: str, timeout: float, retries: int) -> str:
    """GET a URL, retrying transient failures with a short backoff."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-GB,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:200]
            if exc.code in (403, 429) and "captcha" in body.lower():
                raise ScotLISError(
                    "ScotLIS served a CAPTCHA challenge (AWS WAF). Slow down or "
                    "run the search in a browser."
                ) from exc
            if exc.code < 500 and exc.code != 429:
                raise ScotLISError(f"ScotLIS returned HTTP {exc.code}: {body}") from exc
            last_error = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(2 ** attempt)
    raise ScotLISError(f"Could not reach ScotLIS: {last_error}")


def _extract_page_props(html: str) -> dict:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise ScotLISError(
            "No __NEXT_DATA__ block in the response — the ScotLIS page layout "
            "has probably changed."
        )
    try:
        return json.loads(m.group(1))["props"]["pageProps"]
    except (ValueError, KeyError) as exc:
        raise ScotLISError(f"Could not parse the ScotLIS page data: {exc}") from exc


def _parse_price(consideration: str | None) -> int | None:
    """Pull an integer out of '£340,000'; non-monetary entries return None."""
    if not consideration:
        return None
    m = _PRICE_RE.search(consideration)
    return int(m.group(1).replace(",", "")) if m else None


def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def _tidy_address(pretty: str, postcode: str) -> str:
    """ScotLIS prints the postcode unspaced ('EH11RE') at the end; fix that."""
    compact = postcode.replace(" ", "")
    if pretty.upper().endswith(compact):
        return pretty[: -len(compact)] + postcode
    return pretty


def search_prices(
    postcode: str, *, timeout: float = 30.0, retries: int = 2
) -> list[Sale]:
    """Return the registered sales ScotLIS holds for a postcode."""
    postcode = normalise_postcode(postcode)
    query = urllib.parse.urlencode(
        {
            "searchType": "prices",
            "postcode": postcode,
            "sortBy": _SAFE_SORT_BY,
            "sortDir": "asc",
        }
    )
    props = _extract_page_props(_fetch(f"{RESULTS_URL}?{query}", timeout, retries))

    sales = []
    for entry in props.get("addresses") or []:
        title = entry.get("titleNumber", "")
        consideration = entry.get("consideration") or "No price available"
        sales.append(
            Sale(
                title_number=title,
                address=_tidy_address(entry.get("prettyPrint", ""), postcode),
                date=_parse_date(entry.get("entryDate")),
                price=_parse_price(consideration),
                consideration=consideration,
                explanation=entry.get("considerationExplanation"),
                url=PROPERTY_URL.format(title=title),
            )
        )
    return sales


def sort_sales(sales: list[Sale], key: str, descending: bool) -> list[Sale]:
    """Sort locally — ScotLIS returns results in a fixed order regardless of sortBy."""
    # Rows with no price or date sort last in either direction.
    if key == "price":
        ranked = sorted(
            (s for s in sales if s.price is not None),
            key=lambda s: s.price,
            reverse=descending,
        )
        return ranked + [s for s in sales if s.price is None]
    if key == "date":
        ranked = sorted(
            (s for s in sales if s.date is not None),
            key=lambda s: s.date,
            reverse=descending,
        )
        return ranked + [s for s in sales if s.date is None]
    return sorted(sales, key=lambda s: s.address, reverse=descending)


def print_table(sales: Iterable[Sale], postcode: str) -> None:
    sales = list(sales)
    priced = [s.price for s in sales if s.price is not None]
    addr_width = min(max((len(s.address) for s in sales), default=10), 60)

    print(f"\n{len(sales)} result(s) for {postcode}\n")
    header = f"{'DATE':<12} {'PRICE':>10}  {'TITLE':<10} ADDRESS"
    print(header)
    print("-" * (len(header) + addr_width - 7))
    for s in sales:
        date = s.date.strftime("%d %b %Y") if s.date else "—"
        # Non-monetary considerations are free text, so they trail the address
        # rather than blowing out the price column.
        note = f"  · {s.consideration}" if s.price is None else ""
        print(f"{date:<12} {s.price_display:>10}  {s.title_number:<10} {s.address}{note}")

    if priced:
        priced.sort()
        mid = len(priced) // 2
        median = priced[mid] if len(priced) % 2 else (priced[mid - 1] + priced[mid]) // 2
        print(
            f"\n{len(priced)} with a recorded price — "
            f"median £{median:,}, range £{min(priced):,}–£{max(priced):,}"
        )
    unpriced = len(sales) - len(priced)
    if unpriced:
        print(f"{unpriced} without a monetary price (gifts, transfers, pre-2003 titles).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Search property prices on ScotLIS by postcode."
    )
    parser.add_argument("postcode", help="e.g. 'EH1 1RE'")
    parser.add_argument(
        "--sort", choices=("address", "date", "price"), default="address"
    )
    parser.add_argument("--desc", action="store_true", help="sort descending")
    parser.add_argument(
        "--format", choices=("table", "json", "csv"), default="table"
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    try:
        postcode = normalise_postcode(args.postcode)
        sales = sort_sales(search_prices(postcode, timeout=args.timeout), args.sort, args.desc)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ScotLISError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not sales:
        print(
            f"No registered titles found for {postcode}. ScotLIS only covers "
            "Scotland, and only properties on the Land Register.",
            file=sys.stderr,
        )
        return 0

    if args.format == "json":
        json.dump([s.as_dict() for s in sales], sys.stdout, indent=2)
        print()
    elif args.format == "csv":
        writer = csv.DictWriter(
            sys.stdout,
            fieldnames=["title_number", "address", "date", "price", "consideration", "explanation", "url"],
        )
        writer.writeheader()
        writer.writerows(s.as_dict() for s in sales)
    else:
        print_table(sales, postcode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
