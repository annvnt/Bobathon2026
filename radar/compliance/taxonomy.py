"""Substance synonym and CAS resolution against taxonomy.json."""

from __future__ import annotations

import json
import re
from functools import lru_cache

from radar.config import TAXONOMY_FILE

CAS_PATTERN = re.compile(r"\b(\d{1,7}-\d{2}-\d)\b")

CAS_TO_CANONICAL: dict[str, str] = {
    "7439-92-1": "lead",
    "7440-43-9": "cadmium",
    "7439-97-6": "mercury",
    "18540-29-9": "hexavalent_chromium",
    "117-81-7": "DEHP",
    "84-74-2": "DBP",
    "85-68-7": "BBP",
    "80-05-7": "BPA",
    "1163-19-5": "decaBDE",
    "79-94-7": "TBBPA",
}

SYNONYMS: dict[str, str] = {
    "lead": "lead",
    "pb": "lead",
    "blei": "lead",
    "plomb": "lead",
    "cadmium": "cadmium",
    "cd": "cadmium",
    "mercury": "mercury",
    "hg": "mercury",
    "quecksilber": "mercury",
    "hexavalent chromium": "hexavalent_chromium",
    "cr vi": "hexavalent_chromium",
    "dehp": "DEHP",
    "dbp": "DBP",
    "bbp": "BBP",
    "bpa": "BPA",
    "bisphenol a": "BPA",
    "mccp": "MCCP",
    "chlorinated paraffins": "MCCP",
    "pfhxa": "PFAS_PFHxA",
    "pfas": "PFAS_PFHxA",
    "deca-bde": "decaBDE",
    "tbbpa": "TBBPA",
}

FAMILY_KEYWORDS: dict[str, list[str]] = {
    "RoHS": ["rohs", "2011/65", "hazardous substances", "annex ii", "annex iv"],
    "REACH": ["reach", "1907/2006", "svhc", "annex xvii", "candidate list"],
    "Battery": ["battery", "batteries", "2023/1542", "battery passport", "batterie"],
    "PPWR": ["packaging", "ppwr", "2025/40", "verpackung"],
    "GPSR": ["product safety", "gpsr", "2023/988"],
    "RED": ["radio equipment", "2014/53", "common charger", "cybersecurity"],
    "WEEE": ["weee", "waste electrical", "elektrogesetz", "elektroG"],
    "POPs": ["persistent organic", "pops", "2019/1021"],
    "EnergyLabel": ["energy label", "eprel", "2017/1369"],
    "ESPR": ["ecodesign", "espr", "digital product passport", "2024/1781"],
    "ToySafety": ["toy safety", "2009/48"],
    "MDR": ["medical device", "2017/745"],
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "led_lighting": ["led", "luminaire", "lighting", "lamp"],
    "battery_pack": ["battery pack", "power bank", "power station"],
    "emobility_battery": ["lmt", "e-scooter", "e-bike", "light means of transport"],
    "toy_electronic": ["toy", "spielzeug"],
    "medical_wearable": ["medical", "body-worn", "in-vivo"],
    "cable": ["cable", "connector", "kabel"],
    "display": ["display", "monitor", "panel"],
    "wearable": ["wearable", "fitness"],
    "smart_home": ["smart home", "sensor", "hub", "camera"],
    "audio": ["speaker", "headphone", "audio"],
    "power_supply": ["charger", "power supply", "adapter"],
}


@lru_cache(maxsize=1)
def load_taxonomy() -> dict:
    return json.loads(TAXONOMY_FILE.read_text(encoding="utf-8"))


def canonical_substances() -> set[str]:
    return set(load_taxonomy().get("substances", {}))


def resolve_cas(text: str) -> set[str]:
    found: set[str] = set()
    for cas in CAS_PATTERN.findall(text):
        if cas in CAS_TO_CANONICAL:
            found.add(CAS_TO_CANONICAL[cas])
    return found


def resolve_substances(text: str) -> set[str]:
    """Resolve substance keys from free text; guards 'lead time' false positives."""
    lower = text.lower()
    found = resolve_cas(text)
    if re.search(r"\blead\s+(time|acid\s+battery|solder|content|alloy)\b", lower):
        found.add("lead")
    elif re.search(r"\b(lead|pb|blei)\b", lower) and "lead time" not in lower:
        if "lead" in canonical_substances():
            found.add("lead")
    for phrase, key in SYNONYMS.items():
        if phrase in lower and key in canonical_substances():
            found.add(key)
    return found


def detect_family(text: str) -> str:
    lower = text.lower()
    for family, keywords in FAMILY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return family
    return "REACH"


def detect_categories(text: str) -> list[str] | str:
    lower = text.lower()
    cats = [cat for cat, kws in CATEGORY_KEYWORDS.items() if any(kw in lower for kw in kws)]
    return cats if cats else "all"
