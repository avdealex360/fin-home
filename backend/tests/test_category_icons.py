"""Tabler icon names must exist in @tabler/icons-webfont@3.24.0 (see frontend/index.html)."""

from app.category_icons import CATEGORY_ICONS, _FALLBACK, _GROUP_DEFAULTS

# Subset verified against tabler-icons.min.css v3.24.0
VALID_TABLER_ICONS = {
    "ti-activity",
    "ti-arrow-down-circle",
    "ti-brand-netflix",
    "ti-briefcase",
    "ti-building-bank",
    "ti-car",
    "ti-cash",
    "ti-circle-plus",
    "ti-credit-card",
    "ti-device-tv",
    "ti-gift",
    "ti-hanger",
    "ti-heart-rate-monitor",
    "ti-home",
    "ti-inbox",
    "ti-paw",
    "ti-pig-money",
    "ti-receipt",
    "ti-shield",
    "ti-shopping-cart",
    "ti-sparkles",
    "ti-stethoscope",
    "ti-tag",
    "ti-tools-kitchen-2",
    "ti-wallet",
    "ti-wifi",
}


def _all_mapped_icons() -> set[str]:
    icons = {v["icon"] for v in CATEGORY_ICONS.values()}
    icons.update(v["icon"] for v in _GROUP_DEFAULTS.values())
    icons.add(_FALLBACK["icon"])
    return icons


def test_category_icons_use_valid_tabler_names():
    unknown = _all_mapped_icons() - VALID_TABLER_ICONS
    assert not unknown, f"Unknown Tabler icons: {sorted(unknown)}"
