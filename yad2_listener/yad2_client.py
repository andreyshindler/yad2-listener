"""Fetch and parse listings from Yad2's feed API.

Yad2's website (www.yad2.co.il) is a front-end that reads from a JSON gateway
at gw.yad2.co.il. Given a normal search-page URL, ``build_feed_url`` derives the
matching gateway "feed" endpoint and forwards the search filters as query
params. ``parse_listings`` then normalizes the (frequently-changing) response
shapes into a flat list of :class:`Listing` objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlparse

import requests

GATEWAY = "https://gw.yad2.co.il/feed-search-legacy"

# Browser-like headers — the gateway sits behind Cloudflare and rejects
# requests that don't look like they came from the site.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://www.yad2.co.il",
    "Referer": "https://www.yad2.co.il/",
}


@dataclass(frozen=True)
class Listing:
    """A single normalized Yad2 listing."""

    id: str
    title: str
    price: str = ""
    location: str = ""
    url: str = ""
    image: str = ""
    extra: dict = field(default_factory=dict, compare=False)

    def summary(self) -> str:
        parts = [self.title or "(ללא כותרת)"]
        if self.price:
            parts.append(f"💰 {self.price}")
        if self.location:
            parts.append(f"📍 {self.location}")
        if self.url:
            parts.append(self.url)
        return "\n".join(parts)


def build_feed_url(search_url: str) -> str:
    """Translate a yad2.co.il search-page URL into the gateway feed URL.

    e.g. ``https://www.yad2.co.il/realestate/forsale?city=5000``
    ->   ``https://gw.yad2.co.il/feed-search-legacy/realestate/forsale?city=5000``
    """
    parsed = urlparse(search_url)

    if "gw.yad2.co.il" in parsed.netloc:
        # Already a gateway URL — use it as-is.
        return search_url

    path = parsed.path.strip("/")
    if not path:
        raise ValueError(f"Cannot determine Yad2 category from URL: {search_url!r}")

    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query = urlencode(params)
    feed_url = f"{GATEWAY}/{path}"
    if query:
        feed_url += f"?{query}"
    return feed_url


def fetch_listings(
    search_url: str,
    *,
    session: requests.Session | None = None,
    timeout: int = 20,
) -> list[Listing]:
    """Fetch the search and return normalized listings."""
    feed_url = build_feed_url(search_url)
    sess = session or requests.Session()
    response = sess.get(feed_url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    return parse_listings(response.json())


# --- Parsing -------------------------------------------------------------

def parse_listings(payload: Any) -> list[Listing]:
    """Normalize Yad2's JSON into a flat list of :class:`Listing`.

    Yad2 changes its response shape over time and between categories, so we
    dig out any embedded list of "item-like" dicts rather than hard-coding a
    single path.
    """
    listings: list[Listing] = []
    seen_ids: set[str] = set()

    for raw in _iter_item_dicts(payload):
        listing = _normalize_item(raw)
        if listing is None or listing.id in seen_ids:
            continue
        seen_ids.add(listing.id)
        listings.append(listing)

    return listings


# Keys that (when present in a dict) mark it as a candidate listing item.
_ID_KEYS = ("link_token", "token", "id", "orderId", "adNumber", "ad_number")


def _iter_item_dicts(node: Any) -> Iterable[dict]:
    """Recursively yield dicts that look like individual listing items."""
    if isinstance(node, dict):
        if _looks_like_item(node):
            yield node
            return  # don't descend into an item's own sub-objects
        for value in node.values():
            yield from _iter_item_dicts(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_item_dicts(value)


def _looks_like_item(node: dict) -> bool:
    has_id = any(node.get(key) for key in _ID_KEYS)
    has_content = any(
        key in node
        for key in ("price", "title_1", "title", "address", "row_1", "merchant")
    )
    return has_id and has_content


def _first(node: dict, *keys: str) -> str:
    for key in keys:
        value = node.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
    return ""


def _normalize_item(node: dict) -> Listing | None:
    item_id = _first(node, *_ID_KEYS)
    if not item_id:
        return None

    title = _first(node, "title_1", "title", "text", "row_1")
    subtitle = _first(node, "title_2", "row_2", "row_3")
    if subtitle and subtitle != title:
        title = f"{title} — {subtitle}".strip(" —")

    price = _first(node, "price", "priceLabel", "price_text")
    if price and price.replace(",", "").replace(".", "").isdigit():
        price = f"{price} ₪"

    location = _first(node, "address", "city", "neighborhood", "area")

    token = _first(node, "link_token", "token") or item_id
    url = _first(node, "url", "link") or f"https://www.yad2.co.il/item/{token}"
    if url.startswith("/"):
        url = f"https://www.yad2.co.il{url}"

    image = ""
    img = node.get("image") or node.get("img_url") or node.get("cover_image")
    if isinstance(img, str):
        image = img
    elif isinstance(node.get("images"), list) and node["images"]:
        first_img = node["images"][0]
        image = first_img if isinstance(first_img, str) else _first(first_img or {}, "src", "url")

    return Listing(
        id=str(item_id),
        title=title or "(ללא כותרת)",
        price=price,
        location=location,
        url=url,
        image=image,
        extra=node,
    )
