from bracket.utils.frontend_cache import IMMUTABLE, REVALIDATE, cache_control_for


def test_hashed_assets_are_cached_for_long() -> None:
    assert cache_control_for("assets/index-BxY12.js") == IMMUTABLE
    assert cache_control_for("assets/fonts/inter.woff2") == IMMUTABLE


def test_everything_else_is_revalidated() -> None:
    for path in [
        "",
        "index.html",
        "locales/nb/common.json",
        "favicon.svg",
        "assets",
        "assetsx/a.js",
    ]:
        assert cache_control_for(path) == REVALIDATE
