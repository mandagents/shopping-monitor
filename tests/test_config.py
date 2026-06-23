from src.config import load_config


def test_load_config_reads_products_list(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "products:\n"
        "  - name: 'Midea PortaSplit 3,5 kW'\n"
        '    ean: "4048164116478"\n'
        '    model_no: "10002085"\n'
        "    max_price_eur: 850\n"
        "    match_require_all: [portasplit]\n"
        "    match_require_any: ['12000']\n"
        "    match_exclude_any: [cool]\n"
        "  - name: 'Midea PortaSplit Cool 2,35 kW'\n"
        "    ean: ''\n"
        "    model_no: ''\n"
        "    max_price_eur: 850\n"
        "    match_require_all: [portasplit, cool]\n"
        "    match_require_any: ['2,35']\n"
        "    match_exclude_any: []\n"
        "sources_enabled: [idealo, toom]\n"
        "hamburg_pickup_priority: true\n"
        "health_fail_threshold: 3\n"
    )
    cfg = load_config(str(cfg_file))
    assert len(cfg.products) == 2
    p0 = cfg.products[0]
    assert p0.ean == "4048164116478"
    assert p0.max_price_eur == 850.0
    assert p0.match_exclude_any == ["cool"]
    assert p0.name == "Midea PortaSplit 3,5 kW"
    p1 = cfg.products[1]
    assert p1.ean == ""
    assert p1.max_price_eur == 850.0
    assert p1.match_require_all == ["portasplit", "cool"]
    assert cfg.sources_enabled == ["idealo", "toom"]
    assert cfg.health_fail_threshold == 3


def test_load_config_product_price_cap_is_per_product(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "products:\n"
        "  - name: 'A'\n"
        "    ean: '111'\n"
        "    model_no: ''\n"
        "    max_price_eur: 500\n"
        "    match_require_all: []\n"
        "    match_require_any: []\n"
        "    match_exclude_any: []\n"
        "  - name: 'B'\n"
        "    ean: '222'\n"
        "    model_no: ''\n"
        "    max_price_eur: 900\n"
        "    match_require_all: []\n"
        "    match_require_any: []\n"
        "    match_exclude_any: []\n"
        "sources_enabled: []\n"
        "hamburg_pickup_priority: false\n"
        "health_fail_threshold: 2\n"
    )
    cfg = load_config(str(cfg_file))
    assert cfg.products[0].max_price_eur == 500.0
    assert cfg.products[1].max_price_eur == 900.0
