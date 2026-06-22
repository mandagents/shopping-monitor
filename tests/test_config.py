from src.config import load_config


def test_load_config_reads_product_and_price(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "product:\n"
        '  ean: "4048164116478"\n'
        '  model_no: "10002085"\n'
        "  match_require_all: [portasplit]\n"
        "  match_require_any: ['12000']\n"
        "  match_exclude_any: [cool]\n"
        "max_price_eur: 850\n"
        "sources_enabled: [idealo, toom]\n"
        "hamburg_pickup_priority: true\n"
        "health_fail_threshold: 3\n"
    )
    cfg = load_config(str(cfg_file))
    assert cfg.product.ean == "4048164116478"
    assert cfg.max_price_eur == 850.0
    assert cfg.sources_enabled == ["idealo", "toom"]
    assert cfg.product.match_exclude_any == ["cool"]
    assert cfg.health_fail_threshold == 3
