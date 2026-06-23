from src.sources import SPECS, get_check, unknown_sources


def test_all_v1_jsonld_sources_present():
    # hornbach is now a Playwright source, not a JSON-LD SPEC entry.
    for name in ["idealo", "obi", "bauhaus", "hagebau"]:
        assert name in SPECS
        assert SPECS[name].url.startswith("https://")


def test_hornbach_is_playwright_not_spec():
    """Hornbach moved from SPECS to a dedicated Playwright module."""
    assert "hornbach" not in SPECS, (
        "hornbach must NOT be in SPECS — it would route to the old httpx path"
    )
    fn = get_check("hornbach")
    assert callable(fn)
    from src.sources import hornbach
    assert fn is hornbach.check


def test_idealo_uses_aggregate_price_mode():
    assert SPECS["idealo"].price_mode == "aggregate"
    assert SPECS["obi"].price_mode == "offer"


def test_get_check_returns_callable():
    check = get_check("obi")
    assert callable(check)


def test_unknown_sources_detects_typos():
    assert unknown_sources(["idealo", "toom", "obi"]) == []
    assert unknown_sources(["idealo", "nope"]) == ["nope"]


def test_hornbach_in_known_sources():
    from src.sources import KNOWN_SOURCES
    assert "hornbach" in KNOWN_SOURCES
    assert unknown_sources(["hornbach"]) == []


def test_ean_anchor_baked_into_no_url_secret():
    # URLs müssen die recon-verifizierten Produkt-IDs enthalten
    assert "204374464" in SPECS["idealo"].url
    # hornbach URL lives in hornbach.py, not SPECS
    from src.sources.hornbach import URL as HORNBACH_URL
    assert "12356554" in HORNBACH_URL
    assert "8620890" in SPECS["obi"].url
    assert "31934233" in SPECS["bauhaus"].url
    assert "1425543" in SPECS["hagebau"].url
