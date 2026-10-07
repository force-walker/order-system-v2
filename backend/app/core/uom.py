CANONICAL_UOMS = frozenset({"piece", "case", "kg"})

UOM_ALIASES = {
    "kg": "kg",
    "piece": "piece",
    "pc": "piece",
    "count": "piece",
    "case": "case",
    "ctn": "case",
}


def normalize_uom(value: str | None) -> str | None:
    normalized = (value or "").strip().casefold()
    if not normalized:
        return None
    return UOM_ALIASES.get(normalized, normalized)


def canonicalize_uom_input(value: str | None) -> str | None:
    normalized = normalize_uom(value)
    if normalized is not None and normalized not in CANONICAL_UOMS:
        raise ValueError("UOM must be one of: case, kg, piece")
    return normalized
