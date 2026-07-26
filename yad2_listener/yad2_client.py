"""Fetch and parse listings from Yad2's feed API.

Yad2's website (www.yad2.co.il) is a front-end that reads from a JSON gateway
at gw.yad2.co.il. Given a normal search-page URL, ``build_feed_url`` derives the
matching gateway "feed" endpoint and forwards the search filters as query
params. ``parse_listings`` then normalizes the (frequently-changing) response
shapes into a flat list of :class:`Listing` objects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlparse

log = logging.getLogger(__name__)

GW = "https://gw.yad2.co.il"

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


class Yad2FetchError(RuntimeError):
    """Raised when no gateway endpoint returned usable JSON."""


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


# Maps a search-page category path -> the modern gateway feed paths to try,
# in order. Yad2 retired the old ``feed-search-legacy`` endpoints in favor of
# per-domain feeds; we keep the legacy one last as a fallback.
_FEED_PATHS: dict[str, list[str]] = {
    "realestate/forsale": ["realestate-feed/forsale/map"],
    "realestate/rent": ["realestate-feed/rent/map"],
    "realestate/commercial": ["realestate-feed/commercial-forsale/map"],
    "vehicles/cars": ["vehicles-feed/cars"],
    "vehicles/motorcycles": ["vehicles-feed/motorcycles"],
    "products": ["products-feed"],
}


def candidate_feed_urls(search_url: str) -> list[str]:
    """Return the gateway feed URLs to try for a given search-page URL.

    The first that returns usable JSON wins. Yad2's endpoints change over
    time, so we try the modern per-domain feed(s) plus the legacy feed.
    """
    parsed = urlparse(search_url)

    if "gw.yad2.co.il" in parsed.netloc:
        return [search_url]  # already a gateway URL — use as-is

    path = parsed.path.strip("/")
    if not path:
        raise ValueError(f"Cannot determine Yad2 category from URL: {search_url!r}")

    query = urlencode(dict(parse_qsl(parsed.query, keep_blank_values=True)))

    feed_paths = list(_FEED_PATHS.get(path, []))
    feed_paths.append(f"feed-search-legacy/{path}")  # legacy fallback

    urls = []
    for feed_path in feed_paths:
        url = f"{GW}/{feed_path}"
        if query:
            url += f"?{query}"
        urls.append(url)
    return urls


# Backwards-compatible single-URL helper (first candidate).
def build_feed_url(search_url: str) -> str:
    return candidate_feed_urls(search_url)[0]


# Injected before any page script runs, to hide the tell-tale signs of an
# automated browser that Radware Bot Manager looks for.
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['he-IL', 'he', 'en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
const _query = window.navigator.permissions && window.navigator.permissions.query;
if (_query) {
  window.navigator.permissions.query = (p) => (
    p && p.name === 'notifications'
      ? Promise.resolve({state: Notification.permission})
      : _query(p)
  );
}
"""

_CHALLENGE_MARKERS = ("captcha", "radware", "bot manager", "just a moment", "attention required")


def _looks_like_challenge(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in _CHALLENGE_MARKERS)


def fetch_listings(
    search_url: str,
    *,
    timeout: int = 60,
    settle_ms: int = 6000,
    headless: bool | None = None,
    **_ignored: Any,
) -> list[Listing]:
    """Fetch listings by driving a real browser past Radware Bot Manager.

    Yad2 is guarded by Radware Bot Manager (a JavaScript bot challenge), so a
    plain HTTP client just receives the captcha page. We load the search page
    in Chromium (headful under Xvfb in Docker — far harder to fingerprint than
    headless), let the challenge resolve, and capture the JSON the page itself
    fetches from the ``gw.yad2.co.il`` gateway. Falls back to the SSR
    ``__NEXT_DATA__`` blob if no gateway JSON is seen.

    Raises :class:`Yad2FetchError` — with diagnostics — if no usable data.
    """
    import os

    # Imported lazily so the (heavy) dependency is only needed at fetch time.
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    if headless is None:
        headless = os.environ.get("YAD2_HEADLESS", "1").lower() not in ("0", "false", "no")

    payloads: list[Any] = []
    json_responses: list[str] = []  # any yad2 JSON seen (diagnostics)

    def on_response(response) -> None:
        try:
            content_type = response.headers.get("content-type", "")
            if "yad2.co.il" in response.url and "json" in content_type.lower():
                json_responses.append(response.url)
                if "gw.yad2.co.il" in response.url:
                    payloads.append(response.json())
        except Exception:  # a body we can't read is not worth crashing over
            pass

    final_title = final_url = ""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        try:
            context = browser.new_context(
                user_agent=DEFAULT_HEADERS["User-Agent"],
                locale="he-IL",
                timezone_id="Asia/Jerusalem",
                viewport={"width": 1366, "height": 900},
            )
            context.add_init_script(_STEALTH_JS)
            page = context.new_page()
            page.on("response", on_response)

            page.goto(search_url, wait_until="domcontentloaded", timeout=timeout * 1000)

            # Wait for the Radware challenge to clear: it auto-reloads into the
            # real page once its JS finishes, so poll the title until it stops
            # looking like a challenge (or we run out of patience).
            deadline_ms = 30000
            waited = 0
            while waited < deadline_ms and _looks_like_challenge(page.title()):
                page.wait_for_timeout(1000)
                waited += 1000

            try:
                page.wait_for_load_state("networkidle", timeout=timeout * 1000)
            except PlaywrightTimeout:
                pass  # some XHRs keep the connection warm; proceed anyway
            page.wait_for_timeout(settle_ms)  # let late XHRs land

            if not payloads:
                payloads.extend(_next_data_payloads(page))

            final_title = page.title()
            final_url = page.url
        finally:
            browser.close()

    listings: dict[str, Listing] = {}
    for payload in payloads:
        for item in parse_listings(payload):
            listings.setdefault(item.id, item)

    if not payloads:
        raise Yad2FetchError(
            "Browser loaded the page but captured no Yad2 gateway JSON. "
            f"headless={headless}, final_title={final_title!r}, final_url={final_url!r}, "
            f"looks_like_challenge={_looks_like_challenge(final_title)}, "
            f"yad2_json_responses_seen={len(json_responses)}. "
            "If looks_like_challenge is true, the bot challenge did not clear."
        )

    log.info("Captured %d gateway payload(s), %d listing(s)", len(payloads), len(listings))
    return list(listings.values())


def _next_data_payloads(page) -> list[Any]:
    """Fallback: pull the SSR __NEXT_DATA__ JSON embedded in the page."""
    import json

    try:
        element = page.query_selector("#__NEXT_DATA__")
        if element:
            return [json.loads(element.inner_text())]
    except Exception:
        pass
    return []


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
