from src.jsonld import (
    availability_state,
    extract_jsonld,
    find_product,
    first_offer,
    offer_price,
)

OBI_HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Midea PortaSplit",
 "gtin13":"4048164116478",
 "offers":{"@type":"Offer","availability":"http://schema.org/InStoreOnly","price":799.99,"priceCurrency":"EUR"}}
</script></head><body></body></html>
"""

IDEALO_HTML = """
<script type="application/ld+json">
{"@type":"Product","name":"Midea PortaSplit 3,5 kW","gtin13":"4048164116478",
 "offers":{"@type":"AggregateOffer","lowPrice":999,"highPrice":1049,"offerCount":2,
 "availability":"https://schema.org/InStock"}}
</script>
"""


def test_find_product_and_offer_fields():
    product = find_product(extract_jsonld(OBI_HTML))
    assert product["gtin13"] == "4048164116478"
    offer = first_offer(product)
    assert offer_price(offer, "offer") == 799.99


def test_aggregate_offer_uses_low_price():
    product = find_product(extract_jsonld(IDEALO_HTML))
    assert offer_price(first_offer(product), "aggregate") == 999.0


def test_availability_state_mapping():
    assert availability_state("https://schema.org/InStock") == (True, False)
    assert availability_state("http://schema.org/InStoreOnly") == (True, True)
    assert availability_state("https://schema.org/OutOfStock") == (False, False)
    assert availability_state(None) == (False, False)


def test_availability_limited_availability_is_available():
    from src.jsonld import availability_state
    assert availability_state("https://schema.org/LimitedAvailability") == (True, False)


def test_find_product_handles_graph_and_type_list():
    from src.jsonld import extract_jsonld, find_product
    html = (
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@graph":['
        '{"@type":"BreadcrumbList"},'
        '{"@type":["Product","IndividualProduct"],"name":"Midea PortaSplit","gtin13":"4048164116478"}'
        ']}</script>'
    )
    product = find_product(extract_jsonld(html))
    assert product is not None
    assert product["gtin13"] == "4048164116478"
