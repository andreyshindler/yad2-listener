from yad2_listener.yad2_client import build_feed_url, parse_listings


def test_build_feed_url_from_search_page():
    url = build_feed_url("https://www.yad2.co.il/realestate/forsale?city=5000&rooms=3-4")
    assert url == (
        "https://gw.yad2.co.il/feed-search-legacy/realestate/forsale?city=5000&rooms=3-4"
    )


def test_build_feed_url_passthrough_for_gateway():
    gw = "https://gw.yad2.co.il/feed-search-legacy/vehicles/cars?manufacturer=19"
    assert build_feed_url(gw) == gw


def test_parse_legacy_feed_shape():
    payload = {
        "data": {
            "feed": {
                "feed_items": [
                    {
                        "id": "abc123",
                        "link_token": "abc123",
                        "title_1": "דירת 4 חדרים",
                        "title_2": "רחוב הרצל",
                        "price": "1,850,000",
                        "row_1": "תל אביב",
                    },
                    {"type": "banner"},  # non-listing noise, should be ignored
                ]
            }
        }
    }
    listings = parse_listings(payload)
    assert len(listings) == 1
    item = listings[0]
    assert item.id == "abc123"
    assert "דירת 4 חדרים" in item.title
    assert item.price == "1,850,000 ₪"
    assert item.url == "https://www.yad2.co.il/item/abc123"


def test_parse_deduplicates_by_id():
    payload = {
        "items": [
            {"id": "1", "title": "A", "price": "10"},
            {"id": "1", "title": "A dup", "price": "10"},
            {"id": "2", "title": "B", "price": "20"},
        ]
    }
    listings = parse_listings(payload)
    assert sorted(item.id for item in listings) == ["1", "2"]


def test_parse_empty_payload():
    assert parse_listings({}) == []
    assert parse_listings({"data": {"feed": {"feed_items": []}}}) == []
