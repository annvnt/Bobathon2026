"""Ordered compliance action lists per regulation family (product plan §6.3)."""

from __future__ import annotations

from typing import Any

ACTION_LISTS: dict[str, dict[str, Any]] = {
    "Battery": {
        "applies_when": "has_battery = true AND battery sold in EU market",
        "deadline_note": "18 February 2027 for portable batteries; earlier for industrial",
        "steps": [
            {"step": 1, "action": "Confirm battery specifications: type, capacity (Wh), cell chemistry", "owner": "Product / R&D"},
            {"step": 2, "action": "Collect carbon footprint data per kWh across the battery lifecycle", "owner": "Supply chain"},
            {"step": 3, "action": "Collect recycled content data: cobalt, lithium, nickel, lead %", "owner": "Supply chain"},
            {"step": 4, "action": "Complete supply chain due diligence documentation", "owner": "Legal / procurement"},
            {"step": 5, "action": "Register product in EPREL (battery product group)", "owner": "Compliance manager"},
            {"step": 6, "action": "Generate Digital Product Passport record in EPREL", "owner": "Compliance / IT"},
            {"step": 7, "action": "Attach QR code to product and packaging before EU market placement", "owner": "Operations"},
            {"step": 8, "action": "Update technical file and Declaration of Conformity (DoC)", "owner": "Compliance manager"},
        ],
    },
    "RoHS": {
        "applies_when": "Electrical/electronic equipment sold in EU (non-purely-industrial)",
        "deadline_note": "In force now — no transition period for new products",
        "steps": [
            {"step": 1, "action": "Identify restricted substances: Pb, Hg, Cd, Cr6+, PBBs, PBDEs, DEHP, DBP, BBP, DIBP", "owner": "R&D / materials"},
            {"step": 2, "action": "Collect material declarations from all component suppliers", "owner": "Procurement"},
            {"step": 3, "action": "Check applicable exemptions (Annex III / IV) for your product category", "owner": "Compliance manager"},
            {"step": 4, "action": "Commission lab testing if supplier declarations insufficient", "owner": "Compliance manager"},
            {"step": 5, "action": "Compile technical documentation (keep 10 years)", "owner": "Compliance manager"},
            {"step": 6, "action": "Issue EU Declaration of Conformity", "owner": "Authorised representative"},
            {"step": 7, "action": "Apply CE marking", "owner": "Operations"},
        ],
    },
    "REACH": {
        "applies_when": "SVHC in substances[] above 0.1% w/w in any article",
        "deadline_note": "In force now — obligation at point of placing on market",
        "steps": [
            {"step": 1, "action": "Check current ECHA SVHC Candidate List for substances in product", "owner": "Compliance manager"},
            {"step": 2, "action": "Determine concentration of each SVHC in each article", "owner": "R&D / materials"},
            {"step": 3, "action": "If threshold exceeded: notify ECHA via SCIP database", "owner": "Compliance manager"},
            {"step": 4, "action": "Communicate SVHC presence to downstream users and consumers on request", "owner": "Sales"},
            {"step": 5, "action": "Evaluate substitution feasibility and document assessment", "owner": "R&D"},
            {"step": 6, "action": "Update product documentation and SDS if applicable", "owner": "Compliance manager"},
        ],
    },
    "GPSR": {
        "applies_when": "Consumer product sold in EU",
        "deadline_note": "GPSR in force since 13 December 2024",
        "steps": [
            {"step": 1, "action": "Conduct product risk assessment and document safety measures", "owner": "R&D / compliance"},
            {"step": 2, "action": "Appoint EU Authorised Representative if manufacturer is non-EU", "owner": "Legal"},
            {"step": 3, "action": "Register in Safety Gate portal if required for category", "owner": "Compliance manager"},
            {"step": 4, "action": "Establish internal market surveillance contact point", "owner": "Operations"},
            {"step": 5, "action": "Prepare technical file: risk assessment, tests, instructions", "owner": "Compliance manager"},
            {"step": 6, "action": "Apply GPSR-compliant labelling", "owner": "Operations"},
            {"step": 7, "action": "Establish complaints and recall procedure", "owner": "Operations"},
        ],
    },
    "WEEE": {
        "applies_when": "EEE category product sold in Germany (DE market)",
        "deadline_note": "Registration must precede first sale in Germany",
        "steps": [
            {"step": 1, "action": "Register as producer with Stiftung EAR", "owner": "Compliance / legal"},
            {"step": 2, "action": "Join an authorised WEEE take-back scheme", "owner": "Operations"},
            {"step": 3, "action": "Mark products with crossed-out wheelie bin symbol", "owner": "Operations / design"},
            {"step": 4, "action": "Report annual quantities to Stiftung EAR", "owner": "Compliance manager"},
            {"step": 5, "action": "Finance collection and recycling via take-back scheme", "owner": "Finance / operations"},
        ],
    },
    "PPWR": {
        "applies_when": "Product has packaging AND sold in EU",
        "deadline_note": "12 August 2026 for initial obligations",
        "steps": [
            {"step": 1, "action": "Classify packaging types: primary, secondary, transport", "owner": "Operations"},
            {"step": 2, "action": "Calculate recyclability rate for each packaging unit", "owner": "R&D / operations"},
            {"step": 3, "action": "Assess recycled content in plastic packaging", "owner": "Procurement"},
            {"step": 4, "action": "Evaluate packaging minimisation", "owner": "Design / operations"},
            {"step": 5, "action": "Register with national EPR scheme per EU market", "owner": "Compliance manager"},
            {"step": 6, "action": "Report annual packaging quantities per country", "owner": "Compliance manager"},
        ],
    },
}


def get_actions(family: str) -> dict[str, Any]:
    return ACTION_LISTS.get(family, {
        "applies_when": f"Product attributes match {family} scope",
        "deadline_note": "See source regulation for deadline",
        "steps": [
            {"step": 1, "action": f"Review {family} obligations for this product", "owner": "Compliance manager"},
            {"step": 2, "action": "Collect evidence and update technical file", "owner": "Compliance manager"},
            {"step": 3, "action": "Update Declaration of Conformity if required", "owner": "Compliance manager"},
        ],
    })
