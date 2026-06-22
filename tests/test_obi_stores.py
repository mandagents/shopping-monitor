"""TDD tests for the obi_stores source (Hamburg store-level pickup availability)."""
import pytest

from src.sources.obi_stores import parse_stock

# The real all-zero response shape (10 Hamburg-area stores, all qty=0)
REAL_ALL_ZERO = [
    {"storeId": "281", "availableQuantity": 0},
    {"storeId": "497", "availableQuantity": 0},
    {"storeId": "420", "availableQuantity": 0},
    {"storeId": "040", "availableQuantity": 0},
    {"storeId": "483", "availableQuantity": 0},
    {"storeId": "443", "availableQuantity": 0},
    {"storeId": "377", "availableQuantity": 0},
    {"storeId": "545", "availableQuantity": 0},
    {"storeId": "253", "availableQuantity": 0},
    {"storeId": "569", "availableQuantity": 0},
]


def test_all_zero_returns_empty_list():
    """Real current state: all Hamburg stores qty=0 → no in-stock stores."""
    result = parse_stock(REAL_ALL_ZERO)
    assert result == []


def test_one_store_available_returns_that_store_id():
    """Synthetic: one store has qty=2 → its ID is in the result."""
    data = [
        {"storeId": "281", "availableQuantity": 0},
        {"storeId": "497", "availableQuantity": 2},
        {"storeId": "420", "availableQuantity": 0},
    ]
    result = parse_stock(data)
    assert result == ["497"]


def test_multiple_stores_available():
    data = [
        {"storeId": "281", "availableQuantity": 3},
        {"storeId": "497", "availableQuantity": 0},
        {"storeId": "420", "availableQuantity": 1},
    ]
    result = parse_stock(data)
    assert "281" in result
    assert "420" in result
    assert "497" not in result
    assert len(result) == 2


# --- Anti-silent-failure guard: malformed inputs must raise ValueError ---

def test_empty_list_raises_value_error():
    """Empty list is not a valid stock response (would silently suppress alerts)."""
    with pytest.raises(ValueError):
        parse_stock([])


def test_dict_instead_of_list_raises_value_error():
    """API returning a dict instead of a list must raise."""
    with pytest.raises(ValueError):
        parse_stock({"storeId": "281", "availableQuantity": 0})  # type: ignore[arg-type]


def test_missing_available_quantity_key_raises_value_error():
    """Entries without availableQuantity key must raise (format change guard)."""
    with pytest.raises(ValueError):
        parse_stock([{"storeId": "281"}])


def test_non_dict_entries_raise_value_error():
    """List entries that are not dicts must raise."""
    with pytest.raises(ValueError):
        parse_stock(["281", "497"])  # type: ignore[arg-type]


# --- check() integration: test with a fake HTTP client ---

class _FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json

    @property
    def text(self):
        # Minimal HTML with JSON-LD for the product page fetch (price extraction)
        return """<html><body>
<script type="application/ld+json">
{"@type":"Product","name":"Midea PortaSplit","gtin13":"4048164116478",
 "offers":{"@type":"Offer","availability":"http://schema.org/InStoreOnly","price":"799.99"}}
</script>
</body></html>"""


class _FakeClient:
    def __init__(self, stock_data):
        self._stock_data = stock_data
        self._call_count = 0

    def get(self, url, **kwargs):
        self._call_count += 1
        if "stock" in url:
            return _FakeResponse(self._stock_data)
        # Product page fetch (for price via JSON-LD)
        return _FakeResponse(None)  # will use .text


class _FakeClientWithPage:
    """Fake client that returns stock JSON for stock URL and HTML for product page."""

    PRODUCT_HTML = """<html><body>
<script type="application/ld+json">
{"@type":"Product","name":"Midea PortaSplit","gtin13":"4048164116478",
 "offers":{"@type":"Offer","availability":"http://schema.org/InStoreOnly","price":"799.99"}}
</script>
</body></html>"""

    def __init__(self, stock_data):
        self._stock_data = stock_data

    def get(self, url, **kwargs):
        if "stock" in url:
            return _StockResponse(self._stock_data)
        return _PageResponse(self.PRODUCT_HTML)


class _StockResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _PageResponse:
    def __init__(self, html):
        self.text = html

    def raise_for_status(self):
        pass

    def json(self):
        return {}


def test_check_not_available_when_all_zero():
    """check() with all-zero stock returns Offer(available=False)."""
    from src.sources.obi_stores import check

    client = _FakeClientWithPage(REAL_ALL_ZERO)
    offer = check(client)
    assert offer is not None
    assert offer.available is False
    assert offer.pickup_only is True
    assert offer.ean == "4048164116478"
    assert offer.source == "obi_stores"


def test_check_available_when_store_has_stock():
    """check() with one store in stock returns Offer(available=True)."""
    from src.sources.obi_stores import check

    in_stock_data = [
        {"storeId": "281", "availableQuantity": 5},
        {"storeId": "497", "availableQuantity": 0},
    ]
    client = _FakeClientWithPage(in_stock_data)
    offer = check(client)
    assert offer is not None
    assert offer.available is True
    assert "1 Markt" in offer.title or "1" in offer.title


def test_check_price_extracted_from_page():
    """check() extracts price from the product page JSON-LD."""
    from src.sources.obi_stores import check

    client = _FakeClientWithPage(REAL_ALL_ZERO)
    offer = check(client)
    assert offer is not None
    assert offer.price == 799.99
