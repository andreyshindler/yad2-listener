import json

import pytest

from yad2_listener import yad2_client
from yad2_listener.scraper_client import ScraperClient


def test_from_env_none_without_key(monkeypatch):
    monkeypatch.delenv("YAD2_SCRAPER_API_KEY", raising=False)
    assert ScraperClient.from_env() is None


def test_from_env_builds_with_key(monkeypatch):
    monkeypatch.setenv("YAD2_SCRAPER_API_KEY", "k")
    monkeypatch.setenv("YAD2_SCRAPER", "zenrows")
    client = ScraperClient.from_env()
    assert client is not None
    assert client.provider == "zenrows"
    assert client.country == "il"


class _FakeResp:
    status_code = 200
    text = json.dumps(
        {"data": {"feed": {"feed_items": [
            {"id": "9", "link_token": "t9", "title_1": "בדיקה", "price": "1000", "row_1": "תל אביב"}
        ]}}}
    )

    def json(self):
        return json.loads(self.text)


def test_fetch_listings_uses_scraper_when_configured(monkeypatch):
    monkeypatch.setenv("YAD2_SCRAPER_API_KEY", "k")
    monkeypatch.setenv("YAD2_SCRAPER", "scrapingbee")

    calls = {}

    def fake_get(self, url, headers=None, timeout=70):
        calls["url"] = url
        return _FakeResp()

    monkeypatch.setattr(ScraperClient, "get", fake_get)

    items = yad2_client.fetch_listings("https://www.yad2.co.il/realestate/forsale?city=5000")
    assert calls["url"] == "https://gw.yad2.co.il/realestate-feed/forsale/map?city=5000"
    assert [i.id for i in items] == ["t9"]


def test_scraper_raises_on_non_json(monkeypatch):
    monkeypatch.setenv("YAD2_SCRAPER_API_KEY", "k")

    class _HtmlResp:
        status_code = 200
        text = "<html>blocked</html>"

        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(ScraperClient, "get", lambda self, url, headers=None, timeout=70: _HtmlResp())

    with pytest.raises(yad2_client.Yad2FetchError):
        yad2_client.fetch_listings("https://www.yad2.co.il/realestate/forsale?city=5000")
