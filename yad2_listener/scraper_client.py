"""Fetch URLs through a third-party scraping API.

Yad2 is behind Radware Bot Manager, which blocks datacenter IPs outright. A
scraping API routes the request through a residential (ideally Israeli) IP and
handles the anti-bot layer, returning the target's response body. This client
speaks to a few common providers, selected by the ``YAD2_SCRAPER`` env var.
"""

from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)


class ScraperClient:
    def __init__(
        self,
        provider: str,
        api_key: str,
        *,
        country: str = "il",
        render_js: bool = False,
        session: requests.Session | None = None,
    ):
        self.provider = provider
        self.api_key = api_key
        self.country = country
        self.render_js = render_js
        self.session = session or requests.Session()

    @classmethod
    def from_env(cls) -> "ScraperClient | None":
        """Build from env, or return None if no API key is configured."""
        api_key = os.environ.get("YAD2_SCRAPER_API_KEY", "").strip()
        if not api_key:
            return None
        return cls(
            provider=os.environ.get("YAD2_SCRAPER", "scrapingbee").strip().lower(),
            api_key=api_key,
            country=os.environ.get("YAD2_SCRAPER_COUNTRY", "il").strip() or "il",
            render_js=os.environ.get("YAD2_SCRAPER_RENDER_JS", "0").lower()
            in ("1", "true", "yes"),
        )

    def get(
        self,
        target_url: str,
        *,
        headers: dict | None = None,
        timeout: int = 70,
    ) -> requests.Response:
        """Fetch ``target_url`` through the provider. Returns the provider's
        HTTP response, whose body is the target's body."""
        if self.provider == "scrapingbee":
            params = {
                "api_key": self.api_key,
                "url": target_url,
                "render_js": "true" if self.render_js else "false",
                "premium_proxy": "true",
            }
            if self.country:
                params["country_code"] = self.country
            fwd = {}
            if headers:
                params["forward_headers"] = "true"
                fwd = {f"Spb-{k}": v for k, v in headers.items()}
            return self.session.get(
                "https://app.scrapingbee.com/api/v1/", params=params, headers=fwd, timeout=timeout
            )

        if self.provider == "zenrows":
            params = {"apikey": self.api_key, "url": target_url, "premium_proxy": "true"}
            if self.render_js:
                params["js_render"] = "true"
            if self.country:
                params["proxy_country"] = self.country
            fwd = {}
            if headers:
                params["custom_headers"] = "true"
                fwd = dict(headers)
            return self.session.get(
                "https://api.zenrows.com/v1/", params=params, headers=fwd, timeout=timeout
            )

        if self.provider == "scraperapi":
            params = {"api_key": self.api_key, "url": target_url, "premium": "true"}
            if self.render_js:
                params["render"] = "true"
            if self.country:
                params["country_code"] = self.country
            return self.session.get(
                "https://api.scraperapi.com/", params=params, headers=headers or {}, timeout=timeout
            )

        raise ValueError(
            f"Unknown YAD2_SCRAPER provider: {self.provider!r} "
            "(expected scrapingbee, zenrows, or scraperapi)"
        )
