from src.sources import SPECS, get_check, unknown_sources


def test_all_v1_jsonld_sources_present():
    for name in ["idealo", "hornbach", "obi", "bauhaus", "hagebau"]:
        assert name in SPECS
        assert SPECS[name].url.startswith("https://")


def test_idealo_uses_aggregate_price_mode():
    assert SPECS["idealo"].price_mode == "aggregate"
    assert SPECS["obi"].price_mode == "offer"


def test_get_check_returns_callable():
    check = get_check("obi")
    assert callable(check)


def test_unknown_sources_detects_typos():
    assert unknown_sources(["idealo", "toom", "obi"]) == []
    assert unknown_sources(["idealo", "nope"]) == ["nope"]


def test_ean_anchor_baked_into_no_url_secret():
    # URLs müssen die recon-verifizierten Produkt-IDs enthalten
    assert "204374464" in SPECS["idealo"].url
    assert "12356554" in SPECS["hornbach"].url
    assert "8620890" in SPECS["obi"].url
    assert "31934233" in SPECS["bauhaus"].url
    assert "1425543" in SPECS["hagebau"].url
