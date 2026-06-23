from .base import SourceSpec, check_jsonld

SPECS: dict[str, SourceSpec] = {
    "idealo": SourceSpec(
        "idealo",
        "https://www.idealo.de/preisvergleich/OffersOfProduct/204374464_-portasplit-3-5-kw-midea.html",
        price_mode="aggregate",
    ),
    "hornbach": SourceSpec(
        "hornbach",
        "https://www.hornbach.de/p/klimasplitgeraet-midea-portasplit-12-000-btu-105-m-weiss/12356554/",
    ),
    "obi": SourceSpec(
        "obi",
        "https://www.obi.de/p/8620890/midea-mobile-split-klimaanlage-portasplit",
    ),
    "bauhaus": SourceSpec(
        "bauhaus",
        "https://www.bauhaus.info/klimaanlagen/midea-klimasplitgeraet-portasplit-12000-btu/p/31934233",
    ),
    "hagebau": SourceSpec(
        "hagebau",
        "https://www.hagebau.de/p/midea-klimaanlage-portasplit-12000-btu-anV1425543/",
    ),
}


KNOWN_SOURCES = set(SPECS) | {"toom", "obi_stores", "toom_stores", "bauhaus_stores", "aliexpress"}


def unknown_sources(names) -> list:
    return [n for n in names if n not in KNOWN_SOURCES]


def get_check(name: str):
    if name == "toom":
        from . import toom

        return toom.check
    if name == "obi_stores":
        from . import obi_stores

        return obi_stores.check
    if name == "toom_stores":
        from . import toom_stores

        return toom_stores.check
    if name == "bauhaus_stores":
        from . import bauhaus_stores

        return bauhaus_stores.check
    if name == "aliexpress":
        from . import aliexpress

        return aliexpress.check
    spec = SPECS[name]
    return lambda client: check_jsonld(client, spec)
