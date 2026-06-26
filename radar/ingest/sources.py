"""Source registry aligned with Dataset/SOURCES.md."""

from __future__ import annotations

# Maps regulation families to preferred live sources (see SOURCES.md quick map).
FAMILY_SOURCES: dict[str, list[str]] = {
    "RoHS": ["EUR-Lex", "ECHA"],
    "REACH": ["EUR-Lex", "ECHA"],
    "POPs": ["EUR-Lex", "ECHA"],
    "CLP": ["EUR-Lex", "ECHA"],
    "Battery": ["EUR-Lex", "OpenLegalData", "Bundestag"],
    "PPWR": ["EUR-Lex", "Bundestag"],
    "GPSR": ["EUR-Lex", "SafetyGate"],
    "RED": ["EUR-Lex", "HarmonisedStandards"],
    "EMC": ["EUR-Lex", "HarmonisedStandards"],
    "LVD": ["EUR-Lex", "HarmonisedStandards"],
    "ESPR": ["EUR-Lex", "EPREL"],
    "EnergyLabel": ["EPREL", "EUR-Lex"],
    "WEEE": ["EUR-Lex", "OpenLegalData", "Bundestag"],
    "ToySafety": ["EUR-Lex"],
    "MDR": ["EUR-Lex"],
}

# Active connectors for Core tier (live APIs + local ECHA lists + OJ RSS).
ACTIVE_CONNECTORS = ("EUR-Lex", "EU Official Journal", "Bundestag", "OpenLegalData", "ECHA")

SOURCE_META: dict[str, dict[str, str]] = {
    "EUR-Lex": {
        "url": "https://eur-lex.europa.eu",
        "description": "EU legal texts — RoHS, REACH, Battery Reg, PPWR, GPSR, RED",
    },
    "EU Official Journal": {
        "url": "https://eur-lex.europa.eu/oj",
        "description": "Daily OJ L/C RSS — new acts, corrigenda and amendments",
    },
    "ECHA": {
        "url": "https://echa.europa.eu",
        "description": "SVHC Candidate List, Annex XVII restrictions (local XLSX in ECHA/)",
    },
    "Bundestag": {
        "url": "https://search.dip.bundestag.de",
        "description": "German parliamentary legislative process (DIP API)",
    },
    "OpenLegalData": {
        "url": "https://de.openlegaldata.io",
        "description": "Open Legal Data — German laws and case law (REST API)",
    },
    "EPREL": {
        "url": "https://eprel.ec.europa.eu",
        "description": "EU energy-label database (stretch)",
    },
    "SafetyGate": {
        "url": "https://ec.europa.eu/safety-gate-alerts",
        "description": "Product safety recalls (stretch)",
    },
}

EURLEX_SEARCH_TERMS = [
    "REACH",
    "RoHS",
    "battery",
    "packaging",
    "radio equipment",
    "2023/1542",
    "2011/65",
]

DIP_SEARCH_TERMS = ["Elektrogesetz", "Batterie", "Verpackung", "Batterierecht"]

OLDP_SEARCH_TERMS = ["Batterie", "Elektro", "Elektrogesetz", "Abfall", "Verpackung", "Batteriegesetz"]
