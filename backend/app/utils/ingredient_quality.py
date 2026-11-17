"""Conservative separation of source text; never repairs unreadable words."""
import re

from app.utils.helpers import normalize_text

INGREDIENTS_VERSION = "ingredient-quality-v1"


def separate_ingredients(raw: str) -> tuple[str, bool]:
    text = normalize_text(raw)
    # Require multiple table signals, not a lone ingredient such as protein.
    signals = sum(bool(re.search(pattern, text)) for pattern in (
        r"\b(?:informacao nutricional|normacao nutricional|valor energetico)\b",
        r"\b(?:kcal|percentual de valores diarios|vd)\b",
        r"\b(?:carboidratos|gorduras totais|fibras alimentares|sodio)\b.*\d",
    ))
    if signals < 2:
        return raw, False
    # An explicit heading is needed to identify a surviving ingredient section.
    # If the OCR damaged the heading we do not guess where the list starts.
    heading = re.search(r"(?i)\bingredientes\b[^:\n]{0,60}:\s*", raw)
    if not heading:
        return "", True
    candidate = raw[heading.end():].strip()
    tail, contaminated = separate_ingredients(candidate)
    return tail if not contaminated else "", True
