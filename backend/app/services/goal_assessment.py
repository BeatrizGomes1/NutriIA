"""Quantitative product composition, never a diet/consumption prescription.

References: EC 1924/2006 Annex (protein/fibre composition benchmarks),
EU 1169/2011 Annex XIV (4 kcal/g protein, 2 kcal/g fibre).
See NUTRITION_GOAL_CRITERIA.md for scope, formulas and limitations.
"""
from dataclasses import dataclass, field
from decimal import Decimal, localcontext

from pydantic import ValidationError
from app.models.nutrition import NutritionFacts

GOAL_RULES_VERSION = "goal-composition-v1"
REFERENCE = "EC 1924/2006 Annex; EU 1169/2011 Annex XIV"


def number(value):
    return Decimal(str(value)) if value is not None else None


def display(value):
    if not value:
        return "0"
    if value < Decimal("0.01") or value >= Decimal("1000000"):
        return format(value, ".6g")
    with localcontext() as ctx:
        ctx.prec = max(28, value.adjusted() + 6)
        return format(value.quantize(Decimal("0.01")), "f").rstrip("0").rstrip(".")


@dataclass
class GoalAssessment:
    goal: str
    state: str = "insufficient"
    metrics: dict[str, Decimal] = field(default_factory=dict)
    findings: dict[str, str] = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    reference: str = REFERENCE


def assess_goal(nutrition: NutritionFacts, goal: str) -> GoalAssessment:
    result = GoalAssessment(goal)
    if goal not in {"muscle_gain", "weight_loss"}:
        return result
    label = "ganho de massa" if goal == "muscle_gain" else "perda de peso"
    prefix = f"Avalia\u00e7\u00e3o para {label}: "
    try:
        facts = NutritionFacts.model_validate({name: getattr(nutrition, name, None) for name in NutritionFacts.model_fields})
    except (ValidationError, TypeError, ValueError):
        result.state = "inconsistent"
        result.observations.append("Dados nutricionais inconsistentes: os valores s\u00e3o inv\u00e1lidos e n\u00e3o foram usados em c\u00e1lculos.")
        return result
    if facts.basis == "unknown":
        result.missing.append("nutrition.basis")
        result.observations.append("Detalhe da avalia\u00e7\u00e3o: falta confirmar a refer\u00eancia dos nutrientes para avaliar as quantidades para " + label + ".")
        return result

    energy, protein, fibre = map(number, (facts.calories_kcal, facts.protein_g, facts.fiber_g))
    carbs, sugars = map(number, (facts.carbohydrates_g, facts.sugars_g))
    portion = number(facts.serving_quantity)
    mass = Decimal(100) if facts.basis == "per_100g" else (
        portion if facts.basis == "per_serving" and facts.serving_unit == "g" else None)
    inconsistent = (
        mass is not None and any(v is not None and v > mass for v in (protein, fibre, carbs, sugars))
        or mass is not None and protein is not None and carbs is not None and protein + carbs > mass
        or carbs is not None and sugars is not None and sugars > carbs
        or energy is not None and protein is not None and protein * 4 > energy
        or energy is not None and fibre is not None and fibre * 2 > energy
        or energy is not None and sum(v * factor for v, factor in ((protein, 4), (fibre, 2)) if v is not None) > energy
    )
    if inconsistent:
        result.state = "inconsistent"
        result.observations.append("Dados nutricionais inconsistentes: os nutrientes e sua refer\u00eancia precisam de revis\u00e3o antes dos c\u00e1lculos.")
        return result

    # Convert only within the same mass/volume dimension; never infer density.
    reference_quantity = Decimal(100) if facts.basis in {"per_100g", "per_100ml"} else portion
    unit = {"per_100g": "g", "per_100ml": "ml"}.get(facts.basis, facts.serving_unit)
    energy100 = energy * 100 / reference_quantity if energy is not None and reference_quantity else None
    fibre100g = fibre * 100 / reference_quantity if fibre is not None and unit == "g" and reference_quantity else None
    fibre100kcal = fibre * 100 / energy if fibre is not None and energy is not None and energy > 0 else None

    if goal == "muscle_gain":
        if energy is not None and energy > 0 and protein is not None:
            percentage = protein * 4 * 100 / energy
            result.metrics["protein_energy_percent"] = percentage
            level = "high" if percentage >= 20 else "source" if percentage >= 12 else "below_source"
            result.findings["protein"] = level
            description = {"high": "atinge a refer\u00eancia de alta propor\u00e7\u00e3o proteica",
                           "source": "atinge a refer\u00eancia de fonte de prote\u00ednas",
                           "below_source": "fica abaixo da refer\u00eancia de fonte de prote\u00ednas"}[level]
            result.observations.append(prefix + f"cerca de {display(percentage)}% da energia vem de prote\u00ednas; {description}.")
            result.observations.append("Detalhe da avalia\u00e7\u00e3o: prote\u00edna (g) \u00d7 4 kcal/g \u00f7 energia (kcal), na mesma base; refer\u00eancias de 12% e 20% da energia.")
        else:
            result.missing.extend(k for k, v in (("protein_g", protein), ("calories_kcal", energy)) if v is None or k == "calories_kcal" and v == 0)
            result.observations.append(prefix + "faltam prote\u00ednas e energia compar\u00e1veis para avaliar a propor\u00e7\u00e3o proteica.")
    else:
        if energy100 is not None:
            result.metrics[f"energy_kcal_per_100{unit}"] = energy100
            result.findings["energy_density"] = "measured"
            result.observations.append(prefix + f"densidade energ\u00e9tica de {display(energy100)} kcal por 100 {unit}, sem concluir que o produto causa emagrecimento.")
            result.observations.append("Detalhe da avalia\u00e7\u00e3o: a densidade energ\u00e9tica permite comparar energia em quantidades iguais, somente na mesma unidade; n\u00e3o h\u00e1 limite arbitr\u00e1rio de calorias nesta regra.")
        else:
            result.missing.append("calories_kcal" if energy is None else "serving_quantity/unit")
            result.observations.append(prefix + "faltam energia ou tamanho da por\u00e7\u00e3o com unidade para avaliar a densidade energ\u00e9tica.")
        if fibre is None:
            result.missing.append("fiber_g")
            result.observations.append("Detalhe da avalia\u00e7\u00e3o: fibras n\u00e3o informadas; aus\u00eancia do dado n\u00e3o significa zero fibras.")
        else:
            high = (fibre100g is not None and fibre100g >= 6) or (fibre100kcal is not None and fibre100kcal >= 3)
            source = (fibre100g is not None and fibre100g >= 3) or (fibre100kcal is not None and fibre100kcal >= Decimal("1.5"))
            result.findings["fibre"] = "high" if high else "source" if source else "not_established"
            if fibre100g is not None:
                result.metrics["fibre_g_per_100g"] = fibre100g
            if fibre100kcal is not None:
                result.metrics["fibre_g_per_100kcal"] = fibre100kcal
            text = ("atinge a refer\u00eancia de alto teor de fibras" if high else
                    "atinge a refer\u00eancia de fonte de fibras" if source else
                    "os dados dispon\u00edveis n\u00e3o demonstram o atendimento \u00e0 refer\u00eancia de fonte de fibras")
            result.observations.append(prefix + text + ".")
            quantities = []
            if fibre100g is not None:
                quantities.append(f"{display(fibre100g)} g de fibras por 100 g")
            if fibre100kcal is not None:
                quantities.append(f"{display(fibre100kcal)} g de fibras por 100 kcal")
            if quantities:
                result.observations.append("Detalhe da avalia\u00e7\u00e3o: fibras calculadas, aproximadamente " + "; ".join(quantities) + ".")
            result.observations.append("Detalhe da avalia\u00e7\u00e3o: refer\u00eancias de fibras de 3/6 g por 100 g ou 1,5/3 g por 100 kcal; somente as bases calcul\u00e1veis foram consideradas.")

    # A labelled serving is a reference quantity, never a recommended dose.
    compatible_portion = facts.basis == "per_serving" or (
        portion is not None and facts.serving_unit == unit and reference_quantity is not None)
    if compatible_portion and (energy is not None or protein is not None or fibre is not None):
        factor = Decimal(1) if facts.basis == "per_serving" else portion / reference_quantity
        values = []
        for key, value, suffix in (("calories_kcal", energy, "kcal"), ("protein_g", protein, "g de prote\u00ednas"), ("fiber_g", fibre, "g de fibras")):
            if value is not None:
                result.metrics[f"serving_{key}"] = value * factor
                values.append(f"{display(value * factor)} {suffix}")
        size = f" de {display(portion)} {facts.serving_unit}" if portion is not None else " (tamanho n\u00e3o informado)"
        result.observations.append("Detalhe da avalia\u00e7\u00e3o: na por\u00e7\u00e3o declarada" + size + ", " + "; ".join(values) + ". N\u00e3o \u00e9 recomenda\u00e7\u00e3o de consumo.")
    elif facts.basis != "per_serving":
        result.missing.append("compatible_serving_quantity/unit")
    result.state = "evaluated" if result.findings and not result.missing else "partial" if result.findings else "insufficient"
    return result
