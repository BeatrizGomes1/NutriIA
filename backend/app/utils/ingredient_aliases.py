from dataclasses import dataclass

from app.utils.helpers import contains_term, normalize_text


ALIASES_BY_CONCEPT = {
    "milk": (
        "milk",
        "leite",
        "milk powder",
        "skimmed milk powder",
        "skim milk powder",
        "leite em po",
        "leite em po desnatado",
        "milk solids",
        "milk protein",
        "lactose",
        "casein",
        "caseina",
        "caseinate",
        "caseinato",
        "whey",
        "whey powder",
        "soro de leite",
        "proteina do soro do leite",
    ),
    "sugar": (
        "sugar",
        "acucar",
        "sugars",
        "sucrose",
        "sacarose",
        "glucose",
        "glicose",
        "dextrose",
        "glucose syrup",
        "xarope de glicose",
        "corn syrup",
        "xarope de milho",
        "high fructose corn syrup",
        "xarope de milho rico em frutose",
    ),
}

RELATED_TERMS_BY_CONCEPT = {
    "sugar": ("maltodextrin", "maltodextrina"),
}


@dataclass(frozen=True)
class IngredientAliasMatch:
    concept: str
    source_excerpt: str
    matched_term: str
    relation: str


def find_ingredient_alias(profile_term: str, ingredients_text: str) -> IngredientAliasMatch | None:
    ingredient_parts = [
        part.strip(" \t\r\n.:")
        for part in ingredients_text.replace("(", ",").replace(")", ",").split(",")
    ]
    ingredient_parts = [
        part for semicolon_part in ingredient_parts for part in semicolon_part.split(";")
    ]

    for part in ingredient_parts:
        if contains_term(part, profile_term):
            return IngredientAliasMatch(
                concept="literal",
                source_excerpt=part.strip(),
                matched_term=profile_term,
                relation="exact",
            )

    normalized_profile_term = normalize_text(profile_term)
    for concept, aliases in ALIASES_BY_CONCEPT.items():
        if not any(contains_term(normalized_profile_term, alias) for alias in aliases):
            continue

        for part in ingredient_parts:
            for alias in sorted(aliases, key=len, reverse=True):
                if contains_term(part, alias):
                    relation = "synonym" if normalize_text(alias) != normalized_profile_term else "exact"
                    return IngredientAliasMatch(
                        concept=concept,
                        source_excerpt=part.strip(),
                        matched_term=alias,
                        relation=relation,
                    )

        for part in ingredient_parts:
            for related_term in RELATED_TERMS_BY_CONCEPT.get(concept, ()):
                if contains_term(part, related_term):
                    return IngredientAliasMatch(
                        concept=concept,
                        source_excerpt=part.strip(),
                        matched_term=related_term,
                        relation="related",
                    )

    return None
