"""Conservative, evidence-based rules independent of the language model.

A lack of matches guarantees neither absence nor safety. The dictionary is
intentionally bounded: unknown derivatives are not invented.
"""
from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from typing import Any

from app.models.nutrition import AnalysisContext, AnalysisResult, AnalysisStatus, Conflict, Product
from app.utils.helpers import contains_term, normalize_text

RULES_VERSION = "food-safety-v2"
NO_GUARANTEE = "A aus\u00eancia de conflito identificado n\u00e3o garante seguran\u00e7a alimentar."

# Food concepts remain distinct. In particular lactose is NOT milk protein.
ALIASES = {
    "milk": ("leite", "milk", "leite em po", "milk powder", "caseina", "casein",
             "caseinato", "caseinate", "caseinato de sodio", "sodium caseinate",
             "caseinato de calcio", "calcium caseinate", "whey", "soro de leite",
             "proteina do leite", "milk protein", "lactalbumina", "lactoglobulina"),
    "casein": ("caseina", "casein", "caseinato", "caseinate", "caseinato de sodio",
               "sodium caseinate", "caseinato de calcio", "calcium caseinate"),
    "whey": ("whey", "soro de leite", "proteina do soro do leite", "whey protein"),
    "lactose": ("lactose",),
    "peanut": ("amendoim", "amendoins", "peanut", "peanuts", "arachis hypogaea"),
    "soy": ("soja", "soy", "soya", "soybean", "soybeans", "lecitina de soja",
            "soy lecithin", "proteina de soja", "soy protein", "tofu"),
    "wheat": ("trigo", "wheat", "farinha de trigo", "wheat flour", "triticum aestivum"),
    "gluten": ("gluten", "trigo", "wheat", "cevada", "barley", "centeio", "rye"),
    "sugar": ("acucar", "sugar", "sugars", "sacarose", "sucrose", "glicose",
              "glucose", "dextrose", "xarope de glicose", "glucose syrup"),
}
PROFILE_NAMES = {
    "milk": ("leite", "milk", "proteina do leite", "proteinas do leite", "aplv"),
    "casein": ("caseina", "casein", "caseinato", "caseinate"),
    "whey": ("whey", "soro de leite", "proteina do soro do leite"),
    "lactose": ("lactose",),
    "peanut": ("amendoim", "amendoins", "peanut", "peanuts"),
    "soy": ("soja", "soy", "soya"),
    "wheat": ("trigo", "wheat"),
    "gluten": ("gluten",),
    "sugar": ("acucar", "sugar"),
}
MAY = re.compile(r"\b(?:pode conter|podem conter|may contain|tracos de|traces of|"
                 r"produzido em|fabricado em|produced in|manufactured in|shared equipment)\b")
NEGATIVE = re.compile(r"\b(?:nao contem|sem|livre de|isento de|zero|"
                      r"does not contain|free from|no)\b")
UNREADABLE = re.compile(r"\b(?:ilegivel|unreadable|illegible|incompleto|incomplete|"
                        r"nao informado|nao disponivel|nao legivel|indisponivel|unknown|n a|parcial|etc)\b")


@dataclass
class SafetyAssessment:
    conflicts: list[Conflict] = field(default_factory=list)
    cross_contact: list[Conflict] = field(default_factory=list)
    insufficient_reasons: list[str] = field(default_factory=list)

    def result(self, context: AnalysisContext) -> AnalysisResult | None:
        reasons = list(dict.fromkeys([*context.blocking_reasons, *self.insufficient_reasons]))
        # Missing data cannot undo a conflict already supported by evidence.
        # Keep the missing-data reasons alongside all confirmed/possible alerts.
        if self.conflicts:
            status = AnalysisStatus.NOT_RECOMMENDED
            summary = "Conflito identificado com alergia ou restri\u00e7\u00e3o declarada."
        elif reasons:
            status = AnalysisStatus.INSUFFICIENT_INFORMATION
            summary = "Informa\u00e7\u00f5es insuficientes para avaliar o produto."
        elif self.cross_contact:
            status = AnalysisStatus.ATTENTION
            summary = "Poss\u00edvel contamina\u00e7\u00e3o cruzada declarada na fonte."
        else:
            return None
        conflicts = [*self.conflicts, *self.cross_contact]
        return AnalysisResult(status=status, product_name=context.product.name or context.product.ean,
            summary=summary, reasons=[*reasons, *(c.evidence for c in conflicts), NO_GUARANTEE],
            conflicts=conflicts, evidence=list(dict.fromkeys(c.source_excerpt for c in conflicts)),
            provider="deterministic_guardrail")


def _profile_concept(item: str) -> str | None:
    text = normalize_text(item)
    # Match declared targets, not incidental substrings in arbitrary prose.
    text = re.sub(r"^(?:alergia (?:a|ao|as|aos)|alergico a|intolerancia a|"
                  r"intolerante a|sem|evitar|evito|restricao a)\s+", "", text)
    for concept, names in PROFILE_NAMES.items():
        if text in names:
            return concept
    return None


def _segments(text: str):
    # Split clauses before normalization so excerpts remain literal. Commas
    # within a warning keep its scope until a sentence or new declaration.
    for clause in re.split(r"[.\n]+", text):
        markers = list(re.finditer(r"(?i)\b(?:pode conter|podem conter|may contain|"
                                  r"tra[c\u00e7]os de|traces of|produzido em|fabricado em|produced in|"
                                  r"manufactured in|shared equipment|"
                                  r"n[a\u00e3]o cont[e\u00e9]m|contains|cont[e\u00e9]m)\b", clause))
        starts = sorted({0, *(m.start() for m in markers)})
        for start, end in zip(starts, [*starts[1:], len(clause)]):
            part = clause[start:end].strip(" ,:;")
            if not part:
                continue
            normalized = normalize_text(part)
            if MAY.search(normalized) or normalized.startswith(("nao contem", "does not contain", "free from")):
                yield part
                continue
            # Separate ordinary ingredients without separating subingredients.
            # A plant drink must not mask a later, explicitly listed milk.
            depth, start = 0, 0
            for index, character in enumerate(part):
                if character in "([":
                    depth += 1
                elif character in ")]":
                    depth = max(0, depth - 1)
                elif character in ",;" and depth == 0:
                    ingredient = part[start:index].strip()
                    if ingredient:
                        yield ingredient
                    start = index + 1
            ingredient = part[start:].strip()
            if ingredient:
                yield ingredient


def _is_negative(text: str, alias: str) -> bool:
    # Only negate a target in the scope of that declaration. A claim such as
    # "zero lactose" does not negate milk proteins in the same clause.
    for marker in NEGATIVE.finditer(text):
        scope = text[marker.end():]
        if marker.group() in {"nao contem", "does not contain", "free from"}:
            if contains_term(scope, alias):
                return True
        elif scope.strip().startswith(alias + " ") or scope.strip() == alias:
            return True
    if re.search(r"\b" + re.escape(alias) + r" free\b", text):
        return True
    # Ignore only occurrences inside a plant-drink name, not every milk
    # occurrence in the excerpt (e.g. 'leite de soja com leite').
    if alias in {"leite", "milk"}:
        remainder, plant_names = re.subn(
            r"\b(?:leite de (?:soja|coco|amendoa|aveia|arroz)|"
            r"(?:soy|coconut|almond|oat|rice) milk)\b", " ", text)
        return bool(plant_names) and not contains_term(remainder, alias)
    return False


def assess_food_safety(product: Product, profile: Mapping[str, Any]) -> SafetyAssessment:
    assessment = SafetyAssessment()
    # Prefer original text. The normalized list can lose negation boundaries.
    raw = product.ingredients_text or ", ".join(product.ingredients)
    normalized = normalize_text(raw)
    if (not normalized or normalized in {"ingredientes", "ingredients", "contains", "contem", "n a", "null"}
            or product.food_safety.ingredients_status in {"incomplete", "unreadable"}
            or UNREADABLE.search(normalized) or "..." in raw or "\u2026" in raw):
        assessment.insufficient_reasons.append(
            "A lista de ingredientes est\u00e1 ausente, ileg\u00edvel ou incompleta.")
    sources = [(raw, False), (product.food_safety.ingredient_source_text or "", False),
               (product.food_safety.allergen_statement or "", False),
               (product.food_safety.cross_contact_statement or "", True)]
    seen = set()
    for category, key in (("allergy", "allergies"), ("restriction", "restrictions")):
        for item in profile.get(key, []) or []:
            if not isinstance(item, str) or not normalize_text(item):
                continue
            concept = _profile_concept(item)
            aliases = ALIASES.get(concept, (normalize_text(item),))
            for source, possible in sources:
                for excerpt in _segments(source):
                    text = normalize_text(excerpt)
                    for alias in sorted(aliases, key=len, reverse=True):
                        if not contains_term(text, alias) or _is_negative(text, alias):
                            continue
                        is_cross = possible or bool(MAY.search(text))
                        identity = (category, normalize_text(item), excerpt, is_cross)
                        if identity in seen:
                            break
                        seen.add(identity)
                        explanation = (
                            "Poss\u00edvel contamina\u00e7\u00e3o cruzada: " if is_cross
                            else "Presen\u00e7a declarada na fonte: "
                        ) + f"'{excerpt}', relacionada a '{item}'."
                        conflict = Conflict(term=alias, category=category, profile_item=item,
                                            evidence=explanation, source_excerpt=excerpt)
                        (assessment.cross_contact if is_cross else assessment.conflicts).append(conflict)
                        break
    return assessment


def deterministic_result(context: AnalysisContext) -> AnalysisResult | None:
    return assess_food_safety(context.product, context.profile).result(context)
