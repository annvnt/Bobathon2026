"""Market / jurisdiction expansion — EU member states and delivery countries."""

from __future__ import annotations

# EU-27 ISO 3166-1 alpha-2 (2020+)
EU_MEMBER_STATES: tuple[str, ...] = (
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
)

EU_CODES = frozenset({"EU", "EEA", "EUR"})


def is_eu_member(country: str) -> bool:
    return country.upper() in EU_MEMBER_STATES


def countries_affected(country: str) -> list[str]:
    """Countries where a regulation with this jurisdiction applies."""
    code = country.upper()
    if code in EU_CODES:
        return list(EU_MEMBER_STATES)
    return [code]


def expand_jurisdictions(delivery_countries: list[str]) -> list[str]:
    """
    Expand delivery markets into regulation jurisdictions to search.

    Example: product shipped to Germany → EU-level law + DE national law.
    """
    jurisdictions: set[str] = set()
    for raw in delivery_countries:
        code = (raw or "").strip().upper()
        if not code:
            continue
        if code in EU_CODES:
            jurisdictions.add("EU")
            continue
        if is_eu_member(code):
            jurisdictions.update({"EU", code})
        else:
            jurisdictions.add(code)
    return sorted(jurisdictions)
