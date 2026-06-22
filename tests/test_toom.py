from src.sources.toom import parse

TOOM_HTML = """
<html><body>
<span class="price">699,00 €</span>
<script type="application/ld+json">
{"@type":"Product","name":"Midea Mobiles Klimagerät 'PortaSplit' 12000 BTU/h",
 "sku":"9350668","gtin13":"9350668",
 "offers":{"@type":"Offer","availability":"http://schema.org/OutOfStock","price":"799"}}
</script>
</body></html>
"""


def test_toom_uses_visible_price_not_jsonld_price():
    offer = parse(TOOM_HTML)
    assert offer.price == 699.0  # NICHT 799 aus dem JSON-LD
    assert offer.available is False
    assert offer.ean is None  # gtin13 ist unbrauchbar -> Name-Match


def test_toom_missing_availability_is_failure():
    html = '<script type="application/ld+json">{"@type":"Product","name":"x","offers":{"price":1}}</script>'
    assert parse(html) is None


def test_toom_no_product_is_failure():
    assert parse("<html><body>nichts</body></html>") is None


def test_toom_missing_visible_price_is_failure():
    html = (
        '<script type="application/ld+json">'
        '{"@type":"Product","name":"Midea PortaSplit 12000",'
        '"offers":{"@type":"Offer","availability":"http://schema.org/InStock","price":"799"}}'
        '</script>'
    )
    # InStock in JSON-LD but NO visible "xxx,xx €" on the page -> failure, not Offer(price=None)
    assert parse(html) is None
