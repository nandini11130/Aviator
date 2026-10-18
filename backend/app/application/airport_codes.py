from __future__ import annotations

import re

_AIRPORT_ALIASES = {
    "del": "DEL",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "bombay": "BOM",
    "bom": "BOM",
    "bengaluru": "BLR",
    "bangalore": "BLR",
    "blr": "BLR",
    "hyderabad": "HYD",
    "hyd": "HYD",
    "goa": "GOI",
    "goi": "GOI",
    "chennai": "MAA",
    "madras": "MAA",
    "maa": "MAA",
    "kolkata": "CCU",
    "calcutta": "CCU",
    "ccu": "CCU",
    "pune": "PNQ",
    "pnq": "PNQ",
    "ahmedabad": "AMD",
    "amd": "AMD",
    "lucknow": "LKO",
    "lko": "LKO",
    "kochi": "COK",
    "cochin": "COK",
    "cok": "COK",
    "visakhapatnam": "VTZ",
    "vizag": "VTZ",
    "vtz": "VTZ",
    "jaipur": "JAI",
    "jai": "JAI",
    "guwahati": "GAU",
    "gau": "GAU",
    "chandigarh": "IXC",
    "ixc": "IXC",
    "dubai": "DXB",
    "dxb": "DXB",
    "singapore": "SIN",
    "sin": "SIN",
    "london": "LHR",
    "lhr": "LHR",
    "bangkok": "BKK",
    "bkk": "BKK",
    "almaty": "ALA",
    "ala": "ALA",
    "new york": "JFK",
    "jfk": "JFK",
    "paris": "CDG",
    "cdg": "CDG",
    "tokyo": "HND",
    "hnd": "HND",
    "frankfurt": "FRA",
    "fra": "FRA",
    "sydney": "SYD",
    "syd": "SYD",
}

_AIRPORT_MENTION = re.compile(
    r"(?<![A-Za-z])("
    + "|".join(
        re.escape(alias)
        for alias in sorted(_AIRPORT_ALIASES, key=len, reverse=True)
    )
    + r")(?![A-Za-z])",
    re.IGNORECASE,
)


def normalize_airport_code(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    return _AIRPORT_ALIASES.get(normalized, value.strip().upper())


def find_airport_codes(text: str) -> list[tuple[str, int]]:
    return [
        (normalize_airport_code(match.group()), match.start())
        for match in _AIRPORT_MENTION.finditer(text)
    ]
