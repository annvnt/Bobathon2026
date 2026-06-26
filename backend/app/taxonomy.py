"""Loads the controlled vocabulary (taxonomy.json) from the challenge dataset.

Falls back to a small built-in taxonomy if the dataset file is missing, so the
backend always boots.
"""
from __future__ import annotations

import json
from functools import lru_cache

from .config import settings

_FALLBACK = {
    "product_categories": {
        "led_lighting": "LED luminaires, lamps and strips",
        "power_supply": "External power supplies / chargers / adapters",
        "battery_pack": "Rechargeable battery packs, power banks, power stations",
        "audio": "Bluetooth/Wi-Fi speakers and headphones",
        "smart_home": "Smart-home sensors, hubs, cameras and controllers",
        "wearable": "Consumer wearables",
        "toy_electronic": "Toys containing electronics",
        "other": "Other electrical / electronic equipment",
    },
    "substances": {
        "lead": "Lead (Pb)",
        "cadmium": "Cadmium (Cd)",
        "mercury": "Mercury (Hg)",
        "DEHP": "Bis(2-ethylhexyl) phthalate",
    },
    "regulation_families": {
        "RoHS": "Directive 2011/65/EU",
        "REACH": "Regulation (EC) 1907/2006",
        "WEEE": "Directive 2012/19/EU",
        "Battery": "Regulation (EU) 2023/1542",
        "RED": "Directive 2014/53/EU",
        "GPSR": "Regulation (EU) 2023/988",
    },
    "markets_note": "ISO country codes; 'EU' expands to all 27 member states.",
}


@lru_cache
def get_taxonomy() -> dict:
    path = settings.dataset_dir / "taxonomy.json"
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return _FALLBACK


def categories() -> dict[str, str]:
    return get_taxonomy().get("product_categories", {})


def substances() -> dict[str, str]:
    return get_taxonomy().get("substances", {})


def regulation_families() -> dict[str, str]:
    return get_taxonomy().get("regulation_families", {})
