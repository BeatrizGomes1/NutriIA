"""Verified nutritional observations, independent of food-safety decisions.

The provider may select/reorder observation IDs, but cannot supply unchecked
clinical promises, quantities, or ingredient-based sodium classifications.
"""
import re

from app.models.nutrition import AnalysisContext, AnalysisResult
from app.utils.helpers import normalize_text
from app.services.food_safety import assess_food_safety
from app.services.goal_assessment import assess_goal, GOAL_RULES_VERSION

PERSONALIZATION_VERSION = "nutrition-observations-v3:ingredient-quality-v1:" + GOAL_RULES_VERSION


def observation_catalog(context: AnalysisContext) -> dict[str, dict]:
    product, profile = context.product, context.profile
    nutrition = product.nutrition
    observations = {}

    def add(identifier, text, evidence):
        observations[identifier] = {"id": identifier, "text": text,
                                    "evidence": list(dict.fromkeys(e for e in evidence if e))}

    goal = str(profile.get("goal") or "")
    assessment = assess_goal(nutrition, goal)
    for index, observation in enumerate(assessment.observations):
        evidence = [goal]
        if assessment.state in {"evaluated", "partial"}:
            evidence.extend(str(value) for value in (nutrition.calories_kcal, nutrition.protein_g, nutrition.fiber_g)
                            if value is not None)
        add(f"goal_assessment:{index}", observation, evidence)
    if assessment.state == "inconsistent":
        add("goal", "Os dados nutricionais precisam de revis\u00e3o antes de avaliar seu objetivo.", [goal])
    elif goal == "muscle_gain" and "protein" not in assessment.findings:
        if nutrition.protein_g is not None and nutrition.protein_g > 0:
            message = ("H\u00e1 prote\u00edna informada no r\u00f3tulo, relevante para contextualizar seu objetivo "
                       "de ganho de massa muscular; isso n\u00e3o comprova adequa\u00e7\u00e3o da dieta.")
        else:
            message = ("Seu objetivo \u00e9 ganho de massa muscular; os dados dispon\u00edveis n\u00e3o permitem "
                       "avaliar o aporte proteico do produto.")
        add("goal", message, [goal])
    elif goal == "weight_loss" and not assessment.findings:
        add("goal", "Seu objetivo \u00e9 perda de peso; um produto isolado n\u00e3o permite concluir "
            "se a dieta atende a esse objetivo.", [goal])

    raw = product.ingredients_text or ", ".join(product.ingredients)
    milk_declared = bool(assess_food_safety(product, {"allergies": ["leite"]}).conflicts)
    # A declared lactose restriction is not a clinical diagnosis and milk alone
    # is not sufficient to create a confirmed lactose conflict.
    for index, restriction in enumerate(profile.get("restrictions", []) or []):
        target = re.sub(r"^(?:intolerancia a|intolerante a|sem|restricao a|evitar)\s+", "", normalize_text(restriction))
        if target == "lactose" and not _has_lactose_free_claim(product.name or "", raw):
            add(f"lactose_restriction:{index}",
                ("Para sua restri\u00e7\u00e3o de lactose, " +
                 ("h\u00e1 leite declarado, mas " if milk_declared else "") +
                 "n\u00e3o foi poss\u00edvel confirmar uma declara\u00e7\u00e3o de zero lactose. ") +
                "A lactase, sozinha, n\u00e3o confirma isso.", [restriction])
    for index, preference in enumerate(profile.get("preferences", []) or []):
        normalized = normalize_text(preference)
        identifier = f"preference:{index}"
        if normalized in {"sem lactose", "zero lactose", "lactose free"}:
            sources = [product.name or "", raw]
            claim = None
            for source in sources:
                for match in re.finditer(r"\b(?:zero lactose|sem lactose|lactose[ -]free)\b", source, re.IGNORECASE):
                    prefix = normalize_text(source[:match.start()])
                    if not re.search(r"(?:nao(?: e| declara)?|not(?: declared)?)$", prefix):
                        claim = match.group()
                        break
                if claim:
                    break
            if claim:
                add(identifier, f"O produto declara '{claim}', relacionado \u00e0 prefer\u00eancia "
                    f"'{preference}'; essa declara\u00e7\u00e3o n\u00e3o garante seguran\u00e7a para alergias.",
                    [claim, preference])
            else:
                prefix = "H\u00e1 leite declarado na fonte. " if milk_declared else ""
                add(identifier, prefix + f"N\u00e3o h\u00e1 declara\u00e7\u00e3o expl\u00edcita dispon\u00edvel para confirmar a "
                    f"prefer\u00eancia '{preference}'; a presen\u00e7a de lactase, sozinha, n\u00e3o confirma seu atendimento.",
                    [preference])
        elif normalized in {"baixo sodio", "low sodium"}:
            if nutrition.basis == "unknown" or nutrition.sodium_mg is None:
                add(identifier, f"Para a prefer\u00eancia '{preference}', faltam dados de s\u00f3dio com "
                    "refer\u00eancia confirmada; n\u00e3o \u00e9 poss\u00edvel classificar o teor como baixo ou alto.",
                    [preference])
            else:
                add(identifier, f"A prefer\u00eancia '{preference}' deve ser avaliada pelos valores de "
                    "s\u00f3dio e sua refer\u00eancia, n\u00e3o pela presen\u00e7a isolada de um ingrediente.", [preference])
        else:
            add(identifier, f"A prefer\u00eancia declarada \u00e9 '{preference}'; os dados dispon\u00edveis "
                "n\u00e3o bastam para confirmar seu atendimento.", [preference])

    if nutrition.basis == "unknown" and nutrition.has_any_value():
        add("basis", "A refer\u00eancia dos valores nutricionais \u00e9 desconhecida; n\u00e3o \u00e9 poss\u00edvel "
            "quantificar por por\u00e7\u00e3o ou comparar teores com confian\u00e7a.", [])
    elif assessment.state != "inconsistent":
        basis = {"per_100g": "por 100 g", "per_100ml": "por 100 ml",
                 "per_serving": "por por\u00e7\u00e3o"}.get(nutrition.basis)
        for field, label, unit in (("fiber_g", "fibras", "g"), ("protein_g", "prote\u00ednas", "g"), ("sodium_mg", "s\u00f3dio", "mg"),
                                   ("calories_kcal", "energia", "kcal"), ("sugars_g", "a\u00e7\u00facares", "g"),
                                   ("carbohydrates_g", "carboidratos", "g")):
            value = getattr(nutrition, field)
            if basis and value is not None:
                # Display the supplied value only. No conversions or thresholds.
                add(f"nutrient:{field}", f"O r\u00f3tulo informa {value:g} {unit} de {label} {basis}.",
                    [str(value)])
    if raw.strip() and product.food_safety.ingredients_status != "unreadable":
        label = "Trecho dispon\u00edvel de ingredientes" if product.food_safety.ingredients_status == "incomplete" else "Ingredientes informados"
        add("ingredients", f"{label}: {raw}", [raw])
    return observations


def _has_lactose_free_claim(*sources):
    for source in sources:
        for match in re.finditer(r"\b(?:zero lactose|sem lactose|lactose[ -]free)\b", source, re.IGNORECASE):
            prefix = normalize_text(source[:match.start()])
            if not re.search(r"(?:nao(?: e| declara)?|not(?: declared)?)$", prefix):
                return True
    return False


def verified_explanations(context: AnalysisContext, selected_ids=(), proposed_texts=()):
    catalog = observation_catalog(context)
    # Selection can change ordering, never invent facts or omit the remaining
    # supported context. Legacy summary/reasons survive when matching a fact.
    texts = {item["text"]: key for key, item in catalog.items()}
    order = list(dict.fromkeys([*(texts[t] for t in proposed_texts if t in texts),
                              *(key for key in selected_ids if key in catalog), *catalog]))
    return [catalog[key]["text"] for key in order], list(dict.fromkeys(
        excerpt for key in order for excerpt in catalog[key]["evidence"]))


def has_nutritional_context(context: AnalysisContext) -> bool:
    return bool(context.profile.get("goal") or context.profile.get("preferences")
                or context.product.nutrition.has_any_value())


def append_nutrition(guarded: AnalysisResult, context: AnalysisContext) -> AnalysisResult:
    reasons, evidence = verified_explanations(context)
    return guarded.model_copy(update={
        "reasons": list(dict.fromkeys([*guarded.reasons, *reasons])),
        "evidence": list(dict.fromkeys([*guarded.evidence, *evidence])),
    })
