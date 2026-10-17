import re
import unicodedata


def normalize_text(value: str | None) -> str:
    """Normalize user/product text for conservative term matching."""

    if not value:
        return ""

    without_accents = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_accents.lower()).strip()


def contains_term(text: str, term: str) -> bool:
    normalized_text = normalize_text(text)
    normalized_term = normalize_text(term)
    if not normalized_text or not normalized_term:
        return False
    return f" {normalized_term} " in f" {normalized_text} "
