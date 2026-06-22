from src.sources.base import SourceSpec, parse_jsonld_source

OBI_INSTOREONLY = """
<script type="application/ld+json">
{"@type":"Product","name":"Midea PortaSplit","gtin13":"4048164116478",
 "offers":{"@type":"Offer","availability":"http://schema.org/InStoreOnly","price":799.99}}
</script>
"""

BAUHAUS_OOS = """
<script type="application/ld+json">
{"@type":"Product","name":"Midea Klimasplitgerät PortaSplit 12.000 Btu","gtin13":"4048164116478",
 "offers":{"@type":"Offer","availability":"https://schema.org/OutOfStock","price":"749.00"}}
</script>
"""

NO_AVAILABILITY = """
<script type="application/ld+json">
{"@type":"Product","name":"Midea PortaSplit","gtin13":"4048164116478",
 "offers":{"@type":"Offer","price":749.0}}
</script>
"""


def test_instoreonly_is_not_treated_as_available():
    # InStoreOnly is an unreliable static catalog flag for some retailers
    # (OBI, Hagebau emit it even when sold out) -> must NOT count as available,
    # otherwise the bot sends false-positive alerts.
    spec = SourceSpec("obi", "https://obi.example/p/8620890")
    offer = parse_jsonld_source(OBI_INSTOREONLY, spec)
    assert offer is not None  # still parses (price/ean), just not available
    assert offer.available is False
    assert offer.price == 799.99
    assert offer.ean == "4048164116478"
    assert offer.url == "https://obi.example/p/8620890"


def test_parse_out_of_stock_offer():
    spec = SourceSpec("bauhaus", "https://bauhaus.example/p/31934233")
    offer = parse_jsonld_source(BAUHAUS_OOS, spec)
    assert offer.available is False
    assert offer.price == 749.0


def test_missing_availability_is_failure():
    spec = SourceSpec("hornbach", "https://hornbach.example/p/12356554")
    assert parse_jsonld_source(NO_AVAILABILITY, spec) is None


def test_no_product_is_failure():
    spec = SourceSpec("x", "https://x.example")
    assert parse_jsonld_source("<html></html>", spec) is None


def test_aggregate_price_mode_uses_low_price():
    spec = SourceSpec("idealo", "https://idealo.example/p/204374464", price_mode="aggregate")
    html = (
        '<script type="application/ld+json">'
        '{"@type":"Product","name":"Midea PortaSplit 3,5 kW","gtin13":"4048164116478",'
        '"offers":{"@type":"AggregateOffer","lowPrice":749,"highPrice":999,'
        '"availability":"https://schema.org/InStock"}}</script>'
    )
    offer = parse_jsonld_source(html, spec)
    assert offer.available is True
    assert offer.price == 749.0


def test_trust_ean_false_drops_ean():
    spec = SourceSpec("toomlike", "https://x.example/p", trust_ean=False)
    html = (
        '<script type="application/ld+json">'
        '{"@type":"Product","name":"Midea PortaSplit","gtin13":"4048164116478",'
        '"offers":{"@type":"Offer","availability":"https://schema.org/InStock","price":699}}</script>'
    )
    offer = parse_jsonld_source(html, spec)
    assert offer.ean is None
